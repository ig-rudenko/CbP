#! /usr/bin/env python
# -*- coding: utf-8 -*-

import telnetlib
import datetime
import re
#from diff_config import diff_config
import ftplib
import os
import re

user = ''
password = ''
ip = ''
name = 'test'


def ftp_get_dir(my_folder, start_path):
        print(my_folder, start_path)
        main_dir = '/tffs/' + main_dir + '/' + str(my_folder).strip('[]').strip("'")
        print(main_dir)
        ftp.cwd(main_dir)  # переход в папку
        path = start_path + '/' + str(my_folder).strip('[]').strip("'")  # путь до папки
        print(path)
        os.mkdir(path)       # создание папки
        print('test')
        output = ftp.nlst()  # вывод файлов в папке
        output.remove('.')  # очистка
        output.remove('..')  # очистка
        print(my_folder)
        print(output)
        if output != []:
            for my_file in output:
                print(my_file)
                try:
                    with open(path + '/' + my_file, 'wb') as local_file:
                        ftp.retrbinary('RETR ' + my_file, local_file.write)
                    print('file: '+my_file+' downloaded')
                except ftplib.error_perm:
                    os.remove(path + '/' + my_file)
                    print(my_file + ' is dir')
                    ftp_get_dir(my_file, path)
                print('---------------\n'+path+' |---------------\n')
        x = re.findall("(\D+)\/\D", path)
        path = x[0]
        x = re.findall("(\D+)\/\D", main_dir)
        path = x[0]


                # os.remove(path + '/' + down_file)
                # match = re.match(r'550 (.*): not a plain file', str(exc))
                # next_folder = next_folder.append(match[1])

            # for folder in next_folder:
            #     ftp.cwd('/tffs/' + my_folder + '/' + folder)
            #     output = ftp.nlst()
            #     print(output)


with ftplib.FTP(ip) as ftp:
    now = datetime.datetime.now()
    ftp.login(user=user, passwd=password)
    ftp.cwd('/tffs')                                                # переход в корень
    now = now.strftime('%d-%m-%Y_%H-%M')                            # время
    start_path = '/srv/config_mirror/iskratel/' + name + '/' + now  # начальный путь на сервере
    os.mkdir(start_path)                                            # создание папки
    main_folders = re.findall(r'M[A-Z,0-9]*', ' '.join(ftp.nlst())) # поиск главных папок
    for main_folder in main_folders:
        #mmain_dir = '/tffs'
        ftp_get_dir(main_folder, start_path)
        # start_path = start_path + '/' + str(main_folder).strip('[]').strip("'")  # путь
        # os.mkdir(start_path)      # создание пути
        # #ftp.cwd(str(main_folder).strip('[]').strip("'"))        #переход в папку
        # output = ftp.nlst()         # вывод файлов в папке
        # output.remove('.')          # очистка
        # output.remove('..')         # очистка


