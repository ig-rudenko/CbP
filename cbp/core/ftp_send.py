import os
from cbp.core.logs import critical_log
from cbp.models import BackupGroup, FtpGroup
from re import findall
import ftplib


def send_file_to_server(file_path):
    try:
        bg, dn, fn = findall(r'/home/ftp/(\S+)/(\S+)/(\S+)$', file_path)[0]
        backup_group = BackupGroup.objects.get(backup_group=bg)  # Ищем бэкап группу по имени
        # print(backup_group.backup_group, backup_group.ftp_server_id)
        ftp_server = FtpGroup.objects.get(id=backup_group.ftp_server_id)  # Ищем профиль ftp по бэкап группе
        ftp = ftplib.FTP(host=ftp_server.host, user=ftp_server.login, passwd=ftp_server.password)
        # print(ftp)
        # Загружаем файл на сервер
        with open(file_path, 'rb') as ftp_file:
            status = ftp.storbinary('STOR ' + f"{ftp_server.workdir}/{bg}/{dn}/{fn}", ftp_file, 1024)
        os.remove(file_path)
        ftp.quit()  # Отключаемся от ftp сервера
        return status
    except Exception as e:
        critical_log.critical(e)
        return e
