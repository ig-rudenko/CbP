#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
from concurrent.futures import ThreadPoolExecutor
import subprocess
from datetime import datetime
import sys
import ftplib
from cbp.core import logs
from configparser import ConfigParser
from cbp.core.database import DataBase
from cbp.core.dc import DeviceConnect

from pprint import pprint

start_time = datetime.now()
conf = ConfigParser()
conf.read(f'{sys.path[0]}/cbp.conf')  # Файл конфигурации
backup_dir = conf.get('Path', 'backup_dir').replace('~', sys.path[0])  # Папка сохранения бэкапов


def create_directory(directory: str):
    if not os.path.exists(directory):
        os.makedirs(directory)


# сbp_ftpd_server (запущенный в контейнере) является посредником между сетевым оборудованием и ftp сервером
# Конфигурация вначале клонируется на него, а затем дублируется на ftp сервер(а)
LOCAL_FTP_SERVER_STATUS = subprocess.run(
    ['ping', '-c', '1', '-n', 'cbp_ftpd_server'], stdout=subprocess.DEVNULL
)  # Проверяем, доступен ли cbp_ftpd_server 0 - доступен, 1 и 2 - недоступен

# Определяем все IP адреса машины, на которой запущен контейнер
# Передается в файле docker-compose
MASTER_HOST_IPS = os.environ.get('LOCAL_HOST_IPS')
# Необходимо, когда ftp сервер для бэкапов расположен на master host
# В таком случае процесс резервирования файла конфигурации будет остановлен на шаге загрузки с помощью cbp_ftpd_server
#   без дальнейшего, повторного, копирования на тот же ip адрес

LOCAL_HOST_BACKUP_IP = os.environ.get('LOCAL_HOST_BACKUP_IP')
LOCAL_FTP_USER_NAME = os.environ.get('LOCAL_FTP_USER_NAME')
LOCAL_FTP_USER_PASS = os.environ.get('LOCAL_FTP_USER_PASS')
LOCAL_FTP_USER_HOME = os.environ.get('LOCAL_FTP_USER_HOME')

if not LOCAL_FTP_USER_HOME:  # Если не была задана переменная окружения, для директории сохранения бэкапов
    os.environ['LOCAL_FTP_USER_HOME'] = '/backups'  # Задаём


def ftp_mkdir(ftp: ftplib.FTP, folder: str):
    try:
        ftp.mkd(folder)
    except ftplib.error_perm:
        pass


def ftp_send(ftp_server: dict, local_file_path: str, bg: str, dn: str):
    try:
        with ftplib.FTP(ftp_server['ip'], ftp_server['login'], ftp_server['password']) as ftp:
            ftp.cwd(ftp_server['workdir'])
            # Создаем папки
            ftp_mkdir(ftp, bg)
            ftp_mkdir(ftp, f'{bg}/{dn}')
            file_name = os.path.split(local_file_path)[1]

            # Загружаем локальный файл на ftp сервер
            with open(local_file_path, 'rb') as file:
                s = ftp.storbinary(f'STOR {bg}/{dn}/{file_name}', file, 1024)  # Записываем в файл
            return s
    except Exception as e:
        logs.critical_log.critical(f"FTP: {ftp_server['name']} ({ftp_server['ip']}) {e}")
        return e


