import pexpect
from re import findall
import sys
from profiles import huawei_msan, zyxel, zte, iskratel_slot
import yaml
import ipaddress
from control.database import DataBase
from control.diff_config import diff_config

root_dir = sys.path[0]


def ip_range(ip_input_range_list: list):
    """
    Преобразует диапазон IP адресов в список каждого из них
        192.168.0.1/24    -> ['192.168.0.1', '192.168.0.2', ... '192.168.0.223', '192.168.0.254']

        192.168.0.1-224   -> ['192.168.0.1', '192.168.0.2', ... '192.168.0.223', '192.168.0.224']

        192.168.0-4.1-224 -> ['192.168.0.1', ... '192.168.0.224',
                              '192.168.1.1', ... '192.168.1.224',
                                             ...
                              '192.168.4.1', ... '192.168.0.224']
    """
    result = []  # Итоговый список
    for ip_input_range in ip_input_range_list:
        if '/' in ip_input_range:   # Если в записи IP адреса указана маска подсети
            try:
                ip = ipaddress.ip_network(ip_input_range)   # Пр
            except ValueError:
                ip = ipaddress.ip_interface(ip_input_range).network
            result += [str(i) for i in list(ip.hosts())]
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
    """
    Взаимодействие с сетевым оборудованием посредством протокола TELNET
    """
    def __init__(self, ip: str, device_name: str = ''):
        self.configuration_str = None
        self.device_name = device_name
        self.ip = ip
        self.auth_mode = 'database'
        self.auth_file = f'{root_dir}/auth.yaml'
        self.auth_group = None
        self.login = ['admin']
        self.password = ['admin']
        self.privilege_mode_password = 'enable'
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

    def set_authentication(self, mode: str = 'database', auth_file: str = f'{root_dir}/auth.yaml',
                           auth_group: str = None, login=None, password=None, privilege_mode_password: str = None):
        """
        Задает логин и пароль, в зависимости от выбранных параметров
        """
        self.auth_mode = mode           # Тип авторизации
        self.auth_file = auth_file      # Файл авторизации
        self.auth_group = auth_group    # Группа авторизации

        if mode == 'database':
            """
            Считывает информацию о параметрах авторизации из имеющейся базы данных, указанной в файле конфигурации
            """
            db = DataBase()
            item = db.get_item(ip=self.ip)
            if item:
                self.vendor = item[2]
                self.auth_group = item[3]
                self.backup_group = item[4] or 'default'
                self.auth_mode = 'group'

        if self.auth_mode.lower() == 'group':
            """
            Авторизация с помощью групп, находящихся в файле авторизации <auth_file>, ключ 'GROUPS'
                <auth_file>
                    GROUPS:
                     ├ group1:
                     │ ├ login: ...
                     │ ├ password: ...
                     │ └ privilege_mode_password: ...
                     │
                     └ group2:
                       ├ login: ...
                       ├ password: ...
                       └ privilege_mode_password: ...
            """
            try:
                with open(self.auth_file, 'r') as file:
                    auth_dict = yaml.safe_load(file)    # Преобразуем данные файла в словарь
                iter_dict = auth_dict['GROUPS'][self.auth_group.upper()]    # Находим нужную группу
                # Если имеется ключ 'login' то задаем переменной его значение в виде списка, иначе 'admin'
                self.login = (iter_dict['login'] if isinstance(iter_dict['login'], list)
                              else [iter_dict['login']]) if iter_dict.get('login') else ['admin']
                # Если имеется ключ 'password' то задаем переменной его значение в виде списка, иначе 'admin'
                self.password = (iter_dict['password'] if isinstance(iter_dict['password'], list)
                                 else [iter_dict['password']]) if iter_dict.get('password') else ['admin']
                # Если имеется ключ 'privilege_mode_password' то задаем переменной его значение, иначе 'enable'
                self.privilege_mode_password = iter_dict['privilege_mode_password'] if iter_dict.get(
                    'privilege_mode_password') else 'enable'

            except Exception:
                pass

        if self.auth_mode.lower() == 'auto':
            """
            Авторизация с помощью поиска IP адреса оборудования или его имени в первой попавшейся группе,
            ключи <devices_by_ip>, <devices_by_name>
            находящихся в файле авторизации <auth_file>, ключ 'GROUPS'
                <auth_file>
                    GROUPS:
                     ├ group1:
                     │ ├ login: ...
                     │ ├ password: ...
                     │ ├ privilege_mode_password: ...
                     │ ├ devices_by_ip: ...
                     │ └ devices_by_name: ...
                     │
                     └ group2:
                       ├ login: ...
                       ├ password: ...
                       ├ privilege_mode_password: ...
                       ├ devices_by_ip: ...
                       └ devices_by_name: ...
            """
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
                        self.privilege_mode_password = iter_dict['privilege_mode_password'] if iter_dict.get(
                            'privilege_mode_password') else 'admin'

                        break

            except Exception:
                pass

        if login and password:
            """
            Логин и пароль указаны явно
            """
            self.login = login if isinstance(login, list) else [login]
            self.password = password if isinstance(password, list) else [password]
            self.privilege_mode_password = privilege_mode_password if privilege_mode_password else 'admin'

        if self.auth_mode == 'mixed':
            """
            Авторизация с использованием нескольких логинов и паролей, указанных в файле <auth_file> ключ 'MIXED'
            <auth_file>
                    MIXED:
                     ├ login:
                     │  - login1
                     │  - login2
                     │  - login3
                     └ password:
                        - password1
                        - password2
                        - password3
            """
            try:
                with open(self.auth_file, 'r') as file:
                    auth_dict = yaml.safe_load(file)
                self.login = auth_dict['MIXED']['login']
                self.password = auth_dict['MIXED']['password']

            except Exception:
                pass

    def connect(self) -> bool:
        """
        Подключаемся к оборудованию и определяем его вендор
        """
        if not self.login or not self.password:
            self.set_authentication()
        connected = False
        self.telnet_session = pexpect.spawn(f"telnet {self.ip}")
        try:
            for login, password in zip(self.login + ['admin'], self.password + ['admin']):
                while not connected:  # Если не авторизировались
                    login_stat = self.telnet_session.expect(
                        [
                            r"[Ll]ogin(?![-\siT]).*:\s*$",  # 0
                            r"[Uu]ser\s(?![lfp]).*:\s*$",   # 1
                            r"[Nn]ame.*:\s*$",              # 2
                            r'[Pp]ass.*:\s*$',              # 3
                            r'Connection closed',           # 4
                            r'Unable to connect',           # 5
                            r'[#>\]]\s*$'                   # 6
                        ],
                        timeout=20
                    )
                    if login_stat < 3:
                        self.telnet_session.sendline(login)  # Вводим логин
                        continue
                    if 4 <= login_stat <= 5:
                        print(f"    Telnet недоступен! {self.device_name} ({self.ip})")
                        return False
                    if login_stat == 3:
                        self.telnet_session.sendline(password)  # Вводим пароль
                    if login_stat >= 6:  # Если был поймал символ начала ввода команды
                        connected = True  # Подключились
                    break  # Выход из цикла

                if connected:
                    break

            else:  # Если не удалось зайти под логинами и паролями из списка аутентификации
                print(f'    Неверный логин или пароль! {self.device_name} ({self.ip})')
                return False

            # Подключаемся к базе данных и смотрим, есть ли запись о вендоре для текущего оборудования
            db = DataBase()
            item = db.get_item(ip=self.ip)
            if not item:    # Если в базе нет данных, то создаем их
                db.add_data(data=[(self.ip, self.device_name, self.vendor, self.auth_group, self.backup_group)])
            else:
                self.vendor = item[0][2]

            # Если нет записи о вендоре устройства, то определим его
            if not self.vendor or self.vendor == 'None':
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

                if 'iskratel' in version.lower():
                    self.vendor = 'iskratel'

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
        """
        Считываем сохраненную конфигурацию у оборудования
        """
        if 'huawei-msan' in self.vendor:
            self.configuration_str = huawei_msan.get_configuration(
                telnet_session=self.telnet_session
            )
        if 'zyxel' in self.vendor:
            self.configuration_str = zyxel.get_configuration(
                ip=self.ip,
                device_name=self.device_name,
                login=self.login[0],
                password=self.password[0]
            )
        if 'zte' in self.vendor:
            self.configuration_str = zte.get_configuration(
                telnet_session=self.telnet_session,
                privilege_mode_password=self.privilege_mode_password
            )
        if 'iskratel' in self.vendor:
            self.configuration_str = iskratel_slot.get_configuration(
                telnet_session=self.telnet_session
            )
        return self.configuration_str

    def config_diff(self) -> bool:
        """
        Сравнивает конфигурацию на наличие изменений

        :return: True - конфиги отличаются; False - конфиги идентичны
        """
        return diff_config(self.device_name, self.configuration_str)

    def backup_configuration(self):
        """
        Копирует конфигурационный файл(ы) оборудования в директорию, указанную в файле конфигурации cbp.conf
        """
        if 'huawei-msan' in self.vendor:
            return huawei_msan.backup(
                telnet_session=self.telnet_session,
                device_ip=self.ip,
                device_name=self.device_name,
                backup_group=self.backup_group
            )

        if 'zyxel' in self.vendor:
            return zyxel.backup(
                ip=self.ip,
                device_name=self.device_name,
                login=self.login[0],
                password=self.password[0],
                backup_group=self.backup_group
            )
        if 'zte' in self.vendor:
            return zte.backup(
                telnet_session=self.telnet_session,
                device_ip=self.ip,
                device_name=self.device_name,
                privilege_mode_password=self.privilege_mode_password,
                backup_group=self.backup_group
            )
        if 'iskratel' in self.vendor:
            return iskratel_slot.backup(
                device_name=self.device_name,
                device_ip=self.ip,
                user=self.login[0],
                password=self.password[0],
                backup_group=self.backup_group
            )
