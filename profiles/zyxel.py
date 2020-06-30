#! /usr/bin/env python
# -*- coding: utf-8 -*-

from datetime import datetime
import os
from re import findall
from diff_config import diff_config
import ftplib
import logs

debug_level = 0
'''
                    Уровень отладки:
        0 - не производит отладочный вывод. 
        1 - производит умеренное количество результатов отладки, обычно одна строка на запрос. 
        2 - каждая строка, отправленная и полученная по управляющему соединению.
'''
def elog(info, ip, name):
    logs.error_log.error("%s-> %s: %s" % (ip.ljust(15, '-'), name, info))


def zyxel(ip, name):
    with ftplib.FTP(ip) as ftp:
        ftp.set_debuglevel(debug_level)  # Уровень отладки
        ftp.set_pasv(False)  # Отключение пассивного режима (ОБЯЗАТЕЛЬНО!)
        timed = str(datetime.now())[0:10]
        file_copy = '/srv/config_mirror/dsl/'+name.strip()+'/'+timed+'config-0'
        file_origin = 'config-0'
        try:
            ftp.login(user='eolin', passwd='rootsev')
            cfg = []
            res = ftp.retrlines('RETR'+file_origin, cfg.append)     # Запись конфигурации в переменную
            if not findall(r'226', res):
                elog("Ошибка обращения к файлу конфигурации", ip, name)
                return 0
            cfg = ''.join(cfg)
            diff_result = diff_config(name, cfg, 'dsl')  # Вызов функции сравнения конф-ий

            if diff_result:  # Если файлы различаются
                with open(file_copy, 'w') as fp:
                    res = ftp.retrlines('RETR' + file_origin, fp.write)
                    if not findall(r'226', res):
                        elog("Backup FAILED!", ip, name)
                        if os.path.isfile(file_copy):
                            os.remove(file_copy)
        except ftplib.all_errors as error:
            elog(error, ip, name)
            if os.path.isfile(file_copy):
                os.remove(file_copy)

