import logging
from configparser import ConfigParser
import sys
import os

conf = ConfigParser()
conf.read(f'{sys.path[0]}/cbp.conf')
logs_path = conf.get('Path', 'logs_dir')
if not os.path.exists(logs_path):
    os.makedirs(logs_path)

# ------------------------------------CRITICAL ЛОГ------------------------------------------
critical_log = logging.getLogger('critical')
critical_log.setLevel(logging.CRITICAL)
log_critical_file = logging.FileHandler(f"{logs_path}/critical.log")
formatter = logging.Formatter('%(asctime)s | %(module)s -> %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
log_critical_file.setFormatter(formatter)
critical_log.addHandler(log_critical_file)
# -------------------------------------INFO ЛОГ------------------------------------------
info_log = logging.getLogger('info')
info_log.setLevel(logging.INFO)
log_info_file = logging.FileHandler(f"{logs_path}/info.log")
formatter = logging.Formatter('%(asctime)s | %(module)s -> %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
log_info_file.setFormatter(formatter)
info_log.addHandler(log_info_file)
# -------------------------------------ERROR ЛОГ-----------------------------------------
error_log = logging.getLogger('error')
error_log.setLevel(logging.ERROR)
log_error_file = logging.FileHandler(f"{logs_path}/error.log")
formatter = logging.Formatter('%(asctime)s | %(module)s@%(message)s', datefmt='%Y-%m-%d %H:%M:%S')
log_error_file.setFormatter(formatter)
error_log.addHandler(log_error_file)
