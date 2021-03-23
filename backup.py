#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from concurrent.futures import ThreadPoolExecutor
import subprocess
from datetime import datetime
import sys
from core import logs
from configparser import ConfigParser
from core.database import DataBase
from core.tc import TelnetConnect

start_time = datetime.now()
conf = ConfigParser()
conf.read(f'{sys.path[0]}/cbp.conf')                    # Файл конфигурации
backup_dir = conf.get('Path', 'backup_dir')             # Папка сохранения бэкапов
db_path = conf.get('Path', 'database')                  # База оборудования
auth_file = conf.get('Path', 'auth_file')               # Файл авторизации
thread_count = int(conf.get('Main', 'thread_count'))    # Количество потоков


def get_backup_device(ip: str, device_name: str, auth_group: str):
    ip_check = subprocess.run(['ping', '-c', '3', '-n', ip], stdout=subprocess.DEVNULL)
    # Проверка на доступность: 0 - доступен, 1 и 2 - недоступен
    if ip_check.returncode == 0:
        session = TelnetConnect(ip, device_name)
        session.set_authentication(mode='group', auth_file=auth_file, auth_group=auth_group)
        session.connect()
        session.get_saved_configuration()
        if session.config_diff():
            print(f'starting backup {device_name} ({ip})')
            session.backup_configuration()

    elif ip_check.returncode == 1:
        logs.info_log.info(f"Оборудование недоступно: {device_name} ({ip})")
    elif ip_check.returncode == 2:
        logs.info_log.info(f"Неправильный ip адрес: {device_name} ({ip})")


def backup_start():
    devices_list = DataBase().get_table()
    if not devices_list:
        logs.critical_log.critical(f'База оборудования пуста! {db_path}')
    with ThreadPoolExecutor(max_workers=thread_count) as executor:  # Управление потоками
        for device in devices_list:
            ip = device[0]
            device_name = device[1]
            auth_group = device[3]
            executor.submit(get_backup_device, ip, device_name, auth_group)

# subprocess.run(['chown', '-R', 'proftpd:nogroup', '/srv/config_mirror/'])
# subprocess.run(['chmod', '-R', '600', '/srv/config_mirror/'])
# subprocess.run('find /srv/config_mirror/ -type d -exec chmod 700 {} \;', shell=True)


if __name__ == '__main__':
    backup_start()

    logs.info_log.info(f"Общее время выполнения скрипта: {str(datetime.now() - start_time)}")

