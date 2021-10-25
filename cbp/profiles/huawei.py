import pexpect
from datetime import datetime
from re import findall
from cbp.core.commands import send_command as cmd


def login(session, privilege_mode_password: str):
    huawei_type = 'huawei-2326'
    session.sendline('super')
    v = session.expect(
        [
            'Unrecognized command|Now user privilege is 3 level',     # 0 - huawei-2326
            '[Pp]ass',                  # 1 - huawei-2403 повышение уровня привилегий
            'User privilege level is'   # 2 - huawei-2403 уже привилегированный
        ]
    )
    if v == 1:
        session.sendline(privilege_mode_password)
    if v >= 1:
        huawei_type = 'huawei-2403'
    if session.expect(
            [
                r'<\S+>',   # 0 - режим просмотра
                r'\[\S+\]'  # 1 - режим редактирования
            ]
    ):  # Если находимся в режиме редактирования, то понижаем до режима просмотра
        session.sendline('quit')
        session.expect(r'<\S+>$')
    return huawei_type


def send_command(session, command: str, prompt=r'<\S+>$') -> str:
    return cmd(session, command, prompt=f'{prompt}|Unrecognized command', space_prompt="  ---- More ----")


def get_configuration(session, privilege_mode_password: str):
    login(session, privilege_mode_password)
    return send_command(session, 'display saved-configuration')


def backup(session, device: dict, backup_group: str, backup_server: dict):
    """
    Подключаемся к FTP серверу непосредственно от сетевого оборудования, создаем необходимые директории и
    отправляем файл конфигурации на сервер
    """
    # Сессия должна быть от привилегированного пользователя
    config_file_name = findall(r'Startup saved-configuration file:\s+flash:\/(\S+)',
                               send_command(session, 'display startup'))
    if config_file_name:
        config_file_name = config_file_name[0]
    else:
        return ''

    # Подключаемся к FTP серверу
    session.sendline(f'ftp {backup_server["ip"]}')
    session.expect(r'[Tt]rying')  # Ожидаем подключения
    if session.expect([r'Connected to', pexpect.TIMEOUT], timeout=10):
        # Если не удалось подключиться, то ftp сервер недоступен
        print(f'FTP сервер {backup_server["ip"]} недоступен, не удалось подключиться')
        return ''

    session.sendline(backup_server['login'])
    session.sendline(backup_server['password'])

    # Проверяем статус подключения к ftp серверу
    conn_status = session.expect(
        [
            r'\[ftp\]|230',                  # 230  -  Пользователь идентифицирован, продолжаем
            r'530|connection was closed'     # 530  -  Вход не выполнен! Неверный логин или пароль
        ],
        timeout=10
    )

    if conn_status:
        print('530  -  Вход не выполнен! Неверный логин или пароль')
        return ''  # Если не удалось подключиться

    # Включаем пассивный режим передачи
    session.sendline('passive')
    # Переходим в рабочую директорию
    session.sendline(f'cd {backup_server["workdir"] or "/"}')
    # Создаем группу
    session.sendline(f'mkdir {backup_group}')
    # Создаем папку для текущего устройства в группе
    session.sendline(f'mkdir {backup_group}/{device["name"]}')
    # Переходим в нее
    session.sendline(f'cd {backup_group}/{device["name"]}')
    if session.expect(['250', '550']):
        print(f'Не удалось перейти в папку {backup_server["workdir"]}/{backup_group}/{device["name"]}')
        return ''
    session.expect(r'\[ftp\]$')

    # Определяем текущее время
    timed = str(datetime.now().strftime('%d-%b-%Y_%H:%M')).replace(':', '_')  # 27-Sep-2021_09_40 (Пример)

    # Помещаем файл конфигурации в файл с названием времени создания в текущей папке
    session.sendline(f'put {config_file_name} {timed}_{config_file_name}')
    backup_status = session.expect([
        r'226',  # Бэкап успешен
        r'Error: Failed to run this command because opening local file is unsuccessful'  # Неверное имя файла конфигурации
    ])

    # Возвращаем путь к файлу на ftp сервере
    return f'{backup_server["workdir"]}/{backup_group}/{device["name"]}/{timed}_{config_file_name}' if not backup_status else ''