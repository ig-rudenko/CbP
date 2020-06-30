from concurrent.futures import ThreadPoolExecutor
import subprocess
from datetime import datetime
import os
from profiles.msan import msan
from profiles.zte import zte
import logs
#import profiles.iskratel import iskratel
from profiles.zyxel import zyxel
start_time = datetime.now()


def login(ip, profile, name, tftp):
    '''
    Функция проверяет доступность оборудования
    и наличие каталога под оборудование.
    После, отправляет имя устройства и его ip на profiles.py
    '''
    result = subprocess.run(['ping', '-c', '3', '-n', ip], stdout=subprocess.DEVNULL)  # Проверка на доступность: 0 - доступен, 1 и 2 - недоступен
    x = result.returncode
    if x == 0:
        main_patch = '/srv/config_mirror/'
        if profile == 'MSAN':
            if not os.path.exists(main_patch + 'msan/' + name):
                os.mkdir(main_patch + 'msan/' + name)
                os.chown(main_patch + 'msan/' + name, 113, 65534)
            msan(ip, name)
        elif profile == 'ZTE':
            if not os.path.exists(main_patch + 'asw/' + name):
                os.mkdir(main_patch + 'asw/' + name)
                os.chown(main_patch + 'asw/' + name, 113, 65534)
            zte(ip, name, tftp)
        elif profile == 'Extreme':
            if not os.path.exists(main_patch + 'ssw/' + name):
                os.mkdir(main_patch + 'ssw/' + name)
                os.chown(main_patch + 'ssw/' + name, 113, 65534)
            extreme(ip, name)
        elif profile == 'Zyxel':
            if not os.path.exists(main_patch + 'dsl/' + name):
                os.mkdir(main_patch + 'dsl/' + name)
                os.chown(main_patch + 'dsl/' + name, 113, 65534)
            zyxel(ip, name)
    elif x == 1:  # Запись в логи
        with open('/srv/svi/log/core.log', 'a') as logged:
            logs.info_log.info("Оборудование недоступно: %s" % ip)
    elif x == 2:
        with open('/srv/svi/log/core.log', 'a') as logged:
            logs.info_log.info("Неправильный ip адрес: %s" % ip)


def core():
    with open('/srv/svi/all_switch.txt', 'r') as main_file:  # Файл с данными об оборудовании
        with ThreadPoolExecutor(max_workers=30) as executor:  # Управление потоками
            main_file = main_file.readlines()
            for equipment in main_file:
                cut = equipment.split(' ')
                if len(cut) > 2 and not '#' in cut[0]:
                    ip = cut[0]
                    vendor = cut[1]
                    name = cut[2]
                    tftp = False
                    if len(cut) == 4 and '+' in cut[3]:
                        tftp = True
                    executor.submit(login, ip, vendor, name.strip(), tftp)


core()


logs.info_log.info("Общее время выполнения скрипта: %s" % str(datetime.now() - start_time))


