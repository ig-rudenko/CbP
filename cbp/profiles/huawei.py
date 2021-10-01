import pexpect
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


def backup(session, device_name: str, device_ip: str, backup_group: str, backup_server: dict):
    # Сессия должна быть от привилегированного пользователя
    config_file_name = findall(r'Startup saved-configuration file:\s+flash:\/(\S+)',
                               send_command(session, 'display startup'))
    if config_file_name:
        config_file_name = config_file_name[0]
    else:
        return ''

    # Подключаемся к FTP серверу
