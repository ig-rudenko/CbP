from datetime import datetime
from re import sub
from configparser import ConfigParser
import pexpect
import shutil
from cbp.core import logs
import sys
import os

start_time = datetime.now()

conf = ConfigParser()
conf.read(f'{sys.path[0]}/cbp.conf')
backup_server_ip = conf.get('Main', 'backup_server_ip')  # IP адрес сервера бэкапов
backup_dir = conf.get('Path', 'backup_dir').replace('~', sys.path[0])                 # Полный путь к папке  бэкапов
if not os.path.exists(backup_dir):
    os.makedirs(backup_dir)
    shutil.chown(backup_dir, '')


def elog(info, ip, name):
    """функция логгирования"""
    logs.error_log.error("%s-> %s: %s" % (ip.ljust(15, '-'), name, info))


def get_configuration(session, device: dict):
    try:
        session.sendline('enable')
        session.sendline('config')
        session.sendline('scroll 100')   # Максимальное кол-во отображаемых строк
        session.sendline('display saved-configuration')
        session.expect('display saved-configuration')
        saved_config = ''
        while True:
            m = session.expect(
                [
                    r"---- More \( Press \'Q\' to break \) ----",   # 0 - продолжаем
                    r'\(config\)#'                                  # 1 - конец
                ]
            )
            saved_config += session.before.decode('utf-8')
            if m == 0:
                session.sendline(' ')
            else:
                break
    except (pexpect.EOF, pexpect.TIMEOUT) as error:
        elog(error, device['ip'], device['name'])
        return ''

    saved_config.replace('[37D                                     [37D', '').strip()
    saved_config = sub(r'\[Saving time: \d+-\d+-\d+ \d+:\d+:\d+\+\d+:\d+\]', ' ', saved_config)
    return saved_config


def backup(session, device: dict, backup_dir: str) -> bool:
    session.sendline('\n')
    priority = session.expect(
        [
            r'\(config\)#',  # 0 - режим редактирования конфигурации
            r'\S#',          # 1 - привилегированный режим
            '>'              # 2 - пользовательский режим
        ]
    )
    if priority == 2:
        session.sendline('enable')
        session.sendline('config')
    if priority == 1:
        session.sendline('config')

    timed = str(datetime.now())[0:10]   # yyyy-mm-dd

    session.sendline(
        f"backup configuration ftp {backup_server_ip} backup_dir/{timed}-data.dat"
    )
    print('sent:', f"backup configuration ftp {backup_server_ip} {backup_group}/{device_name}/{timed}-data.dat")
    session.sendline('y')
    bcode = session.expect(
        [
            'Backing up files is successful',                       # 0
            'Failure cause: The path does not',                     # 1
            'The file with the same name exists on FTP server',     # 2
            'Backing up files fail'                                 # 3
        ],
        timeout=300
    )
    print('return', bcode)
    if bcode == 1:
        elog(f"Путь ftp://{backup_group}/{device_name}/ не существует", device_ip, device_name)
    elif bcode == 2:
        elog(f"Файл {timed}-data.dat уже существет в директории: {backup_dir}/{backup_group}/{device_name}/",
             device_ip, device_name)
    elif bcode == 3:
        session.expect(r'Failure cause:')
        session.expect(r'\S+\(config\)#$')
        failure_cause = session.before.decode('utf-8').strip().replace('\n', '')
        elog(f"Backup FAILED! Failure cause: {failure_cause}", device_ip, device_name)
    session.sendline('quit')
    session.sendline('y')

    return True if not bcode else False
