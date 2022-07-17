"""
The listener of wait_dumping_ntlm queue.
Having received a message from the wait_dumping_ntlm queue, it runs the instance of
the process of dumping NTLM-hashes for the specific domain and returns it to the info_dumping_ntlm queue.
"""
import json
import os
import sys
from typing import Any

import pika
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import insert

import modules.support_functions as sup_f
from enviroment import RMQ_CONFIG, NTLM_SCRUT_CONFIG, LOGS_DIR, DATABASE_URI, LOG_CONFIG
from models import NTLMDumpSession
from modules.ntlm_scrut_interface import NTLMScrutInterface

filename = os.path.basename(__file__).split('.')[0]
logger = sup_f.init_custome_logger(
    os.path.join(LOGS_DIR, f'{filename}.log'),
    os.path.join(LOGS_DIR, f'{filename}_error.log'),
    logging_level=LOG_CONFIG['level'],
)


def rmq_callback(current_channel: Any, method: Any, _: Any, body: Any) -> None:
    """
    The performer of the received message from the queue
    """
    rmq_c = None
    msg = {}
    try:
        logger.info('Working on a msg')
        # {"model": "user_cabinet.domain", "pk": 7, "fields": {"name": "AAA", "hostname": "AD-DC.AA.BB",
        # "workstation_name": "DCSonarWS$", "workstation_password": "m3whgiSrgr0PMnNJ...IWD9QLe5d+A=="}}
        msg = json.loads(body.decode('utf-8'))
        logger.info('msg: %s', msg)
        ntlm_scrut_i = NTLMScrutInterface(**NTLM_SCRUT_CONFIG)
        engine = create_engine(DATABASE_URI, future=True)

        data = ntlm_scrut_i.dump_ntlm_run(
            f"{msg['fields']['name']}/{msg['fields']['workstation_name']}:"
            f"{msg['fields']['workstation_password']}@{msg['fields']['hostname']}"
        )
        logger.info('data: %s', data)

        with engine.connect() as conn:
            stmt = insert(NTLMDumpSession).values(
                session_name=data['session_name'],
                domain_name=msg['fields']['name'],
                domain_pk=msg['pk'],
            )
            stmt = stmt.on_conflict_do_update(
                constraint='ntlm_dump_session_domain_pk_key',
                set_={'session_name': data['session_name']},
            )
            conn.execute(stmt)
            conn.commit()

        rmq_c = pika.BlockingConnection(pika.ConnectionParameters(**RMQ_CONFIG))
        dumping_ntlm_info_ch = rmq_c.channel()
        dumping_ntlm_info_ch.queue_declare(queue='info_dumping_ntlm', durable=True)
        dumping_ntlm_info_ch.basic_publish(
            exchange='',
            routing_key='info_dumping_ntlm',
            body=sup_f.dict_to_json_bytes(
                {
                    'domain_pk': msg['pk'],
                    'domain_name': msg['fields']['name'],
                    'status': 'PERFORMING',
                    'error_desc': '',
                }
            ),
            properties=pika.BasicProperties(
                delivery_mode=2,  # make message persistent
            ),
        )

    except Exception as exc:
        logger.error('Error', exc_info=sys.exc_info())
        if msg:
            rmq_c = pika.BlockingConnection(pika.ConnectionParameters(**RMQ_CONFIG))
            dumping_ntlm_info_ch = rmq_c.channel()
            dumping_ntlm_info_ch.queue_declare(queue='info_dumping_ntlm', durable=True)
            dumping_ntlm_info_ch.basic_publish(
                exchange='',
                routing_key='info_dumping_ntlm',
                body=sup_f.dict_to_json_bytes(
                    {
                        'domain_pk': msg['pk'],
                        'domain_name': msg['fields']['name'],
                        'status': 'ERROR',
                        'error_desc': sup_f.get_error_text(exc),
                    }
                ),
                properties=pika.BasicProperties(
                    delivery_mode=2,  # make message persistent
                ),
            )
    finally:
        if rmq_c is not None:
            rmq_c.close()
        current_channel.basic_ack(delivery_tag=method.delivery_tag)


if __name__ == '__main__':

    rmq_conn = None   # pylint: disable=invalid-name
    try:
        rmq_conn = pika.BlockingConnection(pika.ConnectionParameters(**RMQ_CONFIG))
        dumping_ntlm_wait_ch = rmq_conn.channel()
        dumping_ntlm_wait_ch.queue_declare(queue='wait_dumping_ntlm', durable=True)
        dumping_ntlm_wait_ch.basic_consume(queue='wait_dumping_ntlm', on_message_callback=rmq_callback)
        dumping_ntlm_wait_ch.start_consuming()
    except Exception as e:
        logger.error('Error', exc_info=sys.exc_info())
    finally:
        if rmq_conn is not None:
            rmq_conn.close()
