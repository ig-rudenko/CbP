from datetime import datetime
import re
import ftplib
import os

import pexpect

from cbp.core import logs


def elog(info, devices_ip, name):
    """
    Функция логирования.
    Аргументы: текст ошибки(str), ip платы(str), имя платы(str).
    """
    logs.error_log.error("%s-> %s: %s" % (devices_ip.ljust(15, '-'), name, info))


def get_configuration(session, device: dict) -> str:
    try:
        session.sendline('show system config')
        saved_config = ''
        while True:
            m = session.expect(
                [
                    r"Press any key to continue or Esc to stop scrolling\.",  # 0 - продолжаем
                    r'>\s*$'  # 1 - выход
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
    # Урезаем динамическую информацию
    cut1 = saved_config.find('Basic System data')
    cut2 = saved_config.find('IP routing-running')
    cut3 = saved_config.find('Bridge status:')
    cut4 = saved_config.find('Mactable for all interfaces:')
    cut5 = saved_config.find('VLANs registered in system:')
    cut6 = saved_config.find('bridge poll load')
    cut7 = saved_config.find('calculated discarding probabilities')
    cut8 = saved_config.find('Status and summary statistic DHCP RA:')
    cut9 = saved_config.find('Opt82 and statistics for each interface:')
    cut10 = saved_config.find('Status and summary statistic of PPPoE IA:')
    cut11 = saved_config.find('Show PPPoE specific information for each interface:')
    cut12 = saved_config.find('mBAN>')
    saved_config = saved_config[cut1:cut2] + saved_config[cut3:cut4] + saved_config[cut5:cut6] + \
                   saved_config[cut7:cut8] + saved_config[cut9:cut10] + saved_config[cut11:cut12]
    return saved_config


def ftp_download(start_path: str, local_path: str, ftp, device_name: str, device_ip: str) -> bool:
    """
    Функция построения дерева директорий и скачивания всех файлов в них.
    Аргументы: начальный путь на ftp(str), начальный локальный путь для записи(str).

    :param start_path: текущий путь на удаленном устройстве
    :param local_path: путь на удаленном сервере
    :param ftp: текущая сессия FTP
    :param device_name: имя устройства
    :param device_ip: IP адрес устройства
    """

    try:
        ftp.cwd(start_path)     # Переходим в папку
    except Exception as exc:
        elog("Ошибка при переходе в директорию " + start_path + ': ' + str(exc), device_ip, device_name)
        return False
    ls = []     # Список файлов в папке
    ftp.dir(ls.append)
    status = True   # Отсутствие ошибок при загрузки
    for line in ls:
        if line.startswith('d') and not line.endswith('.'):  # Если обнаружили папку
            folder = re.search(r'\S*$', line).group(0)  # Имя папки
            try:
                if not os.path.exists(f"{local_path}/{folder}"):    # Если нет локальной папки с таким именем
                    os.mkdir(f"{local_path}/{folder}")
                print(device_name + '    найдена папка ' + f"{start_path}/{folder}")
                # Рекурсия - передаем найденную папку в функцию
                status = ftp_download(f"{start_path}/{folder}", f"{local_path}/{folder}", ftp, device_name, device_ip)
            except Exception as exc:
                elog('Ошибка создания директории ' + folder + ': ' + str(exc), device_ip, device_name)
                return False
        if line.startswith('-'):    # Если найден файл
            file = re.search(r'\S*$', line).group(0)    # Имя файла
            print(device_name + '    найден файл ' + f"{start_path}/{file}")
            try:
                with open(local_path + '/' + file, 'wb') as local_file:  # Создаем/открываем файл в бинарном режиме
                    ftp.retrbinary('RETR ' + file, local_file.write)    # Скачиваем файл
            except Exception as exc:
                elog('Ошибка при скачивании файла ' + f"{start_path}/{file}" + ': ' + str(exc), device_ip, device_name)
                return False
    return status


def backup(device_ip: str, device_name: str, user: str, password: str, backup_group: str) -> bool:
    try:
        with ftplib.FTP(device_ip) as ftp:
            ftp.login(user=user, passwd=password)
            ftp.cwd('/tffs')
            now = datetime.now().strftime("%d-%m-%Y")
            my_folders = re.findall(r'M[A-Z,0-9]*', ' '.join(ftp.nlst()))
            for my_folder in my_folders:
                print(device_name + '    найдена М папка ' + my_folder)
                # папка для хранения файлов конфигурации
                local_path = f'{backup_dir}/{backup_group}/{device_name}/{now}/{my_folder}'
                if not os.path.exists(local_path):
                    os.makedirs(local_path)  # Создаем, если нет
                # Скачиваем все из данной папки
                return ftp_download(f'/tffs/{my_folder}', local_path, ftp, device_name, device_ip)
    except Exception as exc:
        elog('Ошибка FTP: ' + str(exc), device_ip, device_name)
        return False


