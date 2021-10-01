from datetime import datetime
import pexpect
from cbp.core import logs


def elog(info, ip, name):
    """функция логгирования"""
    logs.error_log.error("%s-> %s: %s" % (ip.ljust(15, '-'), name, info))


def get_configuration(session):
    session.sendline('show startup-config')
    session.expect(r'Using \d+ out of \d+ bytes')
    saved_config = ''
    while True:
        m = session.expect(
            [
                r" --More-- ",  # 0 - продолжаем
                r'\S+#$'        # 1 - конец
            ],
            timeout=2
        )
        saved_config += session.before.decode('utf-8').replace('        ', '')
        if m == 0:
            session.send(' ')
        else:
            break
    return saved_config


def backup(session, device_name: str, device_ip: str, backup_group: str, backup_server: dict):

    if backup_server["workdir"] == '/':
        backup_server["workdir"] = ''
    if backup_server["workdir"].endswith('/'):
        backup_server["workdir"] = backup_server["workdir"][:-1]
    if backup_server["workdir"].startswith('/'):
        backup_server["workdir"] = backup_server["workdir"][1:]

    print(device_name, device_ip, backup_group, backup_server)
    session.sendline('configure terminal')
    print('configure terminal')
    session.expect(r'\S+\(config\)#$')
    session.sendline('ip ftp passive')
    print('ip ftp passive')
    session.expect(r'\S+\(config\)#$')
    session.sendline('end')
    print('end')
    session.expect(r'\S+#$')

    timed = str(datetime.now().strftime('%d-%b-%Y_%H:%M')).replace(':', '_')  # 27-Sep-2021_09_40 (Пример)

    print(f'copy startup-config ftp://{backup_server["login"]}:{backup_server["password"]}@{backup_server["ip"]}'
          f'{backup_server["workdir"]}/{backup_group}/{device_name}/{timed}_config')
    session.sendline(
        f'copy startup-config ftp://{backup_server["login"]}:{backup_server["password"]}@{backup_server["ip"]}'
        f'{backup_server["workdir"]}/{backup_group}/{device_name}/{timed}_config'
    )
    session.sendline('\n\n')
    session.expect(r'[Ww]riting')
    backup_status = session.expect(
        [
            'bytes copied',                 # 0 - удачно
            '[Ee]rror writing',             # 1 - ошибка
            pexpect.TIMEOUT                 # 2
        ],
        timeout=30
    )
    print('backup status:', backup_status)
    if backup_status == 1:
        session.expect(r'\S+#$')
        error_cause = session.before.decode('utf-8').replace('\n', ' ').replace('\r', ' ')
        logs.error_log.error(f"{device_name} ({device_ip}): Backup error: {error_cause}")

    return f'{backup_server["workdir"]}/{backup_group}/{device_name}/{timed}_config' if not backup_status else ''

