import os.path
import sys
from configparser import ConfigParser

conf = ConfigParser()
conf.read(f'{sys.path[0]}/cbp.conf')
diff_cfg_dir = conf.get('Path', 'diff_cfg_dir').replace('~', sys.path[0])


def diff_config(object_name: str, new_config: str) -> bool:
    """
    Функция сравнивает сохранённый в файле и переданный в переменной конфиг.
    Аргументы : имя узла(str), конфиг(str), профиль(str)
    На выходе выдает одинаковые ли конфиги, если разные перезаписывает сохранённый конфиг текущим
    """
    # Если не существует директории для хранения сравнений конфигураций, то создаем папки
    if not os.path.exists(diff_cfg_dir):
        os.makedirs(diff_cfg_dir)
    cfg_file_path = f'{diff_cfg_dir}/{object_name}.txt'     # Путь к файлу сравнения конфигурации
    # Если не существует файла для хранения сравнений конфигураций, то создаем его
    if not os.path.isfile(cfg_file_path):
        with open(cfg_file_path, 'w'):
            pass
    # Считываем последовательно строчки файла с последней сохраненной конфигурацией
    with open(cfg_file_path, 'r') as f:
        old_config = [line for line in f]
    # Записываем в этот же файл новую конфигурацию
    with open(cfg_file_path, 'w') as w:
        w.write(new_config)
    # Считываем её по строчно, как и предыдущую конфиг-ю, для соблюдения единого формата при сравнении
    with open(cfg_file_path, 'r') as r:
        new_config = [line for line in r]

    # Файлы конфигурации отличаются?
    if old_config != new_config:
        return True
    else:
        return False
