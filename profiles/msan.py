#! /usr/bin/env python
# -*- coding: utf-8 -*-

import telnetlib
from datetime import datetime
from re import findall, search
from diff_config import diff_config
import time
import logs
start_time=datetime.now()

# функция логгирования
def elog(info, ip, name):
    logs.error_log.error("%s-> %s: %s" % (ip.ljust(15, '-'), name, info))

def msan(ip, name):
    timed = str(datetime.now())[0:10]
    user = 'root'
    with open('/etc/svi_password.cfg', 'r') as f:
        master_password = f.readlines()
        for find_pass in master_password:
            if user in find_pass:
                password = str(find_pass.split(' ')[1]).encode('ascii')
                if len(find_pass.split(' ')) == 3:
                    password_two = str(find_pass.split(' ')[2].strip()).encode('ascii')
    en_user = user.encode('ascii')
    # ---------------------TELNET ПОДКЛЮЧЕНИЕ--------------------------
    with telnetlib.Telnet(ip) as t:
        time.sleep(1)
        output = str(t.read_until(b'User name:', timeout=1))
        if bool(findall(r'User name:', output)):
            t.write(en_user + b'\n')                # ввод логина
        elif bool(findall(r'Connection closed by foreign host', output)):
            elog("Превышен лимит подключений", ip, name)
            return 0
        else:
            elog("Ошибка telnet", ip, name)
            return 0
        output = str(t.read_until(b'User password:', timeout=1))
        if bool(findall(r'User password:', output)):
            t.write(password + b'\n')              # ввод пароля
        else:
            elog("Ошибка telnet", ip, name)
            return 0
        output = str(t.read_until(b'User name:', timeout=1))
        if bool(findall(r'User name:', output)):
            t.write(en_user + b'\n')                # ввод логина
            if bool(findall(r'Connection closed by foreign host', output)):
                elog("Превышен лимит подключений", ip, name)
                return 0
            output = str(t.read_until(b'User password:', timeout=1))
            if bool(findall(r'User password:', output)):
                t.write(password_two + b'\n')              # ввод пароля
            else:
                elog("Ошибка telnet", ip, name)
                return 0
            output = str(t.read_until(b'.', timeout=1))
        else:
            if bool(findall(r'Username or password invalid\.', output)):
                elog("Неправильный логин или пароль", ip, name)
                return 0
        if bool(findall(r'Reenter times have reached the upper limit\.', output)):
            elog("Данный пользователь уже зашел на оборудование", ip, name)
            return 0
        t.write(b'enable\n')
        t.write(b'config\n')
        t.write(b'scroll 100\n')
        t.write(b'display saved-configuration\n')
#        t.write(b'display config\n')
        x=t.read_until(b'display saved-configuration')
#        t.write(b'\n')
        cfg = []    # переменная для хранения конфигурации
    # Листинг конфигураций
        brk = False
        while True:
            check = t.read_until(b'to break ) ----', timeout=1).decode('ascii')
            if not brk:
                if bool(search(r'config.#', str(check))):
                    brk = True
                t.write(b' ')
                cfg.append(check.replace('---- More ( Press \'Q\' to break ) ----', '').replace('D                                     D', '').replace('\n', '').replace('\r', '').replace('\x07 ', ''))
            else:
                break
        cfg=''.join(cfg)
        diff_result = diff_config(name, cfg, 'msan')      # вызов функции сравнения конф-ий
        if diff_result:              # Если файлы различаются
    # FTP отправка
            upload_command = str('backup configuration ftp 10.20.0.14 /msan/' + name.strip() + '/' + timed + '-data.dat\n').encode('ascii')
            t.write(upload_command)  # ОТПРАВКА ФАЙЛА
            t.write(b'y\n')  # подтверждение отправки файла
            backup_check = t.read_until(b'(config)#\n  Backing up', timeout=10)
#            print(backup_check)
    # Логирование
            if bool(findall(r'Backing up files is successful', str(backup_check))):
                pass
            elif bool(findall(r'The file with the same name exists on FTP server', str(backup_check))):
                elog("Файл с таким именем уже существует", ip, name)
            else:
                elog("Backup FAILED :(", ip, name)
        t.write(b'quit\n')  # logout
        t.write(b'y\n')