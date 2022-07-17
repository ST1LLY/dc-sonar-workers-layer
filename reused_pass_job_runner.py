"""
The listener of wait_reused_pass_checking queue.
Having received a message from the wait_reused_pass_checking queue, it performs getting the information of
reused passwords accounts for the specific domain and returns it to the info_reused_pass_checking queue.
"""
import json
import os
import sys
from typing import Any

import pika
from sqlalchemy import create_engine, delete
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql import text

import modules.support_functions as sup_f
from enviroment import RMQ_CONFIG, LOGS_DIR, LOG_CONFIG, DATABASE_URI
from models import NTLMDumpHash

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
    domain = {}
    try:
        logger.info('Working on a msg')
        msg = json.loads(body.decode('utf-8'))
        logger.info('msg: %s', msg)
        domain = msg['domain']
        rmq_c = pika.BlockingConnection(pika.ConnectionParameters(**RMQ_CONFIG))
        reused_pass_info_ch = rmq_c.channel()
        reused_pass_info_ch.queue_declare(queue='info_reused_pass_checking', durable=True)
        reused_pass_info_ch.basic_publish(
            exchange='',
            routing_key='info_reused_pass_checking',
            body=sup_f.dict_to_json_bytes(
                {
                    'domain_pk': domain['pk'],
                    'domain_name': domain['fields']['name'],
                    'status': 'PERFORMING',
                    'error_desc': '',
                    'users': [],
                }
            ),
            properties=pika.BasicProperties(
                delivery_mode=2,  # make message persistent
            ),
        )

        engine = create_engine(DATABASE_URI)
        engine_session_maker = sessionmaker(engine)

        with engine_session_maker() as session:
            stmt_del = delete(NTLMDumpHash).where(~NTLMDumpHash.domain_pk.in_(msg['exist_domains_pk']))
            session.execute(stmt_del)
            session.commit()

        with engine_session_maker() as session:
            stmt = text(
                """
            with this_domain as (SELECT domain_pk, user_login, user_ntlm_hash
                FROM public.ntlm_dump_hash where domain_pk = :id),
                non_this_domain as (SELECT domain_pk, user_login, user_ntlm_hash
                FROM public.ntlm_dump_hash where domain_pk <> :id)
                select
                    this_domain.domain_pk as domain_pk,
                    this_domain.user_login as user_login,
                    non_this_domain.domain_pk as reused_domain_pk,
                    non_this_domain.user_login as reused_user_login
                from this_domain
                join non_this_domain on non_this_domain.user_ntlm_hash = this_domain.user_ntlm_hash;
            """
            )
            users = session.execute(stmt, {'id': domain['pk']})

        reused_pass_info_ch.basic_publish(
            exchange='',
            routing_key='info_reused_pass_checking',
            body=sup_f.dict_to_json_bytes(
                {
                    'domain_pk': domain['pk'],
                    'domain_name': domain['fields']['name'],
                    'status': 'FINISHED',
                    'error_desc': '',
                    'users': tuple(dict(row._mapping) for row in users),  # pylint: disable=protected-access
                }
            ),
            properties=pika.BasicProperties(
                delivery_mode=2,  # make message persistent
            ),
        )

    except Exception as exc:
        logger.error('Error', exc_info=sys.exc_info())
        if domain:
            rmq_c = pika.BlockingConnection(pika.ConnectionParameters(**RMQ_CONFIG))
            reused_pass_info_ch = rmq_c.channel()
            reused_pass_info_ch.queue_declare(queue='info_reused_pass_checking', durable=True)
            reused_pass_info_ch.basic_publish(
                exchange='',
                routing_key='info_reused_pass_checking',
                body=sup_f.dict_to_json_bytes(
                    {
                        'domain_pk': domain['pk'],
                        'domain_name': domain['fields']['name'],
                        'status': 'ERROR',
                        'error_desc': sup_f.get_error_text(exc),
                        'users': [],
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
        reused_pass_wait_ch = rmq_conn.channel()
        reused_pass_wait_ch.queue_declare(queue='wait_reused_pass_checking', durable=True)
        reused_pass_wait_ch.basic_consume(queue='wait_reused_pass_checking', on_message_callback=rmq_callback)
        reused_pass_wait_ch.start_consuming()
    except Exception:
        logger.error('Error', exc_info=sys.exc_info())
    finally:
        if rmq_conn is not None:
            rmq_conn.close()
