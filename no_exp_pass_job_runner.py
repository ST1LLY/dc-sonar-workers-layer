"""
The listener of wait_no_exp_pass_checking queue.
Having received a message from the wait_no_exp_pass_checking queue, it performs getting the information of
no expired passwords accounts for the specific domain and returns it to the info_no_exp_pass_checking queue.

Author:
    Konstantin S. (https://github.com/ST1LLY)
"""
import json
import os
import sys
from typing import Any

import pika

import modules.support_functions as sup_f
from enviroment import APP_CONFIG
from enviroment import RMQ_CONFIG, LOGS_DIR, LOG_CONFIG
from modules.ad_interface import ADInterface
from modules.aes_cipher import AESCipher

filename = os.path.basename(__file__).split('.')[0]
logger = sup_f.init_custome_logger(
    os.path.join(LOGS_DIR, f'{filename}.log'),
    os.path.join(LOGS_DIR, f'{filename}_error.log'),
    logging_level=LOG_CONFIG['level'],
)


def rmq_callback(current_ch: Any, method: Any, _: Any, body: Any) -> None:
    """
    The performer of the received message from the queue
    """
    rmq_c = None
    msg = {}
    try:
        logger.info('Working on a msg')
        msg = json.loads(body.decode('utf-8'))
        logger.info('msg: %s', msg)

        rmq_c = pika.BlockingConnection(pika.ConnectionParameters(**RMQ_CONFIG))
        no_exp_pass_info_ch = rmq_c.channel()
        no_exp_pass_info_ch.queue_declare(queue='info_no_exp_pass_checking', durable=True)
        no_exp_pass_info_ch.basic_publish(
            exchange='',
            routing_key='info_no_exp_pass_checking',
            body=sup_f.dict_to_json_bytes(
                {
                    'domain_pk': msg['pk'],
                    'domain_name': msg['fields']['name'],
                    'status': 'PERFORMING',
                    'error_desc': '',
                    'users': [],
                }
            ),
            properties=pika.BasicProperties(
                delivery_mode=2,  # make message persistent
            ),
        )

        ad_interface = ADInterface(
            msg['fields']['hostname'],
            msg['fields']['base_dn'],
            msg['fields']['user_dn'],
            AESCipher(APP_CONFIG['aes_256_key']).decrypt(msg['fields']['user_password']),
        )
        users = tuple(
            {'sam_acc_name': user[1]['sAMAccountName'][0].decode('utf-8', errors='replace')}
            for user in ad_interface.get_no_exp_pass_users()
        )

        no_exp_pass_info_ch.basic_publish(
            exchange='',
            routing_key='info_no_exp_pass_checking',
            body=sup_f.dict_to_json_bytes(
                {
                    'domain_pk': msg['pk'],
                    'domain_name': msg['fields']['name'],
                    'status': 'FINISHED',
                    'error_desc': '',
                    'users': users,
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
            no_exp_pass_info_ch = rmq_c.channel()
            no_exp_pass_info_ch.queue_declare(queue='info_no_exp_pass_checking', durable=True)
            no_exp_pass_info_ch.basic_publish(
                exchange='',
                routing_key='info_no_exp_pass_checking',
                body=sup_f.dict_to_json_bytes(
                    {
                        'domain_pk': msg['pk'],
                        'domain_name': msg['fields']['name'],
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
        current_ch.basic_ack(delivery_tag=method.delivery_tag)


if __name__ == '__main__':

    rmq_conn = None   # pylint: disable=invalid-name
    try:
        rmq_conn = pika.BlockingConnection(pika.ConnectionParameters(**RMQ_CONFIG))
        no_exp_pass_wait_ch = rmq_conn.channel()
        no_exp_pass_wait_ch.queue_declare(queue='wait_no_exp_pass_checking', durable=True)
        no_exp_pass_wait_ch.basic_consume(queue='wait_no_exp_pass_checking', on_message_callback=rmq_callback)
        no_exp_pass_wait_ch.start_consuming()
    except Exception:
        logger.error('Error', exc_info=sys.exc_info())
    finally:
        if rmq_conn is not None:
            rmq_conn.close()
