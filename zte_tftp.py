#!/usr/bin/env python
# -*- coding: utf-8 -*-

import telnetlib
import time
import getpass
import keyring
import shutil
from re import match
from re import findall
from diff_config import diff_config
from datetime import datetime
from keyrings.alt.file import PlaintextKeyring
import os.path


# ------------------------------------ФУНКЦИЯ ЗАГРУЗКИ ПО TFTP------------------------------------------------
def upload():
    send_tftp = str('tftp 10.20.0.14 upload ' + file_name + '\n').encode('ascii')  # Передача по tftp
    t.write(send_tftp)
    output = str(t.read_until(b'uploaded', timeout=5))
    print(output)
    print('upload')
    if bool(findall(r'bytes uploaded', output)) == True:

        delete_file = str('remove ' + file_name + '\n').encode('ascii')  # Удалить файл после передачи
        t.write(delete_file)
        t.read_until(b'[Yes|No]:', timeout=1)
        t.write(b'y\n')
        output = str(t.read_until(b'done !', timeout=2))
        print(output)
        if bool(findall(r'done !', output)) != True:
            file.write('| ' + str(datetime.now())[0:19] + ' | ' + "{:15}".format(
                devices_ip) + ' | ' + name + ' |  Дубликат ' + file_name + ' файла конфигурации на коммутаторе не был удален!\n')

        dir_in = '/srv/tftp/' + file_name
        if os.path.exists(dir_in):
            dir_out = '/srv/config_mirror/asw/' + name.strip() + '/' + timed + 'startcfg.txt'
            # print(dir_in, dir_out)
            shutil.move(dir_in, dir_out)
            if os.path.exists(dir_out):
                file.write('| ' + str(datetime.now())[0:19] + ' | ' + "{:15}".format(
                    devices_ip) + ' | ' + name + ' | Конфигурация успешно скопирована и перенесена! \n')
            else:
                file.write('| ' + str(datetime.now())[0:19] + ' | ' + "{:15}".format(
                    devices_ip) + ' | ' + name + ' | Файл конфигурации не был перенесен и находится в: ' + dir_in + '! \n')
        else:
            file.write('| ' + str(datetime.now())[0:19] + ' | ' + "{:15}".format(
                devices_ip) + ' | ' + name + ' |  Файл конфигурации не был загружен!\n')
    else:
        file.write('| ' + str(datetime.now())[0:19] + ' | ' + "{:15}".format(
            devices_ip) + ' | ' + name + ' |  Ошибка отправки файла конфигурации!\n')

timed=str(datetime.now())[0:10]

