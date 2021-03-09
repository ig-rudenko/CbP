import time
import shutil
import os.path
from re import findall
from control.diff_config import diff_config
from datetime import datetime
from control import logs

timed = str(datetime.now())[0:10]   # текущая дата 'yyyy-mm-dd'


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
        print(output)
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


def get_configuration(telnet_session, privilege_mode_password: str):
    telnet_session.sendline('\n')
    if telnet_session.expect([r'\(cfg\)#\s*$', r'>\s*$']):
        telnet_session.sendline('enable')
        telnet_session.expect('pass')
        telnet_session.sendline(privilege_mode_password)
        telnet_session.expect(r'\(cfg\)#\s*$')
    telnet_session.sendline('show start-config')
    config = ''
    while True:
        m = telnet_session.expect(
                [r'\(cfg\)#\s*$', '----- more ----- Press Q or Ctrl+C to break -----']
            )
        config += telnet_session.before.decode('utf-8')
        if m == 0:
            break
        elif m == 1:
            telnet_session.sendline(' ')
    return config

    # wii - После преобразования с битовой строки остаются символы:
    wii = '\x08 \x08\x08 \x08\x08 \x08\x08 \x08\x08 \x08\x08 \x08\x08 \x08\x08 \x08\x08 \x08\x08 \x08\x08 ' \
          '\x08\x08 \x08\x08 \x08\x08 \x08\x08 \x08\x08 \x08\x08 \x08\x08 \x08\x08 \x08'

    # --------------------------Сравнение конфигураций-------------------------------
    trfl = diff_config(name, cfg, 'asw')
    t.write(b'config tffs\n')
    if trfl:
        # ------------------------------РАБОТА С TFTP----------------------------------
        if tftp:
            command_to_copy = str('copy startcfg.txt  ' + zte_name + '.txt \n').encode('ascii')
            # Копирование файла на коммутаторе
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
                command_to_copy = str('copy startrun.dat  ' + zte_name + '.txt \n').encode('ascii')
                # Копирование файла на коммутаторе
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

# zte('172.30.0.73', 'SVSL-961-Eroshenko9-ASW1', True)
