import pexpect
from re import findall
import sys
import os
from cbp.profiles import huawei_msan, zyxel, zte, iskratel_slot, cisco, huawei
from cbp.core.database import DataBase
from cbp.core import logs


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
                        print(login_stat)
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
            self.session.expect('display version')
            while True:
                m = self.session.expect([r']$', '---- More', r'>$', r'#', pexpect.TIMEOUT, pexpect.EOF, '{'])
                if m == 6:
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
            model = findall(r'VERSION\s*:\s*(MA[\d\S]+)', version)
            if model:
                self.device['vendor'] = 'huawei-msan'
                self.device['model'] = model[0]

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
        if 'huawei' in self.device['vendor']:
            self.configuration_str = huawei.get_configuration(
                session=self.session,
                privilege_mode_password=self.__auth_profile['privilege_mode_password']
            )

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
            self.configuration_str = cisco.get_configuration(session=self.session)
        return self.configuration_str

    def config_diff(self) -> bool:
        """
        Сравнивает конфигурацию на наличие изменений
        Функция сравнивает сохранённый в файле и новый конфиг.
        :return: True - конфиги отличаются; False - конфиги идентичны
        """
        # Если не существует директории для хранения сравнений конфигураций, то создаем папки
        if not os.path.exists(f'{sys.path[0]}/diff'):
            os.makedirs(f'{sys.path[0]}/diff')
        cfg_file_path = f"{sys.path[0]}/diff/{self.device['name']}"  # Путь к файлу сравнения конфигурации
        # Если не существует файла для хранения сравнений конфигураций, то создаем его
        if not os.path.isfile(cfg_file_path):
            with open(cfg_file_path, 'w'):
                pass
        # Считываем последовательно строчки файла с последней сохраненной конфигурацией
        with open(cfg_file_path, 'r') as f:
            old_config = [line for line in f]
        # Записываем в этот же файл новую конфигурацию
        with open(cfg_file_path, 'w') as w:
            w.write(self.configuration_str)
        # Считываем её по строчно, как и предыдущую конфиг-ю, для соблюдения единого формата при сравнении
        with open(cfg_file_path, 'r') as r:
            new_config = [line for line in r]

        # Файлы конфигурации отличаются?
        if old_config != new_config:
            return True     # ДА
        else:
            return False    # НЕТ

    def backup_configuration(self, backup_group: str, backup_server: dict):
        """
        Копирует конфигурационный файл(ы) оборудования в директорию, указанную в файле конфигурации cbp.conf
        """
        print('backup starting...')
        if 'huawei' in self.device['vendor']:
            return huawei.backup(
                session=self.session,
                device=self.device,
                backup_group=backup_group,
                backup_server=backup_server
            )
        if 'huawei-msan' in self.device['vendor']:
            return huawei_msan.backup(
                session=self.session,
                device=self.device,
                backup_group=backup_group,
                backup_server=backup_server
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
                session=self.session,
                device_name=self.device['name'],
                device_ip=self.device['ip'],
                backup_group=backup_group,
                backup_server=backup_server
            )
