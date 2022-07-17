"""
The module contains jobs run by sheduler

Author:
    Konstantin S. (https://github.com/ST1LLY)

TODO: refactor to be more concise
"""
import os
import re
import sys
import time

import pika
from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import create_engine
from sqlalchemy import select, delete
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import sessionmaker

import modules.support_functions as sup_f
from enviroment import LOGS_DIR, DATABASE_URI, LOG_CONFIG, NTLM_SCRUT_CONFIG, RMQ_CONFIG
from models import NTLMDumpSession, NTLMBruteSession, NTLMDumpHash
from modules.ntlm_scrut_interface import NTLMScrutInterface

filename = os.path.basename(__file__).split('.')[0]
logger = sup_f.init_custome_logger(
    os.path.join(LOGS_DIR, f'{filename}.log'),
    os.path.join(LOGS_DIR, f'{filename}_error.log'),
    logging_level=LOG_CONFIG['level'],
)


def ntlm_dump_status_checker() -> None:
    """
    Gets the information of run dump NTLM-hashes processes and performs it
    """
    logger.info('run ntlm_dump_status_checker')
    rmq_conn = None
    try:
        engine = create_engine(DATABASE_URI)
        engine_session_maker = sessionmaker(engine)

        # Get all run dumping sessions records from DB
        with engine_session_maker() as session:
            ntlm_dump_sessions = session.execute(select(NTLMDumpSession)).scalars().all()

        if not ntlm_dump_sessions:
            logger.info('ntlm dump sessions have not found')
            return

        ntlm_scrut_i = NTLMScrutInterface(**NTLM_SCRUT_CONFIG)
        rmq_conn = pika.BlockingConnection(pika.ConnectionParameters(**RMQ_CONFIG))
        channel = rmq_conn.channel()
        channel.queue_declare(queue='info_dumping_ntlm', durable=True)
        channel.queue_declare(queue='info_bruting_ntlm', durable=True)

        # Perform per dump session record
        for ntlm_dump_session in ntlm_dump_sessions:
            try:
                logger.info('ntlm_dump_session: %s', ntlm_dump_session)
                # Get status of process by session name
                ntlm_dump_status = ntlm_scrut_i.dump_ntlm_status(ntlm_dump_session.session_name)
                logger.info('ntlm_dump_status: %s', ntlm_dump_status)

                # dump process is running
                if ntlm_dump_status['status'] == 'running':
                    # send info about running
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

                # dump process is finished
                if ntlm_dump_status['status'] == 'finished':
                    # send info about finishing
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
                    # del record about this dump session
                    with engine_session_maker() as session:
                        session.delete(ntlm_dump_session)
                        session.commit()

                    # try to run brute session
                    try:
                        # run brute session
                        data = ntlm_scrut_i.brute_ntlm_run(ntlm_dump_status['hashes_file_path'])
                        # set records about run bruting session to DB
                        with engine_session_maker() as session:
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
                        # send info about run bruting session
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
                        # download file with dumped NTLM hashes and get its path
                        hashes_file_path = ntlm_scrut_i.download_ntlm_hashes(ntlm_dump_status['hashes_file_path'])
                        logger.info('hashes_file_path: %s', hashes_file_path)
                        with open(hashes_file_path, 'r', encoding='UTF-8') as file:
                            with engine_session_maker() as session:

                                # delete previous dumped NTLM hashes from this domain in DB
                                stmt = delete(NTLMDumpHash).where(
                                    NTLMDumpHash.domain_pk == ntlm_dump_session.domain_pk
                                )
                                session.execute(stmt)
                                # set current dumped NTLM hashes for this domain to DB
                                while line := file.readline():
                                    try:
                                        line_data = line.split(':')
                                        record = NTLMDumpHash(
                                            domain_pk=ntlm_dump_session.domain_pk,
                                            user_login=line_data[0],
                                            user_ntlm_hash=f'{line_data[2]}:{line_data[3]}',
                                        )
                                        session.add(record)
                                    except Exception:
                                        logger.error('Error paring line %s', line, exc_info=sys.exc_info())
                                        continue
                                logger.info('session.commit()')
                                session.commit()
                        os.remove(hashes_file_path)
                        continue

                    except Exception as exc:
                        logger.error('Error', exc_info=sys.exc_info())
                        channel.basic_publish(
                            exchange='',
                            routing_key='info_dumping_ntlm',
                            body=sup_f.dict_to_json_bytes(
                                {
                                    'domain_pk': ntlm_dump_session.domain_pk,
                                    'domain_name': ntlm_dump_session.domain_name,
                                    'status': 'ERROR',
                                    'error_desc': sup_f.get_error_text(exc),
                                }
                            ),
                            properties=pika.BasicProperties(
                                delivery_mode=2,  # make message persistent
                            ),
                        )
                        continue

                # dumping session finished with error
                if ntlm_dump_status['status'] == 'error':
                    logger.error('Error: %s', ntlm_dump_status['err_desc'])
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
                    with engine_session_maker() as session:
                        session.delete(ntlm_dump_session)
                        session.commit()
                    continue

                # dumping session was interrupted
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
                    with engine_session_maker() as session:
                        session.delete(ntlm_dump_session)
                        session.commit()
                    continue

                raise Exception(f"Unknown ntlm_dump_status['status']: {ntlm_dump_status['status']}")
            except Exception as exc:
                logger.error('Error', exc_info=sys.exc_info())
                channel.basic_publish(
                    exchange='',
                    routing_key='info_dumping_ntlm',
                    body=sup_f.dict_to_json_bytes(
                        {
                            'domain_pk': ntlm_dump_session.domain_pk,
                            'domain_name': ntlm_dump_session.domain_name,
                            'status': 'ERROR',
                            'error_desc': sup_f.get_error_text(exc),
                        }
                    ),
                    properties=pika.BasicProperties(
                        delivery_mode=2,  # make message persistent
                    ),
                )

                with engine_session_maker() as session:
                    session.delete(ntlm_dump_session)
                    session.commit()

    except Exception:

        logger.error('Error', exc_info=sys.exc_info())
    finally:
        if rmq_conn is not None:
            rmq_conn.close()


