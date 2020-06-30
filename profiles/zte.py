#!/usr/bin/env python
# -*- coding: utf-8 -*-

import telnetlib
import time
import shutil
import os.path
from re import match, findall
from diff_config import diff_config
from datetime import datetime
import logs

timed = str(datetime.now())[0:10]   # текущая дата 'yyyy-mm-dd'
# функция логгирования
def elog(info, ip, name):
    logs.error_log.error("%s-> %s: %s" % (ip.ljust(15, '-'), name, info))


# ------------------------------------ФУНКЦИЯ ЗАГРУЗКИ ПО TFTP------------------------------------------------
def upload(t, zte_name, name, ip):
    send_tftp = str('tftp 10.20.0.14 upload ' + zte_name + '.txt \n').encode('ascii')  # Передача по tftp
    send_tftp
    t.write(send_tftp)
    output = str(t.read_until(b'uploaded', timeout=5))
    if bool(findall(r'bytes uploaded', output)):
        delete_file = str('remove ' + zte_name + '.txt\n').encode('ascii')  # Удалить файл после передачи
        t.write(delete_file)
        t.read_until(b'[Yes|No]:', timeout=1)
        t.write(b'y\n')
        output = str(t.read_until(b'done !', timeout=2))
        if not bool(findall(r'done !', output)):
            elog("Дубликат %s файла конфигурации на коммутаторе не был удален!" % (name), ip, name)
        dir_in = '/srv/tftp/' + zte_name + '.txt'
        if os.path.exists(dir_in):
            dir_out = '/srv/config_mirror/asw/' + name.strip() + '/' + timed + 'startcfg.txt'
            shutil.move(dir_in, dir_out)
            if os.path.exists(dir_out):
                elog("Конфигурация успешно скопирована и перенесена!", ip, name)
            else:
                elog("Файл конфигурации не был перенесен и находится в %s " % (dir_in), ip, name)
        else:
            elog("Файл конфигурации не был загружен!", ip, name)
    else:
        elog("Ошибка отправки файла конфигурации!", ip, name)


def zte(ip, name, tftp):
    '''
    Функция обработки файлов конфигурации
    коммутаторов доступа ZTE
    '''
    user = 'NOC'
    with open('/etc/svi_password.cfg', 'r') as f:
        master_password = f.readlines()
        for find_pass in master_password:
            if user in find_pass:
                 password=str(find_pass.split(' ')[1]).encode('ascii')
    find_name = findall('SVSL-(\d+)-(\S+)-\D{3}(\d)', name)
    zte_name = find_name[0][0] + find_name[0][1] + find_name[0][2]
    user = user.encode('ascii')
    # -------------------------------------------НАЧАЛО-------------------------------------------------
    with telnetlib.Telnet(ip) as t:
        output = str(t.read_until(b'login:', timeout=2))
        if bool(findall(r'log', output)):
            t.write(user + b'\n')
        else:
            elog("Таймаут превышен", ip, name)
            return 0
        output = str(t.read_until(b'password:', timeout=2))
        if bool(findall(r'password:', output)):
            t.write(password + b'\n')
        else:
            elog("Таймаут превышен", ip, name)
        output = str(t.read_until(b'login-authentication failure!', timeout=3))
        if bool(findall(r'login-authentication failure!', output)):
            elog("Неверный логин или пароль", ip, name)
            return 0
        t.write(b'enable\n')
        t.read_until(b'password:')
        t.write(b'sevaccess\n')
        output = str(t.read_until(b'(cfg)#', timeout=2))
        if not bool(findall(r'\(cfg\)#', output)):
            elog("Неверный пароль от привилегированного пользователя", ip, name)
            t.write(b'exit\n')
        t.write(b'show start-config\n')
        time.sleep(0.4)
        cfg=[]
        # wii - После преобразования с битовой строки остаются символы:
        wii = '\x08 \x08\x08 \x08\x08 \x08\x08 \x08\x08 \x08\x08 \x08\x08 \x08\x08 \x08\x08 \x08\x08 \x08\x08 \x08\x08 \x08\x08 \x08\x08 \x08\x08 \x08\x08 \x08\x08 \x08\x08 \x08\x08 \x08'
        # ---------------------------ЛИСТИНГ КОНФИГУРАЦИИ--------------------------------
        while True:
            y = t.read_until(b'break -----', timeout=0.5).decode('ascii')
            if bool(y) and not bool(match('\s', y)):
                t.write(b' ')
                cfg.append(y.replace('----- more ----- Press Q or Ctrl+C to break -----', '').replace(wii, '').replace('\r', ''))
            else:
                break
        cfg = ''.join(cfg)
        # --------------------------Сравнение конфигураций-------------------------------
        trfl = diff_config(name, cfg, 'asw')
        t.write(b'config tffs\n')
        if trfl:
            # ------------------------------РАБОТА С TFTP----------------------------------
            if tftp:
                command_to_copy = str('copy startcfg.txt  ' + zte_name + '.txt \n').encode('ascii') # Копирование файла на коммутаторе
                t.write(command_to_copy)
                time.sleep(1)
                output = str(t.read_until(b'bytes copied', timeout=3))
                if bool(findall(r'bytes copied', output)):
                    upload(t, zte_name, name, ip)                        # ЗАГРУЗКА ПО TFTP
                elif bool(findall(r'File exists', output)):
                    delete_file = str('remove ' + zte_name + '.txt \n').encode('ascii')  # Удалить файл после передачи
                    t.write(delete_file)
                    t.read_until(b'[Yes|No]:', timeout=1)
                    t.write(b'Yes\n')
                    t.write(command_to_copy)
                    t.read_until(b'bytes copied', timeout=3)
                    upload(t, zte_name, name, ip)
                else:
                    t.write(b'cd cfg\n')
                    time.sleep(1)
                    command_to_copy = str('copy startrun.dat  ' + zte_name + '.txt \n').encode('ascii') # Копирование файла на коммутаторе
                    t.write(command_to_copy)
                    time.sleep(3)
                    upload(t, zte_name, name, ip)
                    if ip != '172.30.0.73':
                        elog("Файл конфигурации с именем \'startcfg.txt/startrun.dat\' не найден.", ip, name)
            # -------------------------------ОТПРАВКА ПО FTP----------------------------------
            elif not tftp:
                dir_name = str('ftp 10.20.0.14 asw/' + name.strip() + '/' + timed + 'startrun.dat upload /cfg/startrun.dat username svi password q7TP6GwCS%c3\n\n').encode('ascii')
                t.write(dir_name)
                time.sleep(5)
                output = str(t.read_very_eager().decode('ascii'))
                if bool(findall(r'uploaded', output)):
                    pass
                elif bool(findall(r'([данные])', output)):
                    elog("Некорректные данные аутентификации", ip, name)
                elif bool(findall(r'No such file or directory (0x2)', output)):
                    elog("Неправильный путь на стороне коммутатора", ip, name)
                elif bool(findall(r'No such file or directory', output)):
                    elog("Неправильный путь на стороне сервера", ip, name)
                else:
                    elog("Время ожидания истекло", ip, name)
            else:
                elog("Неправильно задан ключ \'noftp\'", ip, name)
        t.write(b'exit\n')
        t.write(b'exit\n')
        t.write(b'exit\n')
        print(ip, ': Выполнено')
#zte('172.30.0.73', 'SVSL-961-Eroshenko9-ASW1', True)
