from datetime import datetime
from configparser import ConfigParser
import pexpect
from cbp.core import logs
import sys
import os
import shutil

start_time = datetime.now()

cfg = ConfigParser()
cfg.read(f'{sys.path[0]}/cbp.conf')
backup_dir = cfg.get('Path', 'backup_dir')      # Директория сохранения файлов конфигураций
if not os.path.exists(backup_dir):
    os.makedirs(backup_dir)
tftp_directory = cfg.get('TFTP', 'directory')   # Директория TFTP
if not os.path.exists(tftp_directory):
    os.makedirs(tftp_directory)
ftp_user = cfg.get('FTP', 'username')
ftp_password = cfg.get('FTP', 'password')
backup_server_ip = cfg.get('Main', 'backup_server_ip')

timed = str(datetime.now())[0:10]   # текущая дата 'yyyy-mm-dd'


def elog(info, ip, name):
    """функция логгирования"""
    logs.error_log.error("%s-> %s: %s" % (ip.ljust(15, '-'), name, info))


def get_configuration(telnet_session):
    telnet_session.sendline('show startup-config')
    telnet_session.expect(r'Using \d+ out of \d+ bytes')
    saved_config = ''
    while True:
        m = telnet_session.expect(
            [
                r" --More-- ",  # 0 - продолжаем
                r'\S+#$'        # 1 - конец
            ],
            timeout=2
        )
        saved_config += telnet_session.before.decode('utf-8').replace('        ', '')
        if m == 0:
            telnet_session.send(' ')
        else:
            break
    return saved_config


def backup(telnet_session, device_name, device_ip, backup_group):
    telnet_session.sendline('copy running-config tftp:')
    telnet_session.expect(r'Address or name of remote host \[\]\?')
    telnet_session.sendline(backup_server_ip)
    telnet_session.expect(r'Destination filename \S+\?')
    telnet_session.sendline(f'{timed}_{device_name}')
    backup_status = telnet_session.expect(
        [
            'bytes copied',                 # 0 - удачно
            'No such file or directory',    # 1 - нет директории
            pexpect.TIMEOUT                 # 2
        ]
    )

    if backup_status == 1:
        elog(f'Нет директории tftp://{backup_server_ip}/{timed}_{device_name}', device_ip, device_name)
    if backup_status == 2:
        elog(f'Таймаут при обращении к tftp://{backup_server_ip}', device_ip, device_name)
    uploaded_file = f'{tftp_directory}/{timed}_{device_name}'
    if os.path.exists(uploaded_file):
        next_file = f'{backup_dir}/{backup_group}/{device_name.strip()}/{timed}'
        shutil.move(uploaded_file, next_file)   # перемещаем файл конфигурации в папку <backup_dir>
        if not os.path.exists(next_file):
            elog(f"Файл конфигурации не был перенесен и находится в {uploaded_file}", device_ip, device_name)
        return True
    else:
        elog("Файл конфигурации не был загружен!", device_ip, device_name)
    return False
