"""
Shared environment constants for app
"""
import os
import modules.support_functions as sup_f

# Get this file full path
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))

# To initialize paths to directories
LOGS_DIR = os.path.join(ROOT_DIR, 'logs')

TEMP_DIR = os.path.join(ROOT_DIR, 'temp')

# The path to app config file
CONFIG_PATH = os.path.join(ROOT_DIR, 'configs', 'settings.conf')
APP_CONFIG = sup_f.get_config(CONFIG_PATH, 'APP')
RMQ_CONFIG = sup_f.get_config(CONFIG_PATH, 'RMQ')
NTLM_SCRUT_CONFIG = sup_f.get_config(CONFIG_PATH, 'NTLM_SCRUT')
LOG_CONFIG = sup_f.get_config(CONFIG_PATH, 'LOG')
DB_CONFIG = sup_f.get_config(CONFIG_PATH, 'DB')
DATABASE_URI = f"postgresql+psycopg2://{DB_CONFIG['user']}:{DB_CONFIG['pass']}@" \
               f"{DB_CONFIG['host']}:{DB_CONFIG['port']}/back_workers_db"
