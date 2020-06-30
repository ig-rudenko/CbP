import os.path


def diff_config(object_name, new_config, profile):
    '''
    Функция сравнивает сохранённый в файле и переданный в переменной конфиг.
    Аргументы : имя узла(str), конфиг(str), профиль(str)
    На выходе выдает одинаковые ли конфиги, если разные перезаписывает сохранённый конфиг текущим
    '''
    cfgfile = '/srv/svi/diff_cfg/' + object_name + '.txt'
    if not os.path.isfile(cfgfile):
        with open(cfgfile, 'w'):
            pass
    with open(cfgfile, 'r') as f:
        old_config = []
        for line in f:
            old_config.append(line)
        old_config = ''.join(old_config)

    # Если файлы конфигурации отличаются либо папка с бэкапами данного оборудования пуста
#    if old_config != new_config or os.listdir('/srv/config_mirror/'+profile+'/'+object_name+'/') == []:
    if old_config != new_config:
        diff = True
        with open(cfgfile, 'w') as f:
            f.write(new_config)
    else:
        diff = False
    return diff
