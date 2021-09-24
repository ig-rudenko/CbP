import pymysql
import configparser
from cbp.core import logs
import sys
from tabulate import tabulate

conf = configparser.ConfigParser()
try:
    conf.read(f'{sys.path[0]}/cbp.conf')
    db_host = conf.get('mysql', 'host')
    db_user = conf.get('mysql', 'user')
    db_pass = conf.get('mysql', 'password')
    db_database = conf.get('mysql', 'database')

except Exception as error:
    logs.critical_log.critical(error)
    raise error

if not db_host or not db_database or not db_user or not db_pass:
    logs.critical_log.critical('Заполните данные [mysql] в файле конфигурации')
    raise 'Заполните данные [mysql] в файле конфигурации'


class ConnectionDB(object):

    def __enter__(self):
        try:
            self.connection = pymysql.Connection(
                host=db_host,
                user=db_user,
                password=db_pass,
                database=db_database
            )
            if not self.connection:
                logs.critical_log('Не удалось подключиться к базе данных')
            self.cursor = self.connection.cursor()

        except Exception as error:
            logs.critical_log.critical(error)
            raise error

        return self.cursor

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        If __exit__ returns True, the exception is suppressed.
        """
        self.cursor.close()
        if self.connection:
            self.connection.close()
        if exc_type:
            print(f'Exception type: {exc_type}')
            print(f'Value: {exc_val}')
            print(f'Traceback: {exc_tb}')
        else:
            return True

    def __call__(self, function):
        def inner(*args, **kwargs):
            with self as cursor:
                inner.__setattr__('cursor', cursor)
                return_value = function(*args, **kwargs)
                self.connection.commit()
                return return_value

        return inner


class DataBase:

    @ConnectionDB()
    def add_device(self, data: list) -> None:
        """
        Принимаем на вход список [ ip, device_name, vendor, auth_group, backup_group ]
        """
        try:
            self.add_device.cursor.execute(
                f"""insert into cbp_equipment(ip, device_name, vendor, auth_group_id, backup_group_id) values (
                                                        '{data[0]}', 
                                                        '{data[1]}', 
                                                        '{data[2]}', 
                                                        {data[3]}, 
                                                        {data[4]})"""
            )
        except pymysql.IntegrityError:
            # Данная строка уже имеется
            pass
        except Exception as error:
            logs.critical_log.critical(error)

    @ConnectionDB()
    def show_table(self, table: str):
        try:
            self.show_table.cursor.execute(
                f"select * from {table};"
            )
        except Exception as error:
            logs.critical_log.critical(error)

        print(
            tabulate(
                self.show_table.cursor.fetchall(),
                headers=['ip', 'device_name', 'vendor', 'protocol', 'auth_group', 'backup_group'],
                tablefmt="presto"
            )
        )

    @ConnectionDB()
    def get_table(self, table_name: str):
        try:
            self.get_table.cursor.execute(
                f"select * from {table_name};"
            )
        except Exception as error:
            logs.critical_log.critical(error)
            raise error

        return self.get_table.cursor.fetchall()

    @ConnectionDB()
    def get_dev_item(self, ip: str = None, device_name: str = None):
        try:
            if ip:
                self.get_dev_item.cursor.execute(
                    f"select * from cbp_equipment where ip = '{ip}';"
                )
            elif device_name:
                self.get_dev_item.cursor.execute(
                    f"select * from cbp_equipment where device_name = '{device_name}';"
                )
            else:
                return False
        except Exception as error:
            logs.critical_log.critical(error)
            raise error
        return self.get_dev_item.cursor.fetchall()

    @ConnectionDB()
    def execute(self, command):
        try:
            self.execute.cursor.execute(command)
            return self.execute.cursor.fetchall()
        except pymysql.OperationalError as OperationalError:
            print(f'pymysql.OperationalError: {command}\n{OperationalError}')
            return False
        except Exception as error:
            raise error

    @ConnectionDB()
    def update_device(self, ip: str, update_data: dict):
        command = 'UPDATE cbp_equipment SET '
        for key in update_data:
            command += f"{key}='{update_data[key]}'" if isinstance(update_data[key], str) else f"{key}={update_data[key]}"
            command += ', '
        else:
            command = command[:-2] + f" WHERE ip='{ip}'"
        self.execute(command)
