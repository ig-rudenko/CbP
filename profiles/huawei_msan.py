from datetime import datetime
from re import sub
from configparser import ConfigParser
from core import logs
import sys
import os

start_time = datetime.now()

conf = ConfigParser()
conf.read(f'{sys.path[0]}/cbp.conf')
backup_server_ip = conf.get('Main', 'backup_server_ip')     # IP адрес сервера бэкапов
backup_dir = conf.get('Path', 'backup_dir')                 # Полный путь к папке  бэкапов
if not os.path.exists(backup_dir):
    os.makedirs(backup_dir)

def elog(info, ip, name):
    """функция логгирования"""
    logs.error_log.error("%s-> %s: %s" % (ip.ljust(15, '-'), name, info))


def get_configuration(telnet_session):
    telnet_session.sendline('enable')
    telnet_session.sendline('config')
    telnet_session.sendline('scroll 100')   # Максимальное кол-во отображаемых строк
    telnet_session.sendline('display saved-configuration')
    telnet_session.expect('display saved-configuration')
    saved_config = ''
    while True:
        m = telnet_session.expect(
            [
                r"---- More \( Press \'Q\' to break \) ----",   # 0 - продолжаем
                r'\(config\)#'                                  # 1 - конец
            ]
        )
        saved_config += telnet_session.before.decode('utf-8')
        if m == 0:
            telnet_session.sendline(' ')
        else:
            break
    saved_config.replace('[37D                                     [37D', '').strip()
    saved_config = sub(r'\[Saving time: \d+-\d+-\d+ \d+:\d+:\d+\+\d+:\d+\]', ' ', saved_config)
    return saved_config


def backup(telnet_session, device_ip: str, device_name: str, backup_group: str) -> bool:
    telnet_session.sendline('\n')
    priority = telnet_session.expect(
        [
            r'\(config\)#',  # 0 - режим редактирования конфигурации
            r'\S#',          # 1 - привилегированный режим
            '>'              # 2 - пользовательский режим
        ]
    )
    if priority == 2:
        telnet_session.sendline('enable')
        telnet_session.sendline('config')
    if priority == 1:
        telnet_session.sendline('config')

    timed = str(datetime.now())[0:10]   # yyyy-mm-dd
    if not os.path.exists(f'{backup_dir}/{backup_group}/{device_name}'):
        os.makedirs(f'{backup_dir}/{backup_group}/{device_name}')
    telnet_session.sendline(
        f"backup configuration ftp {backup_server_ip} {backup_group}/{device_name}/{timed}-data.dat"
    )
    telnet_session.sendline('y')
    bcode = telnet_session.expect(
        [
            'Backing up files is successful',                       # 0
            'Failure cause: The path does not',                     # 1
            'The file with the same name exists on FTP server',     # 2
            'Backing up files fail'                                 # 3
        ]
    )
    if bcode == 1:
        elog(f"Путь ftp://{backup_group}/{device_name}/ не существует", device_ip, device_name)
    elif bcode == 2:
        elog(f"Файл {timed}-data.dat уже существет в директории: {backup_dir}/{backup_group}/{device_name}/",
             device_ip, device_name)
    elif bcode == 3:
        elog(f"Backup FAILED :(", device_ip, device_name)
    telnet_session.sendline('quit')
    telnet_session.sendline('y')

    return True if bcode == 0 else False
