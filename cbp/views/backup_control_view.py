from django.shortcuts import render
from django.contrib.auth.models import User
from django.http import HttpResponsePermanentRedirect, JsonResponse
from django.contrib.auth.decorators import login_required
from cbp.models import BackupGroup

from re import findall
from configparser import ConfigParser
from datetime import timedelta, date

import sys
import os


@login_required(login_url='accounts/login/')
def show_logs(request):
    if not request.user.is_superuser:
        return HttpResponsePermanentRedirect('/')
    return render(request, 'backup_control/logs.html')


@login_required(login_url='accounts/login/')
def get_logs(request):
    print(request.GET)
    if not request.user.is_superuser:
        return JsonResponse({
            'data': []
        })

    def date_format(d: str):
        date_ = d[:10]
        if str(date.today()) == date_:
            date_ = 'Сегодня'
        elif date_ == str(date.today() - timedelta(days=1)):
            date_ = 'Вчера'
        elif date_ == str(date.today() - timedelta(days=2)):
            date_ = 'Позавчера'
        return f'{date_} {d[11:]}'

    conf = ConfigParser()
    conf.read(f'{sys.path[0]}/cbp.conf')  # Файл конфигурации
    logs_dir = conf.get('Path', 'logs_dir').replace('~', sys.path[0])  # Папка сохранения логов

    if os.path.exists(os.path.join(logs_dir, f"{request.GET.get('type')}.log")):
        with open(os.path.join(logs_dir, f"{request.GET.get('type')}.log")) as file:
            log_file = file.readlines()
    else:
        return JsonResponse({
            'data': []
        })
    logs_data = [
        {
            'time': date_format(line[:19]),
            'module': findall(r'\| (\S+) -> ', line[19:])[0],
            'content': findall(r'\| \S+ -> (.+)', line[19:])[0]
        }
        for line in log_file
    ]

    return JsonResponse({
        'data': logs_data
    })


@login_required(login_url='accounts/login/')
def tasks(request):
    if not request.user.is_superuser:
        return HttpResponsePermanentRedirect('/')
    backup_groups = [bg.backup_group for bg in BackupGroup.objects.all()]

    if request.method == 'POST':
        print(request.POST)
        cron_task = []  # Список задач, которые будут записаны в cron
        for bg in backup_groups:
            if request.POST.get(f'min-{bg}'):
                cron_min = request.POST.get(f'min-{bg}')
                cron_hour = request.POST.get(f'hour-{bg}') or '*'
                cron_day = request.POST.get(f'day-{bg}') or '*'
                cron_month = request.POST.get(f'month-{bg}') or '*'
                cron_week_day = request.POST.get(f'week_day-{bg}') or '*'

                cron_task.append(f'{cron_min} {cron_hour} {cron_day} {cron_month} {cron_week_day} '
                                 f'python /home/django/backup.py {bg}\n')
        print(cron_task)
        with open('/var/spool/cron/crontabs/root', 'w') as cron_file:
            cron_file.writelines(cron_task)

        return HttpResponsePermanentRedirect('/backup_control/tasks')


    print(request.GET)
    with open('/var/spool/cron/crontabs/root') as cron_file:
        crontab_list = [str(l) for l in cron_file.readlines() if not l.startswith('#')]

    if not crontab_list:
        # Пустая таблица crontab
        print('cron is empty')

    result = dict.fromkeys(backup_groups)  # Группы и их период (по умолчанию None)

    for cron_task in crontab_list:
        if s := findall(r'backup\.py (\S+)', cron_task):
            if s[0] in backup_groups:  # Нашли задачу для группы
                result[s[0]] = findall(r'^(\S+) (\S+) (\S+) (\S+) (\S+) ', cron_task)[0]
    print(result)

    return render(request, 'backup_control/tasks.html', {'cron': result})
