import ftplib
from cbp.core.logs import critical_log


def ftp_login(ftp_server):
    print(ftp_server.host, ftp_server.login, ftp_server.password)
    ftp = ftplib.FTP(ftp_server.host)
    try:
        s = ftp.login(ftp_server.login, ftp_server.password)
        print(s)
    except Exception as e:
        critical_log.critical(e)
    return ftp
