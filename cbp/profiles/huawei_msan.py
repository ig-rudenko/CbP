from datetime import datetime
from re import sub
import pexpect
import shutil
from cbp.core import logs
import os


def elog(info, ip, name):
    """функция логгирования"""
    logs.error_log.error(f'{name} ({ip}): {info}')


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


def backup(session, device: dict, backup_group: str, backup_server: dict) -> str:
    session.sendline('\n')
    priority = session.expect(
        [
            r'\(config\)#',   # 0 - режим редактирования конфигурации
            r'\S+#',          # 1 - привилегированный режим
            '>'               # 2 - пользовательский режим
        ]
    )
    if priority == 2:
        session.sendline('enable')
        session.sendline('config')
    if priority == 1:
        session.sendline('config')

    timed = str(datetime.now().strftime('%d-%b-%Y_%H:%M')).replace(':', '_')   # 27-Sep-2021_09_40 (Пример)
    # Проверяем папку для сохранения
    if not os.path.exists(f'/home/ftp/{backup_group}/{device["name"]}'):
        print(f'create: /home/ftp/{backup_group}/{device["name"]}')
        os.makedirs(f'/home/ftp/{backup_group}/{device["name"]}')
    # Устанавливаем права
    shutil.chown(f'/home/ftp/{backup_group}/{device["name"]}', 'cbp_ftp', 'root')

    # Создаем ftp пользователя для передачи файла конфигурации
    session.sendline('ftp set')
    session.sendline(backup_server["login"])
    session.sendline(backup_server['password'])
    session.sendline(
        f"backup configuration ftp {backup_server['ip']} {backup_group}/{device['name']}/{timed}-data.dat"
    )
    print('sent:', f"backup configuration ftp {backup_server['ip']} {backup_group}/{device['name']}/{timed}-data.dat")
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
        elog(f"Путь ftp://{backup_server['ip']}/{backup_group}/{device['name']}/ не существует", device['ip'], device['name'])
    elif bcode == 2:
        elog(f"Файл {timed}-data.dat уже существет в директории: ftp://{backup_server['ip']}/{backup_group}/{backup_group}/{device['name']}/",
             device['ip'], device['name'])
    elif bcode == 3:
        session.expect(r'Failure cause:')
        session.expect(r'\S+\(config\)#$')
        failure_cause = session.before.decode('utf-8').strip().replace('\n', '').replace('\r', '')  # Причина ошибки
        elog(f"Backup FAILED! Failure cause: {failure_cause}", device['ip'], device['name'])
    session.sendline('quit')
    session.sendline('y')

    # Возвращаем путь к файлу конфигурации, если бэкап успешен, либо данный файл уже хранится по указанному пути
    return f"/home/ftp/{backup_group}/{device['name']}/{timed}-data.dat" if not bcode or bcode == 2 else ''