def get_backup_device(ip, device_name, vendor, protocol, login, password, privilege_mode_password,
                      backup_group, ftp_servers: dict) -> int:
    if not ip:
        return 1
    dev_ip_check = subprocess.run(['ping', '-c', '3', '-n', ip], stdout=subprocess.DEVNULL)
    # Проверка на доступность: 0 - доступен, 1 и 2 - недоступен
    if dev_ip_check.returncode == 0:
        session = DeviceConnect(ip, device_name)
        session.connect(login, password, privilege_mode_password, protocol=protocol)
        pprint(session.device)
        session.get_saved_configuration()
        print(session.configuration_str)
        if session.config_diff():  # Если конфигурация отличается, то необходимо сделать бэкап
            print('конфигурация отличается')
            if LOCAL_FTP_USER_NAME and LOCAL_FTP_USER_PASS and LOCAL_FTP_USER_HOME and \
                    LOCAL_HOST_BACKUP_IP and not LOCAL_FTP_SERVER_STATUS:
                # Если запущен cbp_ftpd_server и указан ip адрес master host, а также имеются данные для подключения

                print('Запущен cbp_ftpd_server и указан ip адрес master host, а также имеются данные для подключения',
                      LOCAL_HOST_BACKUP_IP,
                      LOCAL_FTP_USER_NAME,
                      LOCAL_FTP_USER_PASS,
                      LOCAL_FTP_USER_HOME
                      )

                # Копируем конфигурацию на cbp_ftpd_server в директорию,
                # указанную в переменной окружения LOCAL_FTP_USER_HOME,
                # которая должна быть общей с директорией на cbp_ftpd_server

                # Создаем необходимые папки, если требуется
                if not os.path.exists(f'{LOCAL_FTP_USER_HOME}/{backup_group}/{device_name}'):
                    print('Создаем необходимые папки', f'{backup_group}/{device_name}')
                    with ftplib.FTP(LOCAL_HOST_BACKUP_IP, LOCAL_FTP_USER_NAME, LOCAL_FTP_USER_PASS) as ftp:
                        ftp_mkdir(ftp, backup_group)
                        ftp_mkdir(ftp, f'{backup_group}/{device_name}')

                # Делаем бэкап
                local_file_path = '/home/ftpuser' + session.backup_configuration(
                    backup_group=backup_group,
                    backup_server={
                        'ip': LOCAL_HOST_BACKUP_IP,
                        'login': LOCAL_FTP_USER_NAME,
                        'password': LOCAL_FTP_USER_PASS,
                        'workdir': '/'
                    }
                )

                print('local_file_path: ', local_file_path)

            else:  # Если не запущен cbp_ftpd_server или не указан ip адрес master host,
                # либо отсутствуют данные для подключения к cbp_ftpd_server
                local_file_path = ''  # Файл конфигурации не был скачан на master host

            # Смотрим, на какие ftp сервера необходимо отправить конфигурацию
            print('Смотрим, на какие ftp сервера необходимо отправить конфигурацию')
            for ftp_server in ftp_servers:
                print(ftp_server)
                if ftp_server['ip'] == LOCAL_HOST_BACKUP_IP and local_file_path:
                    print('Если файл конфигурации необходимо загрузить на master host и он уже был загружен ранее')
                    # Если файл конфигурации необходимо загрузить на master host и он уже был загружен ранее,
                    continue  # то пропускаем

                # Если файл конфигурации ИМЕЕТСЯ на master host, но его необходимо отправить на другой ftp
                elif ftp_server['ip'] != LOCAL_HOST_BACKUP_IP and local_file_path:
                    # Отправляем имеющийся файл на удаленный ftp сервер
                    ftp_send(ftp_server, local_file_path, backup_group, device_name)

                # Если файл конфигурации НЕ имеется на master host, то отправляем его на другой ftp
                elif not local_file_path:
                    print('Если файл конфигурации НЕ имеется на master host, то отправляем его на другой ftp')
                    # Создаем на FTP сервере необходимые папки
                    with ftplib.FTP(ftp_server['ip'], ftp_server['login'], ftp_server['password']) as ftp:
                        ftp.cwd(ftp_server['workdir'])  # Преходим в рабочую директорию
                        ftp_mkdir(ftp, backup_group)
                        ftp_mkdir(ftp, f'{backup_group}/{device_name}')

                    file_path = session.backup_configuration(
                        backup_group=backup_group,
                        backup_server=ftp_server
                    )
                    print(file_path)

        else:
            print(session.device['ip'], 'configuration not changed')

    elif dev_ip_check.returncode == 1:
        logs.info_log.info(f"Оборудование недоступно: {device_name} ({ip})")
    elif dev_ip_check.returncode == 2:
        logs.info_log.info(f"Неправильный ip адрес: {device_name} ({ip})")


def backup_start(available_backup_group: str = ''):
    db = DataBase()
    devices_list = db.get_table('cbp_equipment')
    auth_groups = db.get_table('cbp_authgroup')
    backup_groups = db.get_table('cbp_backupgroup')

    # Проверка созданных директорий
    for b in backup_groups:
        create_directory(f'{backup_dir}/{b[1]}')

    if not devices_list:
        logs.critical_log.critical(f'База оборудования пуста!')
    with ThreadPoolExecutor(max_workers=1) as executor:  # Управление потоками
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

            # Если необходимо бэкапить только определенную группу
            if available_backup_group and available_backup_group != backup_group:
                continue

            # Смотрим, какие ftp сервера привязаны к backup_group
            ftp_bg = db.get_table('cbp_backupgroup_ftp_server')  # Промежуточная таблица соответствий bg и ftp
            ftp_ids = []  # id подключенных FTP серверов
            for line in ftp_bg:
                if line[1] == backup_group_id:
                    ftp_ids.append(line[2])  # Добавляем id подключенного ftp сервера

            ftp_servers = [
                {
                    'id': line[0],
                    'ip': line[1],
                    'login': line[2],
                    'password': line[3],
                    'workdir': line[4],
                    'name': line[5]
                }
                for line in db.get_table('cbp_ftpgroup') if line[0] in ftp_ids
            ]
            print(ftp_servers)
            # Создаем директорию (если нет) для сохранения файла конфигурации
            create_directory(f'{backup_dir}/{backup_group}/{device_name}')

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
            executor.submit(
                get_backup_device,  # Функция
                ip,
                device_name,
                vendor,
                protocol,
                login,
                password,
                priv_password,
                backup_group,
                ftp_servers
            )


if __name__ == '__main__':
    backup_start(sys.argv[1] if len(sys.argv) == 2 else '')

    logs.info_log.info(f"Общее время выполнения скрипта: {str(datetime.now() - start_time)}")