def ntlm_brute_status_checker() -> None:
    """
    Gets the information of run dump NTLM-hashes processes and performs it
    """
    logger.info('run ntlm_brute_status_checker')
    rmq_conn = None
    try:
        engine = create_engine(DATABASE_URI)
        engine_session_maker = sessionmaker(engine)

        # Get all run bruting sessions records from DB
        with engine_session_maker() as session:
            ntlm_brute_sessions = session.execute(select(NTLMBruteSession)).scalars().all()

        if not ntlm_brute_sessions:
            logger.info('NTLMBruteSession have not found')
            return

        ntlm_scrut_i = NTLMScrutInterface(**NTLM_SCRUT_CONFIG)
        rmq_conn = pika.BlockingConnection(pika.ConnectionParameters(**RMQ_CONFIG))
        channel = rmq_conn.channel()
        channel.queue_declare(queue='info_dumping_ntlm', durable=True)
        channel.queue_declare(queue='info_bruting_ntlm', durable=True)

        # Perform per brute session record
        for ntlm_brute_session in ntlm_brute_sessions:
            try:
                logger.info('ntlm_brute_session: %s', ntlm_brute_session)
                # Get status of process by session name
                ntlm_brute_info = ntlm_scrut_i.brute_ntlm_info(ntlm_brute_session.session_name)
                logger.info('ntlm_brute_info: %s', ntlm_brute_info)

                bruting_progress = 0
                status = 'Running'
                # Run process is found
                if ntlm_brute_info['state'] == 'found':
                    for status_el in ntlm_brute_info['status_data']:
                        # Get info of progress
                        if status_el['title'] == 'Progress':
                            if result := re.findall(r'(\d+)\.\d+%', status_el['value']):
                                bruting_progress = int(result[0])
                                break

                    # Get info of status
                    for status_el in ntlm_brute_info['status_data']:
                        if status_el['title'] == 'Status':
                            status = status_el['value']
                            break

                    # Process is running
                    if status == 'Running':
                        # Send updated info
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

                    # Process is finished
                    if status == 'Exhausted':
                        # Try to get bruted credentials
                        creds_bruted = ntlm_scrut_i.creds_bruted(ntlm_brute_session.session_name)

                        # Bruted creaentials are found
                        if creds_bruted['status'] == 'found':
                            # Send updated info
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
                        # Bruted creaentials are not found
                        elif creds_bruted['status'] == 'not_found':
                            # Send error
                            channel.basic_publish(
                                exchange='',
                                routing_key='info_bruting_ntlm',
                                body=sup_f.dict_to_json_bytes(
                                    {
                                        'domain_pk': ntlm_brute_session.domain_pk,
                                        'domain_name': ntlm_brute_session.domain_name,
                                        'bruting_progress': 0,
                                        'status': 'ERROR',
                                        'error_desc': f'Creds of finished session: {ntlm_brute_session.session_name} '
                                        f'have not found',
                                    }
                                ),
                                properties=pika.BasicProperties(
                                    delivery_mode=2,  # make message persistent
                                ),
                            )

                        else:
                            raise Exception(f"Unknown creds_bruted['status']: {creds_bruted['status']}")

                        # Delete the record of the bruting session from DB
                        with engine_session_maker() as session:
                            session.delete(ntlm_brute_session)
                            session.commit()

                        continue

                    raise Exception(f'Unknown status: {status}')
                # Run process is not found
                if ntlm_brute_info['state'] == 'not_found':
                    # Try to re-run the session from the dump file if exists
                    re_run_info = ntlm_scrut_i.brute_ntlm_re_run(ntlm_brute_session.session_name)
                    # Trying to re-run the session failed
                    if re_run_info['status'] == 'not_found':
                        # Send error
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
                        with engine_session_maker() as session:
                            session.delete(ntlm_brute_session)
                            session.commit()
                        continue
                    # Trying to re-run the session succeeded
                    if re_run_info['status'] == 'success':
                        # It will be rechecked during futher running
                        continue
                    raise Exception(f"Unknown re_run_info['status']: {re_run_info['status']}")

            except Exception as exc:
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
                            'error_desc': sup_f.get_error_text(exc),
                        }
                    ),
                    properties=pika.BasicProperties(
                        delivery_mode=2,  # make message persistent
                    ),
                )

                with engine_session_maker() as session:
                    session.delete(ntlm_brute_session)
                    session.commit()

    except Exception:
        logger.error('Error', exc_info=sys.exc_info())
    finally:
        if rmq_conn is not None:
            rmq_conn.close()


if __name__ == '__main__':
    logger.info('Starting')
    scheduler = None   # pylint: disable=invalid-name
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
