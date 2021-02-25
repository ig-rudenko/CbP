import sqlite3

db_path = 'base.db'


class DbNotSpecifiedError(Exception):
    pass


class ConnectionDB(object):
    def __init__(self, *args, **kwargs):
        for k, v in kwargs.items():
            self.__setattr__(k, v)

    def __enter__(self):
        if 'database' not in self.__dict__:
            raise DbNotSpecifiedError("database attribute wasn't found")
        try:
            self.connection = sqlite3.connect(**self.__dict__)
            self.cursor = self.connection.cursor()
        except sqlite3.Error as db_err:
            print(f'Error: {db_err}')
            raise db_err
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
    def __init__(self, database: str):
        self.database_path = database

    @ConnectionDB(database=db_path)
    def create_table(self):
        cursor = self.create_table.cursor
        try:
            cursor.execute('''
                create table equipment (
                    ip              text not NULL primary key,
                    device_name     text not NULL,
                    vendor          text
                );
            ''')
            return True
        except sqlite3.OperationalError:
            return True
        except:
            return False

    @ConnectionDB(database=db_path)
    def add_data(self, data: list):
        for row in data:
            try:
                self.add_data.cursor.execute(
                    'insert into equipment values (?, ?, ?)',
                    row
                )
            except sqlite3.IntegrityError:
                pass

    @ConnectionDB(database=db_path)
    def show_table(self):
        self.show_table.cursor.execute(
            "select * from equipment"
        )
        print(self.show_table.cursor.fetchall())


if __name__ == '__main__':
    db = DataBase('base.db')
    if db:
        db.create_table()
        data = [('192.168.0.1', 'dev1', ''), ('192.168.0.2', 'dev2', '')]
        db.add_data(data)
        db.show_table()
