import subprocess
from control import logs


def killed_svi():
    '''
    Убивает скрипт backup.py
    '''
    result = subprocess.run(['ps', 'aux'], stdout=subprocess.PIPE) # Вывод всех активных процессов
    x = result.stdout.decode('utf-8').split('\n')
    for templates in x:
        if '/srv/svi/backup.py' in templates and not '/bin/sh -c' in templates: # GREP
            pid = templates.split()[1] # Вырываем PID
            subprocess.run(['kill', '-15', pid]) # Убиваем процесс с этим PID
            logs.critical_log.critical('backup.py был прерван')


killed_svi()
