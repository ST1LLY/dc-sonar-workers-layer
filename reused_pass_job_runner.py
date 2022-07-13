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


def rmq_callback(ch: Any, method: Any, properties: Any, body: Any) -> None:
    rmq_conn = None
    domain = {}
    try:
        logger.info('Working on a msg')
        msg = json.loads(body.decode('utf-8'))
        logger.info(f'msg: {msg}')
        domain = msg['domain']
        rmq_conn = pika.BlockingConnection(pika.ConnectionParameters(**RMQ_CONFIG))
        channel = rmq_conn.channel()
        channel.queue_declare(queue='info_reused_pass_checking', durable=True)
        channel.basic_publish(
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
        Session = sessionmaker(engine)

        with Session() as session:
            stmt_del = delete(NTLMDumpHash).where(~NTLMDumpHash.domain_pk.in_(msg['exist_domains_pk']))
            session.execute(stmt_del)
            session.commit()

        with Session() as session:
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

        channel.basic_publish(
            exchange='',
            routing_key='info_reused_pass_checking',
            body=sup_f.dict_to_json_bytes(
                {
                    'domain_pk': domain['pk'],
                    'domain_name': domain['fields']['name'],
                    'status': 'FINISHED',
                    'error_desc': '',
                    'users': tuple(dict(row._mapping) for row in users),
                }
            ),
            properties=pika.BasicProperties(
                delivery_mode=2,  # make message persistent
            ),
        )

    except Exception as e:
        logger.error('Error', exc_info=sys.exc_info())
        if domain:
            rmq_conn = pika.BlockingConnection(pika.ConnectionParameters(**RMQ_CONFIG))
            channel = rmq_conn.channel()
            channel.queue_declare(queue='info_reused_pass_checking', durable=True)
            channel.basic_publish(
                exchange='',
                routing_key='info_reused_pass_checking',
                body=sup_f.dict_to_json_bytes(
                    {
                        'domain_pk': domain['pk'],
                        'domain_name': domain['fields']['name'],
                        'status': 'ERROR',
                        'error_desc': sup_f.get_error_text(e),
                        'users': [],
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

        channel.queue_declare(queue='wait_reused_pass_checking', durable=True)
        channel.basic_consume(queue='wait_reused_pass_checking', on_message_callback=rmq_callback)
        channel.start_consuming()
    except Exception as e:
        logger.error('Error', exc_info=sys.exc_info())
    finally:
        if rmq_conn is not None:
            rmq_conn.close()
