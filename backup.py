#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from concurrent.futures import ThreadPoolExecutor
import subprocess
from datetime import datetime
import sys
from cbp.core import logs
from configparser import ConfigParser
from cbp.core.database import DataBase
from cbp.core.dc import DeviceConnect

start_time = datetime.now()
conf = ConfigParser()
conf.read(f'{sys.path[0]}/cbp.conf')                    # Файл конфигурации
backup_dir = conf.get('Path', 'backup_dir').replace('~', sys.path[0])  # Папка сохранения бэкапов
thread_count = int(conf.get('Main', 'thread_count'))    # Количество потоков


def get_backup_device(ip, device_name, vendor, protocol, login, password, privilege_mode_password, backup_group) -> int:
    if not ip:
        return 1
    ip_check = subprocess.run(['ping', '-c', '3', '-n', ip], stdout=subprocess.DEVNULL)
    # Проверка на доступность: 0 - доступен, 1 и 2 - недоступен
    if ip_check.returncode == 0:
        session = DeviceConnect(ip, device_name)
        session.connect(login, password, privilege_mode_password, protocol=protocol)
        session.get_saved_configuration()
        print(session.configuration_str)
        if session.config_diff():
            print(f'starting backup {device_name} ({ip})')
            session.backup_configuration(backup_group)

    elif ip_check.returncode == 1:
        logs.info_log.info(f"Оборудование недоступно: {device_name} ({ip})")
    elif ip_check.returncode == 2:
        logs.info_log.info(f"Неправильный ip адрес: {device_name} ({ip})")


def backup_start():
    db = DataBase()
    devices_list = db.get_table('cbp_equipment')
    auth_groups = db.get_table('cbp_authgroup')
    backup_groups = db.get_table('cbp_backupgroup')

    if not devices_list:
        logs.critical_log.critical(f'База оборудования пуста!')
    with ThreadPoolExecutor(max_workers=thread_count) as executor:  # Управление потоками
        for device in devices_list:
            ip = device[1]
            device_name = device[2]
            vendor = device[3]
            protocol = device[4]
            auth_group_id = device[5]
            backup_group_id = device[6]

            for a_g in auth_groups:
                if a_g[0] == auth_group_id:
                    login = a_g[2]
                    password = a_g[3]
                    priv_password = a_g[4]

            for b_g in backup_groups:
                if b_g[0] == backup_group_id:
                    backup_group = b_g[1]

            print(
                ip,
                device_name,
                vendor,
                protocol,
                login,
                password,
                priv_password,
                backup_group
            )
            # executor.submit(
            #     get_backup_device,  # Функция
            #     ip,
            #     device_name,
            #     vendor,
            #     protocol,
            #     login,
            #     password,
            #     priv_password,
            #     backup_group
            # )


if __name__ == '__main__':
    backup_start()

    logs.info_log.info(f"Общее время выполнения скрипта: {str(datetime.now() - start_time)}")
