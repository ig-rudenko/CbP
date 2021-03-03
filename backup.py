from concurrent.futures import ThreadPoolExecutor
import subprocess
from datetime import datetime
import os
import sys
from control import logs
from configparser import ConfigParser
from control.database import DataBase
from control.tc import TelnetConnect

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
            if auth_group.upper() == 'MSAN':
                executor.submit(get_backup_device, ip, device_name, auth_group)


def login(ip, profile, name, tftp):
    """
    Функция проверяет доступность оборудования
    и наличие каталога под оборудование.
    После, отправляет имя устройства и его ip на profiles.py
    """
    ip_check = subprocess.run(['ping', '-c', '3', '-n', ip], stdout=subprocess.DEVNULL)
    # Проверка на доступность: 0 - доступен, 1 и 2 - недоступен

    if ip_check.returncode == 0:
        if profile == 'MSAN':
            if not os.path.exists(backup_dir + 'msan/' + name):
                os.mkdir(backup_dir + 'msan/' + name)
                os.chown(backup_dir + 'msan/' + name, 113, 65534)
            msan(ip, name)
        elif profile == 'ZTE':
            if not os.path.exists(backup_dir + 'asw/' + name):
                os.mkdir(backup_dir + 'asw/' + name)
                os.chown(backup_dir + 'asw/' + name, 113, 65534)
            zte(ip, name, tftp)
        elif profile == 'Iskratel_slot':
            if not os.path.exists(backup_dir + 'dsl/' + name):
                os.mkdir(backup_dir + 'dsl/' + name)
                os.chown(backup_dir + 'dsl/' + name, 113, 65534)
            iskratel_slot(ip, name)
        elif profile == 'Zyxel':
            if not os.path.exists(backup_dir + 'dsl/' + name):
                os.mkdir(backup_dir + 'dsl/' + name)
                os.chown(backup_dir + 'dsl/' + name, 113, 65534)
            zyxel(ip, name)
    elif ip_check.returncode == 1:  # Запись в логи
        logs.info_log.info("Оборудование недоступно: %s" % ip)
    elif ip_check.returncode == 2:
        logs.info_log.info("Неправильный ip адрес: %s" % ip)


def core():
    with open('/srv/svi/all_switch.txt', 'r') as main_file:  # Файл с данными об оборудовании
        try:
            with ThreadPoolExecutor(max_workers=30) as executor:  # Управление потоками
                main_file = main_file.readlines()
                for equipment in main_file:
                    cut = equipment.split(' ')
                    if len(cut) > 2 and '#' not in cut[0]:
                        ip = cut[0]
                        vendor = cut[1]
                        name = cut[2]
                        tftp = False
                        if len(cut) == 4 and '+' in cut[3]:
                            tftp = True
                        try:
                            executor.submit(login, ip, vendor, name.strip(), tftp)
                        except InvalidStateError as invalid_state:
                            logs.critical_log.critical('%s: Попытка вызова незавершенного потока. %s' % (invalid_state, ip))
                        except thread.BrokenThreadPool as sys_resource:
                            logs.critical_log.critical('%s: Не удалось инициализировать поток. %s' % (sys_resource, ip))
                        except CancelledError as stopped_thread:
                            logs.critical_log.critical('%s: Прерывание потока. %s' % (stopped_thread, ip))
                    elif not '#' in cut[0]:
                        logs.info_log.info('Неправильный синтаксис all_switch: %s' % cut)
        except KeyboardInterrupt:
            logs.critical_log.critical('Ручная остановка кода')



#
# core()
#
# subprocess.run(['chown', '-R', 'proftpd:nogroup', '/srv/config_mirror/'])
# subprocess.run(['chmod', '-R', '600', '/srv/config_mirror/'])
# subprocess.run('find /srv/config_mirror/ -type d -exec chmod 700 {} \;', shell=True)


if __name__ == '__main__':
    backup_start()

    logs.info_log.info("Общее время выполнения скрипта: %s" % str(datetime.now() - start_time))

