from concurrent.futures import ThreadPoolExecutor
import subprocess
from datetime import datetime
import os
from profiles.msan import msan
from profiles.zte import zte
import logs
from profiles.iskratel_slot import iskratel_slot
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
        main_patch='/srv/config_mirror/'
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
        elif profile == 'Iskratel_slot':
            if not os.path.exists(main_patch + 'dsl/' + name):
                os.mkdir(main_patch + 'dsl/' + name)
                os.chown(main_patch + 'dsl/' + name, 113, 65534)
            iskratel_slot(ip, name)
        elif profile == 'Zyxel':
            if not os.path.exists(main_patch + 'dsl/' + name):
                os.mkdir(main_patch + 'dsl/' + name)
                os.chown(main_patch + 'dsl/' + name, 113, 65534)
            zyxel(ip, name)
    elif x == 1:  # Запись в логи
        logs.info_log.info("Оборудование недоступно: %s" % ip)
    elif x == 2:
        logs.info_log.info("Неправильный ip адрес: %s" % ip)


def core():
    with open('/srv/svi/all_switch.txt', 'r') as main_file:  # Файл с данными об оборудовании
        try:
            with ThreadPoolExecutor(max_workers=10) as executor:  # Управление потоками
                main_file = main_file.readlines()
                for equipment in main_file:
                    cut = equipment.split(' ')
                    if len(cut) > 2 and not '#' in cut[0]:
                        ip = cut[0]
                        vendor = cut[1]
                        name = cut[2]
                        tftp=False
                        if len(cut) == 4 and '+' in cut[3]:
                            tftp = True
                        try:
                            executor.submit(login, ip, vendor, name.strip(), tftp)
                        except InvalidStateError as invalid_state:
                            logs.critical_log.critical('%s: Попытка вызова незавершенного потока. %s' % (invalid_state, ip))
                        except thread.BrokenThreadPool as sys_resource:
                            logs.critical_log.critical('%s: Не удалось инициализировать поток. %s' % (sys_resource, ip))
                        except CancelledError as stopped_thread:
                            logs.critical_log.critical('%s: Прерывание потока. %s' % (stopped_thread, ip))
                    elif not '#' in cut[0]:
                        logs.info_log.info('Неправильный синтаксис all_switch: %s' % cut)
        except KeyboardInterrupt:
            logs.critical_log.critical('Ручная остановка кода')

#try: core()
#except: logs.critical_log.critical('Скрипт не может быть запущен')
core()

subprocess.run(['chown', '-R', 'proftpd:nogroup', '/srv/config_mirror/'])
subprocess.run(['chmod', '-R', '600', '/srv/config_mirror/'])
subprocess.run('find /srv/config_mirror/ -type d -exec chmod 700 {} \;', shell=True)

logs.info_log.info("Общее время выполнения скрипта: %s" % str(datetime.now() - start_time))

