import os
import sys

from apscheduler.schedulers.background import BackgroundScheduler
import pika
import modules.support_functions as sup_f
from enviroment import LOGS_DIR, DATABASE_URI, LOG_CONFIG, NTLM_SCRUT_CONFIG, RMQ_CONFIG
from models import NTLMDumpSession, NTLMBruteSession
import time
from sqlalchemy import select
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from modules.ntlm_scrut_interface import NTLMScrutInterface
from sqlalchemy.dialects.postgresql import insert
import re

filename = os.path.basename(__file__).split('.')[0]
logger = sup_f.init_custome_logger(
    os.path.join(LOGS_DIR, f'{filename}.log'),
    os.path.join(LOGS_DIR, f'{filename}_error.log'),
    logging_level=LOG_CONFIG['level'],
)


def ntlm_dump_status_checker() -> None:
    logger.info('run ntlm_dump_status_checker')
    rmq_conn = None
    try:
        engine = create_engine(DATABASE_URI)
        Session = sessionmaker(engine)
        with Session() as session:
            ntlm_dump_sessions = session.execute(select(NTLMDumpSession)).scalars().all()

        if not ntlm_dump_sessions:
            logger.info('ntlm dump sessions have not found')
            return

        ntlm_scrut_i = NTLMScrutInterface(**NTLM_SCRUT_CONFIG)
        rmq_conn = pika.BlockingConnection(pika.ConnectionParameters(**RMQ_CONFIG))
        channel = rmq_conn.channel()
        channel.queue_declare(queue='info_dumping_ntlm', durable=True)
        channel.queue_declare(queue='info_bruting_ntlm', durable=True)

        for ntlm_dump_session in ntlm_dump_sessions:
            try:
                logger.info(f'ntlm_dump_session: {ntlm_dump_session}')
                ntlm_dump_status = ntlm_scrut_i.dump_ntlm_status(ntlm_dump_session.session_name)
                logger.info(f'ntlm_dump_status: {ntlm_dump_status}')

                if ntlm_dump_status['status'] == 'running':
                    channel.basic_publish(
                        exchange='',
                        routing_key='info_dumping_ntlm',
                        body=sup_f.dict_to_json_bytes(
                            {
                                'domain_pk': ntlm_dump_session.domain_pk,
                                'domain_name': ntlm_dump_session.domain_name,
                                'status': 'PERFORMING',
                                'error_desc': '',
                            }
                        ),
                        properties=pika.BasicProperties(
                            delivery_mode=2,  # make message persistent
                        ),
                    )
                    continue

                if ntlm_dump_status['status'] == 'finished':
                    channel.basic_publish(
                        exchange='',
                        routing_key='info_dumping_ntlm',
                        body=sup_f.dict_to_json_bytes(
                            {
                                'domain_pk': ntlm_dump_session.domain_pk,
                                'domain_name': ntlm_dump_session.domain_name,
                                'status': 'FINISHED',
                                'error_desc': '',
                            }
                        ),
                        properties=pika.BasicProperties(
                            delivery_mode=2,  # make message persistent
                        ),
                    )
                    with Session() as session:
                        session.delete(ntlm_dump_session)
                        session.commit()
                    ntlm_scrut_i.technical_clean_dump(ntlm_dump_session.session_name)

                    try:
                        data = ntlm_scrut_i.brute_ntlm_run(ntlm_dump_status['hashes_file_path'])
                        with Session() as session:
                            stmt = insert(NTLMBruteSession).values(
                                session_name=data['session_name'],
                                domain_name=ntlm_dump_session.domain_name,
                                domain_pk=ntlm_dump_session.domain_pk,
                            )
                            stmt = stmt.on_conflict_do_update(
                                constraint='ntlm_brute_session_domain_pk_key',
                                set_={'session_name': data['session_name']},
                            )
                            session.execute(stmt)
                            session.commit()

                        channel.basic_publish(
                            exchange='',
                            routing_key='info_bruting_ntlm',
                            body=sup_f.dict_to_json_bytes(
                                {
                                    'domain_pk': ntlm_dump_session.domain_pk,
                                    'domain_name': ntlm_dump_session.domain_name,
                                    'bruting_progress': 0,
                                    'status': 'PERFORMING',
                                    'error_desc': '',
                                }
                            ),
                            properties=pika.BasicProperties(
                                delivery_mode=2,  # make message persistent
                            ),
                        )
                        continue
                    except Exception as e:
                        logger.error('Error', exc_info=sys.exc_info())
                        channel.basic_publish(
                            exchange='',
                            routing_key='info_dumping_ntlm',
                            body=sup_f.dict_to_json_bytes(
                                {
                                    'domain_pk': ntlm_dump_session.domain_pk,
                                    'domain_name': ntlm_dump_session.domain_name,
                                    'status': 'ERROR',
                                    'error_desc': sup_f.get_error_text(e),
                                }
                            ),
                            properties=pika.BasicProperties(
                                delivery_mode=2,  # make message persistent
                            ),
                        )
                        continue

                if ntlm_dump_status['status'] == 'error':
                    logger.error(f"Error: {ntlm_dump_status['err_desc']}")
                    channel.basic_publish(
                        exchange='',
                        routing_key='info_dumping_ntlm',
                        body=sup_f.dict_to_json_bytes(
                            {
                                'domain_pk': ntlm_dump_session.domain_pk,
                                'domain_name': ntlm_dump_session.domain_name,
                                'status': 'ERROR',
                                'error_desc': ntlm_dump_status['err_desc'],
                            }
                        ),
                        properties=pika.BasicProperties(
                            delivery_mode=2,  # make message persistent
                        ),
                    )

                if ntlm_dump_status['status'] == 'interrupted':
                    channel.basic_publish(
                        exchange='',
                        routing_key='info_dumping_ntlm',
                        body=sup_f.dict_to_json_bytes(
                            {
                                'domain_pk': ntlm_dump_session.domain_pk,
                                'domain_name': ntlm_dump_session.domain_name,
                                'status': 'ERROR',
                                'error_desc': 'Dumping procces has been interrupted',
                            }
                        ),
                        properties=pika.BasicProperties(
                            delivery_mode=2,  # make message persistent
                        ),
                    )

                with Session() as session:
                    session.delete(ntlm_dump_session)
                    session.commit()
                ntlm_scrut_i.technical_clean_dump(ntlm_dump_session.session_name)

                raise Exception(f"Unknown ntlm_dump_status['status']: {ntlm_dump_status['status']}")
            except Exception as e:
                logger.error('Error', exc_info=sys.exc_info())
                channel.basic_publish(
                    exchange='',
                    routing_key='info_dumping_ntlm',
                    body=sup_f.dict_to_json_bytes(
                        {
                            'domain_pk': ntlm_dump_session.domain_pk,
                            'domain_name': ntlm_dump_session.domain_name,
                            'status': 'ERROR',
                            'error_desc': str(e),
                        }
                    ),
                    properties=pika.BasicProperties(
                        delivery_mode=2,  # make message persistent
                    ),
                )

                with Session() as session:
                    session.delete(ntlm_dump_session)
                    session.commit()
                ntlm_scrut_i.technical_clean_dump(ntlm_dump_session.session_name)

    except Exception:

        logger.error('Error', exc_info=sys.exc_info())
    finally:
        if rmq_conn is not None:
            rmq_conn.close()


