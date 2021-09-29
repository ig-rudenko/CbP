import ftplib
from cbp.core.logs import critical_log


def ftp_login(ftp_server):
    ftp = None
    try:
        ftp = ftplib.FTP(ftp_server.host)
        ftp.login(ftp_server.login, ftp_server.password)
    except Exception as e:
        critical_log.critical(f"FTP: {ftp_server.host} {e}")
    return ftp
