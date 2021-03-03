#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import pexpect
from re import findall
import sys
from profiles import huawei_msan, zyxel
import yaml
import ipaddress
from control.database import DataBase
from control.diff_config import diff_config

root_dir = sys.path[0]


def ip_range(ip_input_range_list: list):
    result = []
    for ip_input_range in ip_input_range_list:
        if '/' in ip_input_range:
            try:
                ip = ipaddress.ip_network(ip_input_range)
            except ValueError:
                ip = ipaddress.ip_interface(ip_input_range).network
            return [str(i) for i in list(ip.hosts())]
        range_ = {}
        ip = ip_input_range.split('.')
        for num, oct in enumerate(ip, start=1):
            if '-' in oct:
                ip_range = oct.split('-')
                ip_range[0] = ip_range[0] if 0 <= int(ip_range[0]) < 256 else 0
                ip_range[1] = ip_range[0] if 0 <= int(ip_range[1]) < 256 else 0
                range_[num] = oct.split('-')
            elif 0 <= int(oct) < 256:
                range_[num] = [oct, oct]
            else:
                range_[num] = [0, 0]

        for oct1 in range(int(range_[1][0]), int(range_[1][1])+1):
            for oct2 in range(int(range_[2][0]), int(range_[2][1])+1):
                for oct3 in range(int(range_[3][0]), int(range_[3][1])+1):
                    for oct4 in range(int(range_[4][0]), int(range_[4][1])+1):
                        result.append(f'{oct1}.{oct2}.{oct3}.{oct4}')
    return result