def zte(devices_ip, name, tftp):
    '''
    Функция обработки файлов конфигурации
    коммутаторов доступа ZTE
    '''
    user='NOC'
    password = 'oncenoc2020!@#' #keyring.get_password('asw', user)
    user = user.encode('ascii')
    password = password.encode('ascii')

    # -------------------------------------------НАЧАЛО-------------------------------------------------
    with telnetlib.Telnet(devices_ip) as t:
        with open('/srv/svi/log/zte.log', 'a') as file:  # открываем логи

            output = str(t.read_until(b'login:', timeout=2))
            if bool(findall(r'log', output)) == True:
                t.write(user + b'\n')
            else:
                file.write('| ' + str(datetime.now())[0:19] + ' | ' + "{:15}".format(devices_ip) + ' | ' + name + ' | Таймаут превышен\n')  # ошибка ввода логина
                return 0

            output = str(t.read_until(b'password:', timeout=2))
            if bool(findall(r'password:', output)) == True:
                t.write(password + b'\n')
            else:
                file.write('| ' + str(datetime.now())[0:19] + ' | ' + "{:15}".format(devices_ip) + ' | ' + name + ' | Таймаут превышен \n')  # ошибка ввода пароля

            output = str(t.read_until(b'login-authentication failure!', timeout=3))
                                # Неверный логин или пароль
            if bool(findall(r'login-authentication failure!', output)) == True:
                file.write('| ' + str(datetime.now())[0:19] + ' | ' + "{:15}".format(devices_ip) + ' | ' + name + ' | Неверный логин или пароль \n')
                return 0


            t.write(b'enable\n')
            t.read_until(b'password:')
            t.write(b'sevaccess\n')
            output = str(t.read_until(b'(cfg)#', timeout=2))
            if bool(findall(r'\(cfg\)#', output)) != True:
                file.write('| ' + str(datetime.now())[0:19] + ' | ' + "{:15}".format(devices_ip) + ' | ' + name + ' | Неверный пароль от привилегированного пользователя \n')
                t.write(b'exit\n')
            t.write(b'show start-config\n')
            time.sleep(0.4)
            cfg=[]
            # wii - После преобразования с битовой строки остаются символы:
            wii = '\x08 \x08\x08 \x08\x08 \x08\x08 \x08\x08 \x08\x08 \x08\x08 \x08\x08 \x08\x08 \x08\x08 \x08\x08 \x08\x08 \x08\x08 \x08\x08 \x08\x08 \x08\x08 \x08\x08 \x08\x08 \x08\x08 \x08'

            # ---------------------------ЛИСТИНГ КОНФИГУРАЦИИ--------------------------------
            while True:
                y = t.read_until(b'break -----', timeout=0.5).decode('ascii')
                if bool(y) == True and bool(match('\s', y)) == False:
                    t.write(b' ')
                    cfg.append(y.replace('----- more ----- Press Q or Ctrl+C to break -----', '').replace(wii, '').replace('\r', ''))
                else:
                    break
            cfg = ''.join(cfg)

            # --------------------------Сравнение конфигураций-------------------------------
            trfl = diff_config(name, cfg)
            t.write(b'config tffs\n')
            if trfl == True:

                # ------------------------------РАБОТА С TFTP----------------------------------
                if tftp == True:

                    file_name = str(name.strip() + '.txt')
                    command_to_copy = str('copy startcfg.txt ' + file_name + '\n').encode('ascii') # Копирование файла на коммутаторе
                    t.write(command_to_copy)
                    output = str(t.read_until(b'bytes copied', timeout=3))
                    #print(output)
                    if bool(findall(r'bytes copied', output)) == True:
                        upload()                        # ЗАГРУЗКА ПО TFTP

                    elif bool(findall(r'File exists', output)) == True:
                        delete_file = str('remove ' + file_name + '\n').encode('ascii')  # Удалить файл после передачи
                        t.write(delete_file)
                        t.read_until(b'[Yes|No]:', timeout=1)
                        t.write(b'y\n')
                        t.read_until(b'done !', timeout=2)
                        print('deleted')
                        t.write(command_to_copy)
                        t.read_until(b'bytes copied', timeout=3)
                        upload()                        # ЗАГРУЗКА ПО TFTP
                    else:
                        file.write('| ' + str(datetime.now())[0:19] + ' | ' + "{:15}".format(devices_ip) + ' | ' + name + ' | Файл конфигурации с именем \'startcfg.txt\' не найден! \n')


                # -------------------------------ОТПРАВКА ПО FTP----------------------------------
                elif tftp == False:

                    dir_name = str('ftp 10.20.0.14 asw/' + name.strip() + '/' + timed + 'startrun.dat upload /cfg/startrun.dat username svi password q7TP6GwCS%c3\n\n').encode('ascii')
                    t.write(dir_name)
                    time.sleep(5)
                    output = str(t.read_very_eager().decode('ascii'))
                    if bool(findall(r'uploaded', output)) == True:
                        file.write('| ' + str(datetime.now())[0:19] + ' | ' + "{:15}".format(devices_ip) + ' | ' + name + ' | Backup успешен! \n')
                    elif bool(findall(r'([данные])', output)) == True:
                        file.write('| ' + str(datetime.now())[0:19] + ' | ' + "{:15}".format(devices_ip) + ' | ' + name + ' | Некорректные данные аутентификации \n')
                    elif bool(findall(r'No such file or directory (0x2)', output)) == True:
                        file.write('| ' + str(datetime.now())[0:19] + ' | ' + "{:15}".format(devices_ip) + ' | ' + name + ' | Неправильный путь на стороне коммутатора \n')
                    elif bool(findall(r'No such file or directory', output)) == True:
                        file.write('| ' + str(datetime.now())[0:19] + ' | ' + "{:15}".format(devices_ip) + ' | ' + name + ' | Неправильный путь на стороне сервера \n')
                    else:
                        file.write('| ' + str(datetime.now())[0:19] + ' | ' + "{:15}".format(devices_ip) + ' | ' + name + ' | Время ожидания истекло \n')

                else:
                    file.write('| ' + str(datetime.now())[0:19] + ' | ' + "{:15}".format(devices_ip) + ' | ' + name + ' | Неправильно задан ключ \'noftp\' \n')
            else:
                file.write('| ' + str(datetime.now())[0:19] + ' | ' + "{:15}".format(devices_ip) + ' | ' + name + ' | Конфигурация за последние сутки не изменилась \n')


            t.write(b'exit\n')
            t.write(b'exit\n')
            t.write(b'exit\n')

