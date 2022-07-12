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


def rmq_callback(ch: Any, method: Any, properties: Any, body: Any) -> None:
    rmq_conn = None
    msg = {}
    try:
        logger.info('Working on a msg')
        # {"model": "user_cabinet.domain", "pk": 7, "fields": {"name": "AAA", "hostname": "AD-DC.AA.BB",
        # "workstation_name": "DCSonarWS$", "workstation_password": "m3whgiSrgr0PMnNJ...IWD9QLe5d+A=="}}
        msg = json.loads(body.decode('utf-8'))
        logger.info(f'msg: {msg}')
        ntlm_scrut_i = NTLMScrutInterface(**NTLM_SCRUT_CONFIG)
        engine = create_engine(DATABASE_URI, future=True)

        data = ntlm_scrut_i.dump_ntlm_run(
            f"{msg['fields']['name']}/{msg['fields']['workstation_name']}:"
            f"{msg['fields']['workstation_password']}@{msg['fields']['hostname']}"
        )
        logger.info(f'data: {data}')

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

        rmq_conn = pika.BlockingConnection(pika.ConnectionParameters(**RMQ_CONFIG))
        channel = rmq_conn.channel()
        channel.queue_declare(queue='info_dumping_ntlm', durable=True)
        channel.basic_publish(
            exchange='',
            routing_key='info_dumping_ntlm',
            body=sup_f.dict_to_json_bytes(
                {'domain_pk': msg['pk'], 'domain_name': msg['fields']['name'], 'status': 'PERFORMING', 'error_desc': ''}
            ),
            properties=pika.BasicProperties(
                delivery_mode=2,  # make message persistent
            ),
        )

    except Exception as e:
        logger.error('Error', exc_info=sys.exc_info())
        if msg:
            rmq_conn = pika.BlockingConnection(pika.ConnectionParameters(**RMQ_CONFIG))
            channel = rmq_conn.channel()
            channel.queue_declare(queue='info_dumping_ntlm', durable=True)
            channel.basic_publish(
                exchange='',
                routing_key='info_dumping_ntlm',
                body=sup_f.dict_to_json_bytes(
                    {
                        'domain_pk': msg['pk'],
                        'domain_name': msg['fields']['name'],
                        'status': 'ERROR',
                        'error_desc': sup_f.get_error_text(e),
                    }
                ),
                properties=pika.BasicProperties(
                    delivery_mode=2,  # make message persistent
                ),
            )
    finally:
        if rmq_conn is not None:
            rmq_conn.close()
        ch.basic_ack(delivery_tag=method.delivery_tag)


if __name__ == '__main__':

    rmq_conn = None
    try:
        rmq_conn = pika.BlockingConnection(pika.ConnectionParameters(**RMQ_CONFIG))
        channel = rmq_conn.channel()

        channel.queue_declare(queue='wait_dumping_ntlm', durable=True)
        channel.basic_consume(queue='wait_dumping_ntlm', on_message_callback=rmq_callback)
        channel.start_consuming()
    except Exception as e:
        logger.error('Error', exc_info=sys.exc_info())
    finally:
        if rmq_conn is not None:
            rmq_conn.close()
