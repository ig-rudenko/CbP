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


def dslam_iskratel(ip, name):
    # print(ip, name)
    user = 'admin'
    with open('/etc/svi_password.cfg', 'r') as f:
        master_password = f.readlines()
        for find_pass in master_password:
            if user in find_pass:
                password = str(find_pass.split(' ')[1]).encode('ascii')
    user = user.encode('ascii')
    # -------------------------------------------НАЧАЛО-------------------------------------------------
    with telnetlib.Telnet(ip) as t:
        output = str(t.read_until(b'User:', timeout=2))
        if bool(findall(r'User:', output)):
            t.write(user + b'\n')
        else:
            elog("Таймаут превышен", ip, name)
            return 0
        output = str(t.read_until(b'Password:', timeout=2))
        if bool(findall(r'Password:', output)):
            t.write(password + b'\n')
        else:
            elog("Таймаут превышен", ip, name)
            return 0
        output = str(t.read_until(b'#', timeout=0.5))
        if bool(findall(r'User:', output)):
            elog("Неверный логин или пароль", ip, name)
            return 0
        t.write(b'show running-config\n')
        # ---------------------------ЛИСТИНГ КОНФИГУРАЦИИ--------------------------------
        cfg = []
        while True:
            check = t.read_until(b'--More-- or (q)uit', timeout=0.5).decode('ascii')
            if bool(findall(r'--More-- or \(q\)uit', str(check))):
                t.write(b' ')
                print('.')
                cfg.append(check.replace('--More-- or (q)uit\n\n\n', '').replace('\r', '').replace('\n\n\n', ''))
            else:
                break
        cfg = ''.join(cfg)
        print(cfg)
        diff_result = diff_config(name, cfg, 'iskratel')  # вызов функции сравнения конф-ий
        if diff_result:
            send_tftp = str('copy nvram:startup-config tftp://10.20.0.14/srv/config_mirror/iskratel/'+name+'/'+timed+'config\n').encode('ascii')  # Передача по tftp
            t.write(send_tftp)
            t.write(b'y')
            backup_check = t.read_until(b'successfully', timeout=5)
            # Логирование
            if not bool(findall(r'successfully', str(backup_check))):
                elog("Backup FAILED :(", ip, name)

        t.write(b'logout\n')
        t.write(b'n')
dslam_iskratel('192.168.189.169', 'name')