import ftplib
import pexpect
from re import findall
from dateconverter import DateConverter
from cbp.core.download_ftp_tree import download_ftp_tree
from cbp.core.logs import critical_log


def ftp_login(ftp_server):
    ftp = None
    try:
        ftp = ftplib.FTP(ftp_server.host)
        ftp.login(ftp_server.login, ftp_server.password)
    except Exception as e:
        critical_log.critical(f"FTP: {ftp_server.host} {e}")
    return ftp


def format_time(string: str):
    f = string.split()
    return DateConverter(f[1] + f[0] + f[2] if ':' not in f[2] else f[1] + f[0])


def sizeof_fmt(num: int, suffix='Б'):
    for unit in ['', 'К', 'М', 'Г', 'Т']:
        if abs(num) < 1024.0:
            return "%3.1f %s%s" % (num, unit, suffix)
        num /= 1024.0
    return "%.1f %s%s" % (num, 'Yi', suffix)


class FTP:
    def __init__(self, ftp_server: dict):
        self.__ftp = ftp_server
        try:
            self.__session = ftplib.FTP(self.__ftp["ip"])
            self.__session.login(self.__ftp["login"], self.__ftp["password"])
        except Exception as e:
            self.__session = None
            critical_log.critical(f"FTP: {self.__ftp['ip']} {e}")

    def alive(self):
        return bool(self.__session)

    def cd(self, path):
        self.__session.cwd(path)

    def dir(self, path: str = '/'):
        files_list = []
        files = []
        # Передаем все файлы конфигураций в массив
        self.__session.retrlines(f'LIST {path}', files_list.append)

        for file in files_list:
            type_ = 'd' if file.startswith('d') else 'f'
            file_stat = findall(r'^\S+\s+\d+\s+\S+\s+\S+\s+(\d+)\s+(\S+\s+\d+\s+\S+)\s+(.+)$', file)[0]
            files.append(
                (type_, sizeof_fmt(int(file_stat[0])), format_time(file_stat[1]), file_stat[2])
            )
        # Сортируем файлы по дате создания
        files = sorted(files, key=lambda x: x[2].date.toordinal())
        files.reverse()  # По убыванию

        return files

    def upload(self, file_path, remote_file_path):
        with open(file_path, 'rb') as ftp_file:
            self.__session.storbinary(f'STOR {remote_file_path}', ftp_file, 1024)

    def download(self, remote_file_path, to_local_file_path):
        # Создаем и открываем файл для записи
        with open(to_local_file_path, 'wb') as temp_file:
            # Записываем удаленный файл в локальный
            self.__session.retrbinary(f"RETR {remote_file_path}", temp_file.write)

    def download_folder(self, remote_folder, local_folder):
        download_ftp_tree(self.__session, remote_folder, local_folder)

    def delete(self, file):
        self.__session.delete(file)

    def mkdir(self, folder: str):
        try:
            self.__session.mkd(folder)
        except ftplib.error_perm:
            pass

    def __del__(self):
        if self.alive():
            self.__session.quit()
        del self


class SFTP:
    def __init__(self, sftp: dict):
        self.__sftp = sftp
        self.__session = pexpect.spawn(f'sftp -P {sftp["sftp_port"]} {sftp["login"]}@{sftp["ip"]}')
        if self.__session.expect([r'password', r'Are you sure you want to continue connecting']):
            self.__session.sendline('yes')
            self.__session.expect(r'password:')
        self.__session.sendline(sftp['password'])
        if self.__session.expect([r'sftp>', r'Permission denied']):
            self.__session = None

    def alive(self):
        return bool(self.__session)

    def cd(self, path):
        self.__session.sendline(f'cd {path}')
        if self.__session.expect([r'No such file or directory|is not a directory', r'sftp>']):
            return True
        return False

    def dir(self, path: str = ''):
        files = []
        self.__session.sendline(f'ls -l {path}')
        self.__session.expect(r'sftp>')
        files_list = self.__session.before.decode('utf-8').split('\r\n')
        for file in files_list:
            print(file)
            type_ = 'd' if file.startswith('d') else 'f'
            file_stat = findall(r'^\S+\s+\d+\s+\S+\s+\S+\s+(\d+)\s+(\S+\s+\d+\s+\S+)\s+(.+)$', file)
            if file_stat:
                files.append(
                    (type_, sizeof_fmt(int(file_stat[0][0])), format_time(file_stat[0][1]), file_stat[0][2])
                )
        # Сортируем файлы по дате создания
        files = sorted(files, key=lambda x: x[2].date.toordinal())
        files.reverse()  # По убыванию
        return files

    def upload(self, file_path, remote_file_path):
        self.__session.sendline(f'put {file_path} {remote_file_path}')
        if self.__session.expect([r'100%', r'No such file or directory'], timeout=30):
            return False
        return True

    def download(self, remote_file_path, to_local_file_path):
        self.__session.sendline(f'get {remote_file_path} {to_local_file_path}')
        if self.__session.expect([r'100%', r'not found|Not a directory|No such file or directory'], timeout=30):
            return False
        return True

    def download_folder(self, remote_folder, local_folder):
        download_ftp_tree(self.__session, remote_folder, local_folder)

    def delete(self, file):
        self.__session.sendline(f'rm {file}')
        if self.__session.expect([r'Removing', r'No such file or directory|Couldn\'t delete file']):
            return False
        return True

    def mkdir(self, folder: str):
        self.__session.sendline(f'mkdir {folder}')
        if self.__session.expect([r'sftp>', r'Couldn\'t create directory: Failure']):
            return False
        return True

    def __del__(self):
        if self.alive():
            self.__session.sendline('exit')
        del self


class Remote:
    def __init__(self, settings):
        if isinstance(settings, dict):
            self.__sets = {
                'id': settings.get('id'),
                'ip': settings['ip'],
                'name': settings.get('name') or 'unknown',
                'login': settings['login'],
                'password': settings['password'],
                'workdir': settings.get('workdir') or '/',
                'protocol': settings['protocol'],
                'sftp_port': settings.get('sftp_port') or 22
            }
        else:
            self.__sets = {
                'id': settings.id,
                'ip': settings.host,
                'name': settings.name,
                'login': settings.login,
                'password': settings.password,
                'workdir': settings.workdir,
                'protocol': settings.protocol,
                'sftp_port': settings.sftp_port
            }

    def connect(self):
        if self.__sets['protocol'] == 'SFTP':
            return SFTP(self.__sets)
        if self.__sets['protocol'] == 'FTP':
            return FTP(self.__sets)