class TelnetConnect:
    def __init__(self, ip: str, device_name: str = ''):
        self.configuration_str = None
        self.device_name = device_name
        self.ip = ip
        self.auth_mode = 'default'
        self.auth_file = f'{root_dir}/auth.yaml'
        self.auth_group = None
        self.login = []
        self.password = []
        self.telnet_session = None
        self.vendor = ''
        self.interfaces = []
        self.raw_interfaces = []
        self.device_info = None
        self.mac_last_result = None
        self.vlans = None
        self.vlan_info = None
        self.cable_diag = None
        self.backup_group = 'default'

    def set_authentication(self, mode: str = 'default', auth_file: str = f'{root_dir}/auth.yaml',
                           auth_group: str = None, login=None, password=None) -> None:
        self.auth_mode = mode
        self.auth_file = auth_file
        self.auth_group = auth_group

        if self.auth_mode.lower() == 'default' or self.auth_mode.lower() == 'group':
            try:
                with open(self.auth_file, 'r') as file:
                    auth_dict = yaml.safe_load(file)
                self.login = ['admin'] if not self.auth_group else auth_dict['GROUPS'][self.auth_group.upper()]['login']
                self.password = ['admin'] if not self.auth_group else auth_dict['GROUPS'][self.auth_group.upper()]['password']
                self.login = self.login if isinstance(self.login, list) else [self.login]
                self.password = self.password if isinstance(self.password, list) else [self.password]

            except Exception:
                self.login = ['admin']
                self.password = ['admin']

        if self.auth_mode.lower() == 'auto':
            try:
                with open(self.auth_file, 'r') as file:
                    auth_dict = yaml.safe_load(file)
                for group in auth_dict["GROUPS"]:
                    iter_dict = auth_dict["GROUPS"][group]  # Записываем группу в отдельзую переменную
                    # Если есть ключ 'devices_by_name' и в нем имеется имя устройства ИЛИ
                    # есть ключ 'devices_by_ip' и в нем имеется IP устройства
                    if (iter_dict.get('devices_by_name') and self.device_name in iter_dict.get('devices_by_name')) \
                            or (iter_dict.get('devices_by_ip') and self.ip in ip_range(iter_dict.get('devices_by_ip'))):
                        # Логин равен списку логинов найденных в элементе 'login' или 'admin'
                        self.login = (iter_dict['login'] if isinstance(iter_dict['login'], list)
                                      else [iter_dict['login']]) if iter_dict.get('login') else ['admin']
                        # Логин равен списку паролей найденных в элементе 'password' или 'admin'
                        self.password = (iter_dict['password'] if isinstance(iter_dict['password'], list)
                                         else [iter_dict['password']]) if iter_dict.get('password') else ['admin']
                        break
                else:
                    self.login = ['admin']
                    self.password = ['admin']

            except Exception:
                self.login = ['admin']
                self.password = ['admin']

        if login and password:
            self.login = login if isinstance(login, list) else [login]
            self.password = password if isinstance(password, list) else [password]

        if self.auth_mode == 'mixed':
            try:
                with open(self.auth_file, 'r') as file:
                    auth_dict = yaml.safe_load(file)
                self.login = auth_dict['MIXED']['login']
                self.password = auth_dict['MIXED']['password']

            except Exception:
                self.login = ['admin']
                self.password = ['admin']

    def connect(self) -> bool:
        if not self.login or not self.password:
            self.set_authentication()
        connected = False
        self.telnet_session = pexpect.spawn(f"telnet {self.ip}")
        try:
            for login, password in zip(self.login, self.password):
                while not connected:    # Если не авторизировались
                    login_stat = self.telnet_session.expect(
                        [
                            r"[Ll]ogin(?![-\siT]).*:\s*$",  # 0
                            r"[Uu]ser\s(?![lfp]).*:\s*$",   # 1
                            r"[Nn]ame.*:\s*$",              # 2
                            r'[Pp]ass.*:\s*$',              # 3
                            r'Connection closed',           # 4
                            r'Unable to connect',           # 5
                            r']$',                          # 6
                            r'>\s*$',                       # 7
                            r'#\s*$',                       # 8
                        ],
                        timeout=20
                    )
                    if login_stat < 3:
                        self.telnet_session.sendline(login)     # Вводим логин
                        continue                                # Ищем следующую строку
                    if 4 <= login_stat <= 5:
                        print("    Telnet недоступен!")
                        return False
                    if login_stat == 3:
                        self.telnet_session.sendline(password)  # Вводим пароль
                        break
                    if login_stat >= 6:                         # Если был поймал символ начала ввода команды
                        connected = True                        # Подключились
                        break                                   # Выход из цикла

                if connected:
                    break

            else:  # Если не удалось зайти под логинами и паролями из списка аутентификации
                print('    Неверный логин или пароль!')
                return False

            # Подключаемся к базе данных и смотрим, есть ли запись о вендоре для текущего оборудования
            db = DataBase()
            item = db.get_item(ip=self.ip)
            if not item:    # Если в базе нет данных, то создаем их
                db.add_data(data=[(self.ip, self.device_name, self.vendor, self.auth_group, self.backup_group)])
            else:
                self.vendor = item[0][2]

            # Если нет записи о вендоре устройства, то определим его
            if not self.vendor:
                self.telnet_session.sendline('show version')
                version = ''
                while True:
                    m = self.telnet_session.expect([r']$', '-More-', r'>\s*$', r'#\s*', pexpect.TIMEOUT])
                    version += str(self.telnet_session.before.decode('utf-8'))
                    if m == 1:
                        self.telnet_session.sendline(' ')
                    if m == 4:
                        self.telnet_session.sendcontrol('C')
                    else:
                        break
                if ' ZTE Corporation:' in version:
                    self.vendor = 'zte'
                if 'Unrecognized command' in version:
                    self.vendor = 'huawei'
                if 'cisco' in version.lower():
                    self.vendor = 'cisco'
                if 'Next possible completions:' in version:
                    self.vendor = 'd-link'
                if findall(r'SW version\s+', version):
                    self.vendor = 'alcatel_or_lynksys'
                if 'Hardware version' in version:
                    self.vendor = 'edge-core'
                if 'Active-image:' in version:
                    self.vendor = 'eltex-mes'
                if 'Boot version:' in version:
                    self.vendor = 'eltex-esr'
                if 'ExtremeXOS' in version:
                    self.vendor = 'extreme'
                if 'QTECH' in version:
                    self.vendor = 'q-tech'

                if '% Unknown command' in version:
                    self.telnet_session.sendline('display version')
                    while True:
                        m = self.telnet_session.expect([r']$', '---- More', r'>$', r'#', pexpect.TIMEOUT, '{'])
                        if m == 5:
                            self.telnet_session.expect('}:')
                            self.telnet_session.sendline('\n')
                            continue
                        version += str(self.telnet_session.before.decode('utf-8'))
                        if m == 1:
                            self.telnet_session.sendline(' ')
                        if m == 4:
                            self.telnet_session.sendcontrol('C')
                        else:
                            break
                    if findall(r'VERSION : MA\d+', version):
                        self.vendor = 'huawei-msan'

                if 'show: invalid command, valid commands are' in version:
                    self.telnet_session.sendline('sys info show')
                    while True:
                        m = self.telnet_session.expect([r']$', '---- More', r'>\s*$', r'#\s*$', pexpect.TIMEOUT])
                        version += str(self.telnet_session.before.decode('utf-8'))
                        if m == 1:
                            self.telnet_session.sendline(' ')
                        if m == 4:
                            self.telnet_session.sendcontrol('C')
                        else:
                            break
                    if 'ZyNOS version' in version:
                        self.vendor = 'zyxel'

                # После того, как определили тип устройства, обновляем таблицу базы данных
                db.update(
                    ip=self.ip,
                    update_data=[
                        (self.ip, self.device_name, self.vendor, self.auth_group, self.backup_group)
                    ]
                )
            return True

        except pexpect.exceptions.TIMEOUT:
            print("    Время ожидания превышено! (timeout)")
            return False

    def get_saved_configuration(self):
        if 'huawei-msan' in self.vendor:
            self.configuration_str = huawei_msan.get_configuration(self.telnet_session)
            return self.configuration_str
        if 'zyxel' in self.vendor:
            self.configuration_str = zyxel.get_configuration(
                self.ip, self.device_name, self.login[0], self.password[0]
            )
            return self.configuration_str

    def config_diff(self):
        return diff_config(self.device_name, self.configuration_str)

    def backup_configuration(self):
        if 'huawei-msan' in self.vendor:
            return huawei_msan.backup(self.telnet_session, self.ip, self.device_name, self.backup_group)
        if 'zyxel' in self.vendor:
            return zyxel.backup(self.ip, self.device_name, self.login[0], self.password[0], self.backup_group)
