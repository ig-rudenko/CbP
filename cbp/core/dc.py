import pexpect
from re import findall
import sys
from cbp.profiles import huawei_msan, zyxel, zte, iskratel_slot, cisco
import yaml
import ipaddress
from cbp.core.database import DataBase
from cbp.core.diff_config import diff_config
from cbp.core import logs


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


class DeviceConnect:
    """
    Взаимодействие с сетевым оборудованием
    """
    def __init__(self, ip: str, device_name: str = ''):
        self.__auth_profile = {
            'login': '',
            'password': '',
            'privilege_mode_password': ''
        }
        self.device: dict = {
            'ip': ip,
            'name': device_name,
            'vendor': '',
            'model': ''
        }
        self.session = None
        self.device_info = None

    def connect(self, login, password, privilege_mode_password,
                timeout=30,
                protocol='telnet',
                algorithm: str = '',    # Для ssh
                cipher: str = ''        # Для ssh
                ) -> bool:

        self.__auth_profile['login'] = login
        self.__auth_profile['password'] = password
        self.__auth_profile['privilege_mode_password'] = privilege_mode_password

        connected = False
        if protocol == 'ssh':
            algorithm_str = f' -oKexAlgorithms=+{algorithm}' if algorithm else ''
            cipher_str = f' -c {cipher}' if cipher else ''
            for login, password in zip([login] + ['admin'], [password] + ['admin']):
                self.session = pexpect.spawn(
                    f'ssh {login}@{self.device["ip"]}{algorithm_str}{cipher_str}'
                )
                while not connected:
                    login_stat = self.session.expect(
                        [
                            r'no matching key exchange method found',  # 0
                            r'no matching cipher found',  # 1
                            r'Are you sure you want to continue connecting',  # 2
                            r'[Pp]assword:',  # 3
                            r'[#>\]]\s*$',  # 4
                            r'Connection closed'  # 5
                        ],
                        timeout=timeout
                    )
                    if login_stat == 0:
                        self.session.expect(pexpect.EOF)
                        algorithm = findall(r'Their offer: (\S+)', self.session.before.decode('utf-8'))
                        if algorithm:
                            algorithm_str = f' -oKexAlgorithms=+{algorithm[0]}'
                            self.session = pexpect.spawn(
                                f'ssh {login}@{self.device["ip"]}{algorithm_str}{cipher_str}'
                            )
                    if login_stat == 1:
                        self.session.expect(pexpect.EOF)
                        cipher = findall(r'Their offer: (\S+)', self.session.before.decode('utf-8'))
                        if cipher:
                            cipher_str = f' -c {cipher[0].split(",")[-1]}'
                            self.session = pexpect.spawn(
                                f'ssh {login}@{self.device["ip"]}{algorithm_str}{cipher_str}'
                            )
                    if login_stat == 2:
                        self.session.sendline('yes')
                    if login_stat == 3:
                        self.session.sendline(password)
                        if self.session.expect(['[Pp]assword:', r'[#>\]]\s*$']):
                            connected = True
                            break
                        else:
                            break  # Пробуем новый логин/пароль
                    if login_stat == 4:
                        connected = True
                if connected:
                    break

        if protocol == 'telnet':
            self.session = pexpect.spawn(f'telnet {self.device["ip"]}')
            try:
                for login, password in zip([login] + ['admin'], [password] + ['admin']):
                    while not connected:  # Если не авторизировались
                        login_stat = self.session.expect(
                            [
                                r"[Ll]ogin(?![-\siT]).*:\s*$",  # 0
                                r"[Uu]ser\s(?![lfp]).*:\s*$",  # 1
                                r"[Nn]ame.*:\s*$",  # 2
                                r'[Pp]ass.*:\s*$',  # 3
                                r'Connection closed',  # 4
                                r'Unable to connect',  # 5
                                r'[#>\]]\s*$',  # 6
                                r'Press any key to continue'  # 7
                            ],
                            timeout=timeout
                        )
                        if login_stat == 7:  # Если необходимо нажать любую клавишу, чтобы продолжить
                            self.session.send(' ')
                            self.session.sendline(login)  # Вводим логин
                            self.session.sendline(password)  # Вводим пароль
                            self.session.expect('#')

                        if login_stat < 3:
                            self.session.sendline(login)  # Вводим логин
                            continue
                        if 4 <= login_stat <= 5:
                            print(f'    Telnet недоступен! {self.device["name"]} ({self.device["ip"]})')
                            return False
                        if login_stat == 3:
                            self.session.sendline(password)  # Вводим пароль
                        if login_stat >= 6:  # Если был поймал символ начала ввода команды
                            connected = True  # Подключились
                        break  # Выход из цикла

                    if connected:
                        break

                else:  # Если не удалось зайти под логинами и паролями из списка аутентификации
                    print(f'    Неверный логин или пароль! {self.device["name"]} ({self.device["ip"]})')
                    return False
            except pexpect.exceptions.TIMEOUT:
                print(f'Login Error: Время ожидания превышено! {self.device["name"]} ({self.device["ip"]})')
                return False

            DeviceConnect.__set_vendor(self)

            return True

    def __set_vendor(self):
        """
        Подключаемся к оборудованию и определяем его вендор
        """

        self.session.sendline('show version')
        version = ''
        while True:
            m = self.session.expect([r']$', '-More-', r'>\s*$', r'#\s*', pexpect.TIMEOUT, pexpect.EOF])
            version += str(self.session.before.decode('utf-8'))
            if m == 1:
                self.session.sendline(' ')
            if m == 4:
                self.session.sendcontrol('C')
            else:
                break
        if ' ZTE Corporation:' in version:
            self.device['vendor'] = 'zte'
        if 'Unrecognized command' in version:
            self.device['vendor'] = 'huawei'
        if 'cisco' in version.lower():
            self.device['vendor'] = 'cisco'
        if 'Next possible completions:' in version:
            self.device['vendor'] = 'd-link'
        if findall(r'SW version\s+', version):
            self.device['vendor'] = 'alcatel_or_lynksys'
        if 'Hardware version' in version:
            self.device['vendor'] = 'edge-core'
        if 'Active-image:' in version:
            self.device['vendor'] = 'eltex-mes'
        if 'Boot version:' in version:
            self.device['vendor'] = 'eltex-esr'
        if 'ExtremeXOS' in version:
            self.device['vendor'] = 'extreme'
        if 'QTECH' in version:
            self.device['vendor'] = 'q-tech'

        if '% Unknown command' in version:
            self.session.sendline('display version')
            while True:
                m = self.session.expect([r']$', '---- More', r'>$', r'#', pexpect.TIMEOUT, pexpect.EOF, '{'])
                if m == 5:
                    self.session.expect('}:')
                    self.session.sendline('\n')
                    continue
                version += str(self.session.before.decode('utf-8'))
                if m == 1:
                    self.session.sendline(' ')
                if m == 4:
                    self.session.sendcontrol('C')
                else:
                    break
            if findall(r'VERSION : MA\d+', version):
                self.device['vendor'] = 'huawei-msan'

        if 'show: invalid command, valid commands are' in version:
            self.session.sendline('sys info show')
            while True:
                m = self.session.expect([r']$', '---- More', r'>\s*$', r'#\s*$', pexpect.TIMEOUT, pexpect.EOF])
                version += str(self.session.before.decode('utf-8'))
                if m == 1:
                    self.session.sendline(' ')
                if m == 4:
                    self.session.sendcontrol('C')
                else:
                    break
            if 'ZyNOS version' in version:
                self.device['vendor'] = 'zyxel'

        if 'iskratel' in version.lower():
            self.device['vendor'] = 'iskratel'

        # После того, как определили тип устройства, обновляем таблицу базы данных
        db = DataBase()
        db.update_device(ip=self.device['ip'], update_data={'vendor': self.device['vendor']})

    def get_saved_configuration(self):
        """
        Считываем сохраненную конфигурацию у оборудования
        """
        if 'huawei-msan' in self.device['vendor']:
            self.configuration_str = huawei_msan.get_configuration(session=self.session, device=self.device)
        if 'zyxel' in self.device['vendor']:
            self.configuration_str = zyxel.get_configuration(ip=self.device['ip'], device=self.device)
        if 'zte' in self.device['vendor']:
            self.configuration_str = zte.get_configuration(session=self.session,
                                                           privilege_mode_password=self.__auth_profile[
                                                               'privilege_mode_password'])
        if 'iskratel' in self.device['vendor']:
            self.configuration_str = iskratel_slot.get_configuration(session=self.session, device=self.device)
        if 'cisco' in self.device['vendor']:
            self.configuration_str = cisco.get_configuration(
                telnet_session=self.session
            )
        return self.configuration_str

    def config_diff(self) -> bool:
        """
        Сравнивает конфигурацию на наличие изменений
        :return: True - конфиги отличаются; False - конфиги идентичны
        """
        return diff_config(self.device['name'], self.configuration_str)

    def backup_configuration(self, backup_group: str) -> bool:
        """
        Копирует конфигурационный файл(ы) оборудования в директорию, указанную в файле конфигурации cbp.conf
        """
        dev = None
        if 'huawei-msan' in self.device['vendor']:
            dev = huawei_msan
            return huawei_msan.backup(
                telnet_session=self.session,
                device_ip=self.device['ip'],
                device_name=self.device['name'],
                backup_group=backup_group
            )

        if 'zyxel' in self.device['vendor']:
            return zyxel.backup(
                ip=self.device['ip'],
                device_name=self.device['name'],
                login=self.__auth_profile['login'],
                password=self.__auth_profile['password'],
                backup_group=backup_group
            )
        if 'zte' in self.device['vendor']:
            return zte.backup(
                telnet_session=self.session,
                device_ip=self.device['ip'],
                device_name=self.device['name'],
                privilege_mode_password=self.__auth_profile['privilege_mode_password'],
                backup_group=backup_group
            )
        if 'iskratel' in self.device['vendor']:
            return iskratel_slot.backup(
                device_name=self.device['name'],
                device_ip=self.device['ip'],
                user=self.__auth_profile['login'],
                password=self.__auth_profile['password'],
                backup_group=backup_group
            )
        if 'cisco' in self.device['vendor']:
            return cisco.backup(
                telnet_session=self.session,
                device_ip=self.device['ip'],
                device_name=self.device['name'],
                backup_group=backup_group
            )