def ntlm_brute_status_checker() -> None:
    logger.info('run ntlm_brute_status_checker')
    rmq_conn = None
    try:
        engine = create_engine(DATABASE_URI)
        Session = sessionmaker(engine)
        with Session() as session:
            ntlm_brute_sessions = session.execute(select(NTLMBruteSession)).scalars().all()

        if not ntlm_brute_sessions:
            logger.info('NTLMBruteSession have not found')
            return

        ntlm_scrut_i = NTLMScrutInterface(**NTLM_SCRUT_CONFIG)
        rmq_conn = pika.BlockingConnection(pika.ConnectionParameters(**RMQ_CONFIG))
        channel = rmq_conn.channel()
        channel.queue_declare(queue='info_dumping_ntlm', durable=True)
        channel.queue_declare(queue='info_bruting_ntlm', durable=True)

        for ntlm_brute_session in ntlm_brute_sessions:
            try:
                logger.info(f'ntlm_brute_session: {ntlm_brute_session}')
                ntlm_brute_info = ntlm_scrut_i.brute_ntlm_info(ntlm_brute_session.session_name)
                logger.info(f'ntlm_brute_info: {ntlm_brute_info}')
                bruting_progress = 0
                status = 'Running'
                if ntlm_brute_info['state'] == 'found':
                    for status_el in ntlm_brute_info['status_data']:
                        if status_el['title'] == 'Progress':
                            if result := re.findall(r'(\d+)\.\d+%', status_el['value']):
                                bruting_progress = int(result[0])
                                break

                    for status_el in ntlm_brute_info['status_data']:
                        if status_el['title'] == 'Status':
                            status = status_el['value']
                            break

                    if status == 'Running':
                        channel.basic_publish(
                            exchange='',
                            routing_key='info_bruting_ntlm',
                            body=sup_f.dict_to_json_bytes(
                                {
                                    'domain_pk': ntlm_brute_session.domain_pk,
                                    'domain_name': ntlm_brute_session.domain_name,
                                    'bruting_progress': bruting_progress,
                                    'status': 'PERFORMING',
                                    'error_desc': '',
                                }
                            ),
                            properties=pika.BasicProperties(
                                delivery_mode=2,  # make message persistent
                            ),
                        )
                        continue

                    if status == 'Exhausted':

                        creds_bruted = ntlm_scrut_i.creds_bruted(ntlm_brute_session.session_name)
                        if creds_bruted['status'] == 'found':
                            channel.basic_publish(
                                exchange='',
                                routing_key='info_bruting_ntlm',
                                body=sup_f.dict_to_json_bytes(
                                    {
                                        'domain_pk': ntlm_brute_session.domain_pk,
                                        'domain_name': ntlm_brute_session.domain_name,
                                        'bruting_progress': 100,
                                        'status': 'FINISHED',
                                        'error_desc': '',
                                        'creds': creds_bruted['creds'],
                                    }
                                ),
                                properties=pika.BasicProperties(
                                    delivery_mode=2,  # make message persistent
                                ),
                            )
                        elif creds_bruted['status'] == 'not_found':
                            channel.basic_publish(
                                exchange='',
                                routing_key='info_bruting_ntlm',
                                body=sup_f.dict_to_json_bytes(
                                    {
                                        'domain_pk': ntlm_brute_session.domain_pk,
                                        'domain_name': ntlm_brute_session.domain_name,
                                        'bruting_progress': 0,
                                        'status': 'ERROR',
                                        'error_desc': f'Creds of finished session: {ntlm_brute_session.session_name} have not found',
                                    }
                                ),
                                properties=pika.BasicProperties(
                                    delivery_mode=2,  # make message persistent
                                ),
                            )

                        else:
                            raise Exception(f"Unknown creds_bruted['status']: {creds_bruted['status']}")

                        with Session() as session:
                            session.delete(ntlm_brute_session)
                            session.commit()
                        ntlm_scrut_i.technical_clean_brute(ntlm_brute_session.session_name)

                        continue

                    raise Exception(f'Unknown status: {status}')
                if ntlm_brute_info['state'] == 'not_found':
                    re_run_info = ntlm_scrut_i.brute_ntlm_re_run(ntlm_brute_session.session_name)
                    if re_run_info['status'] == 'not_found':
                        channel.basic_publish(
                            exchange='',
                            routing_key='info_bruting_ntlm',
                            body=sup_f.dict_to_json_bytes(
                                {
                                    'domain_pk': ntlm_brute_session.domain_pk,
                                    'domain_name': ntlm_brute_session.domain_name,
                                    'bruting_progress': 0,
                                    'status': 'ERROR',
                                    'error_desc': f'Restore file for {ntlm_brute_session.session_name} has not found',
                                }
                            ),
                            properties=pika.BasicProperties(
                                delivery_mode=2,  # make message persistent
                            ),
                        )
                        with Session() as session:
                            session.delete(ntlm_brute_session)
                            session.commit()
                        ntlm_scrut_i.technical_clean_brute(ntlm_brute_session.session_name)
                        continue
                    if re_run_info['status'] == 'success':
                        # It will be rechecked during futher running
                        continue
                    raise Exception(f"Unknown re_run_info['status']: {re_run_info['status']}")

            except Exception as e:
                logger.error('Error', exc_info=sys.exc_info())
                channel.basic_publish(
                    exchange='',
                    routing_key='info_bruting_ntlm',
                    body=sup_f.dict_to_json_bytes(
                        {
                            'domain_pk': ntlm_brute_session.domain_pk,
                            'domain_name': ntlm_brute_session.domain_name,
                            'bruting_progress': 0,
                            'status': 'ERROR',
                            'error_desc': str(e),
                        }
                    ),
                    properties=pika.BasicProperties(
                        delivery_mode=2,  # make message persistent
                    ),
                )

                with Session() as session:
                    session.delete(ntlm_brute_session)
                    session.commit()
                ntlm_scrut_i.technical_clean_brute(ntlm_brute_session.session_name)

    except Exception:
        logger.error('Error', exc_info=sys.exc_info())
    finally:
        if rmq_conn is not None:
            rmq_conn.close()


if __name__ == '__main__':
    logger.info('Starting')
    scheduler = None
    try:
        scheduler = BackgroundScheduler()
        scheduler.add_jobstore('sqlalchemy', url=DATABASE_URI)
        scheduler.add_job(ntlm_dump_status_checker, 'interval', seconds=60, max_instances=1)
        scheduler.add_job(ntlm_brute_status_checker, 'interval', seconds=60, max_instances=1)
        scheduler.start()
        while True:
            time.sleep(5)
    except (KeyboardInterrupt, SystemExit):
        pass
    except Exception as e:
        logger.error('Error', exc_info=sys.exc_info())
    finally:
        if scheduler is not None:
            scheduler.shutdown()
