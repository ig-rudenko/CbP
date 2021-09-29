from datetime import datetime
import pexpect
from cbp.core import logs
import os
import shutil


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


def backup(telnet, device_name, device_ip, backup_group):
    backup_server_ip = os.environ.get('LOCAL_HOST_IP')
    timed = str(datetime.now().strftime('%d-%b-%Y_%H:%M')).replace(':', '_')  # 27-Sep-2021_09_40 (Пример)
    telnet.sendline('copy running-config tftp:')
    telnet.expect(r'Address or name of remote host \[\]\?')
    telnet.sendline(backup_server_ip)
    telnet.expect(r'Destination filename \S+\?')
    telnet.sendline(f'{timed}_{device_name}')
    backup_status = telnet.expect(
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
    uploaded_file = f'/home/ftp/{timed}_{device_name}'
    if os.path.exists(uploaded_file):
        next_file = f'/home/ftp/{backup_group}/{device_name.strip()}/{timed}'
        shutil.move(uploaded_file, next_file)   # перемещаем файл конфигурации в папку <backup_dir>
        if not os.path.exists(next_file):
            elog(f"Файл конфигурации не был перенесен и находится в {uploaded_file}", device_ip, device_name)
        return True
    else:
        elog("Файл конфигурации не был загружен!", device_ip, device_name)
    return False
