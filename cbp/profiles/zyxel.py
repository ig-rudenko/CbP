from datetime import datetime
import os
import ftplib
from cbp.core import logs
import sys

debug_level = 0
'''
                    Уровень отладки:
        0 - не производит отладочный вывод. 
        1 - производит умеренное количество результатов отладки, обычно одна строка на запрос. 
        2 - каждая строка, отправленная и полученная по управляющему соединению.
'''


def elog(info, ip, name):
    logs.error_log.error("%s-> %s: %s" % (ip.ljust(15, '-'), name, info))


def get_configuration(ip, device: dict):
    with ftplib.FTP(ip) as ftp:
        ftp.set_debuglevel(debug_level)  # Уровень отладки
        ftp.set_pasv(False)  # Отключение пассивного режима (ОБЯЗАТЕЛЬНО!)
        try:
            ftp.login(user=device['login'], passwd=device['password'])
            cfg = []
            res = ftp.retrlines('RETR config-0', cfg.append)     # Запись конфигурации в переменную
            if '226' not in res:
                elog("Ошибка обращения к файлу конфигурации", ip, device['name'])
                return False
            cfg = '\n'.join(cfg)      # Объединяем в строку
            return cfg

        except ftplib.all_errors as error:
            elog(error, ip, device['name'])
            return None


def backup(ip, device_name, login: str, password: str, backup_group: str):
    timed = str(datetime.now())[0:10]  # yyyy-mm-dd
    with ftplib.FTP(ip) as ftp:
        ftp.set_debuglevel(debug_level)  # Уровень отладки
        ftp.set_pasv(False)  # Отключение пассивного режима (ОБЯЗАТЕЛЬНО!)
        if not os.path.exists(f'{backup_dir}/{backup_group}/{device_name.strip()}/'):
            os.makedirs(f'{backup_dir}/{backup_group}/{device_name.strip()}/')
        file_copy = f'{backup_dir}/{backup_group}/{device_name.strip()}/{timed}-config-0'
        try:
            ftp.login(user=login, passwd=password)
            with open(file_copy, 'wb') as fp:
                res = ftp.retrbinary(f'RETR config-0', fp.write)
                if '226' not in res:
                    elog("Backup FAILED!", ip, device_name)
                    if os.path.isfile(file_copy):
                        os.remove(file_copy)
                    return False

        except ftplib.all_errors as error:
            elog(error, ip, device_name)
            if os.path.isfile(file_copy):
                os.remove(file_copy)
            return False

    return True
