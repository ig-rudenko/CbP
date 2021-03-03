#! /usr/bin/env python
# -*- coding: utf-8 -*-

import telnetlib
import datetime
import re
from diff_config import diff_config
import ftplib
import os
from control import logs


def iskratel_slot(devices_ip, name):
    '''
    Функция бэкапа конфига с плат Iskratel.
    Аргументы: ip платы(str), имя платы(str).
    '''

    ### Логи ###
    def elog(info, devices_ip, name):

        '''
        Функция логирования.
        Аргументы: текст ошибки(str), ip платы(str), имя платы(str).
        '''
        logs.error_log.error("%s-> %s: %s" % (devices_ip.ljust(15, '-'), name, info))
    ### / ###

    ### FTP download ###

    def ftp_download(start_path, local_path):
        '''
        Функция построения дерева директорий и скачивания всех файлов в них.
        Аргументы: начальный путь на ftp(str), начальный локальный путь для записи(str).
        '''

        try:
            ftp.cwd(start_path)
        except Exception as exc:
            elog("Ошибка при переходе в директорию " + start_path + ': ' + str(exc) , devices_ip, name)
            pass
        ls = []
        ftp.dir(ls.append)
        for line in ls:
            if line.startswith('d') and not line.endswith('.'):
                dir = re.search(r'\S*$', line)
                try:
                    os.mkdir(local_path + '/' + dir.group(0))
                    print(name + '    найдена папка ' + dir.group(0))
                    ftp_download(start_path + '/' + dir.group(0), local_path + '/' + dir.group(0))
                except Exception as exc:
                    elog('Ошибка создания директории ' + dir.group(0) + ': ' + str(exc), devices_ip, name)
                    pass
            if line.startswith('-'):
                try:
                    file = re.search(r'\S*$', line)
                    print(name + '    найден файл ' + file.group(0))
                    with open (local_path + '/' + file.group(0), 'wb') as local_file:
                        ftp.retrbinary('RETR ' + file.group(0), local_file.write)
                except Exception as exc:
                    elog('Ошибка при скачивании файла ' + file.group(0) + ': ' + str(exc), devices_ip, name)
                    pass
        return
    ### / ###

    now = datetime.datetime.now()
    print(name + '    старт')
    ### Юзернейм и пароль ###
    user = 'sysadmin'
    with open('/etc/svi_password.cfg', 'r') as f:
        master_password = f.readlines()
        for find_pass in master_password:
            try:
                if user and 'iskratel_slot' in find_pass:
                    password = str(find_pass.split(' ')[1]).encode('ascii')
                    en_user = user.encode('ascii')
            except Exception as exc:
                elog('Пароль не найден: ' + str(exc), devices_ip, name)
                return
    ### / ###

    ### Логин ###
    t = telnetlib.Telnet(devices_ip)
    output = t.expect([b'user id :'], timeout=2)
    if bool(re.findall(r'user id :', output[2].decode('ascii'))) == True:
        t.write(en_user + b'\n')
    else:
        elog('Не найдена строка ввода логина', devices_ip, name)
        return
    output = t.expect([b'password:'], timeout=2)
    if bool(re.findall(r'password:', output[2].decode('ascii'))) == True:
        t.write(password + b'\n')
    else:
        elog('Не найдена строка ввода пароля', devices_ip, name)
        return
    ### / ###

    ### Чтение конфигурации ###
    output = t.expect([b'mBAN>'], timeout=2)
    if bool(re.findall(r'mBAN>', output[2].decode('ascii'))) == True:
        t.write(b'show system config\n')
        print(name + '    логин успешен')
    else:
        elog('Не найдена строка приглашения',devices_ip, name)
        return
    cfg = []
    i = 1
    check = (b'1', b'2', b'3')
    while 'mBAN>' not in check[2].decode('ascii'):
        check = t.expect([b'Press any key to continue or Esc to stop scrolling.', b'mBAN>'], timeout=0.2)
        t.write(b' ')
        cfg.append(check[2].decode('ascii').replace('\r\nPress any key to continue or Esc to stop scrolling.', ''))
        i+=1
        if i > 110:
            print(name + '    бесконечный цикл конфига')
            break
#    try:
#        while i < 30:
#            output = t.expect([b'Press any key to continue or Esc to stop scrolling.'], timeout=0.2)
#            if bool(re.findall(r'Press any key to continue or Esc to stop scrolling.', output[2].decode('ascii'))) == True:
#                cfg.append(output[2].decode('ascii').replace('\r\nPress any key to continue or Esc to stop scrolling.', ''))
#                t.write(b' ')
#            elif bool(re.findall(r'mBAN>$', output[2].decode('ascii'))) == True:
#                cfg.append(output[2].decode('ascii').replace('\r\nPress any key to continue or Esc to stop scrolling.', ''))
#                break
#            elif if bool(re.findall(r'Press any key to continue or Esc to stop scrolling.', output[2].decode('ascii'))) == False:
#                
#            i+=1
#            print(i)
#    except Exception as exc:
#        elog('Ошибка чтения конфигурации: ' + str(exc),devices_ip, name)
#        return
    ### / ###

    t.write(b'exit\n')  # logout 

    ### Первод конфига в строку, удаление блоков с динамическими данными, вызов функции сравнения ###
    cfg = ''.join(cfg).replace('\r', '')
    cut1 = cfg.find('Basic System data')
    cut2 = cfg.find('IP routing-running')
    cut3 = cfg.find('Bridge status:')
    cut4 = cfg.find('Mactable for all interfaces:')
    cut5 = cfg.find('VLANs registered in system:')
    cut6 = cfg.find('bridge poll load')
    cut7 = cfg.find('calculated discardind probabilities')
    cut8 = cfg.find('Status and summary statistic DHCP RA:')
    cut9 = cfg.find('Opt82 and statistics for each interface:')
    cut10 = cfg.find('Status and summary statistic of PPPoE IA:')
    cut11 = cfg.find('Show PPPoE specific information for each interface:')
    cut12 = cfg.find('mBAN>')
    cfg = cfg[cut1:cut2] + cfg[cut3:cut4] + cfg[cut5:cut6] + cfg[cut7:cut8] + cfg[cut9:cut10] + cfg[cut11:cut12]
    print(name + '    конфиг собран и подрезан')
    try:
        diff_result = diff_config(name, cfg, 'iskratel')
    except Exception as exc:
        elog('Ошибка функции сравнения: ' + str(exc), devices_ip, name)
        return
     ### / ###

    if diff_result == True:

        ### FTP ###
        try:
            with ftplib.FTP(devices_ip) as ftp:
                ftp.login(user=user, passwd=password.decode('ascii'))
                ftp.cwd('/tffs')
                now = now.strftime('%d-%m-%Y_%H-%M')
                start_local_path = '/srv/config_mirror/dsl/' + name + '/' + now
                os.mkdir(start_local_path)
                my_folders = re.findall(r'M[A-Z,0-9]*', ' '.join(ftp.nlst()))
                for my_folder in my_folders:
                    print(name + '    найдена М папка ' + my_folder)
                    local_path = start_local_path + '/' + str(my_folder).strip('[]').strip("'")
                    os.mkdir(local_path)
                    download = ftp_download('/tffs/'+str(my_folder).strip('[]').strip("'"), local_path)
                ftp.quit()
        except Exception as exc:
            elog('Ошибка FTP: ' + str(exc), devices_ip, name)
            ftp.quit()
            return
        ### / ###
    print(name + '    скрипт завешён')
#test =  iskratel_slot('192.168.188.43', 'test_isk')
