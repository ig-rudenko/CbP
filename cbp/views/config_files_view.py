from django.shortcuts import render
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponsePermanentRedirect, HttpResponseRedirect
from cbp.models import BackupGroup, FtpGroup, Equipment
from cbp.views.user_checks import check_user_permission

from cbp.core.logs import critical_log
from cbp.core.ftp_login import ftp_login
from cbp.core.download_ftp_tree import download_ftp_tree
from dateconverter import DateConverter
from re import findall
import shutil
import sys
import os


@login_required(login_url='accounts/login/')
def home(request):

    if request.method == 'GET':

        current_user = User.objects.get(username=str(request.user))  # Текущий пользователь
        available_backup_groups_ids = [g.id for g in
                                   BackupGroup.objects.filter(users__username=current_user.username)]

        # Все доступные группы у пользователя
        if not available_backup_groups_ids and not current_user.is_superuser:
            # Если у данного пользователя нет доступных групп и он не суперпользователь, то ничего не выводим
            return render(
                request,
                'home.html',
                {
                    "form": {},
                    'superuser': request.user.is_superuser
                }
            )

        all_ftp_servers = FtpGroup.objects.all()  # Все доступные FTP сервера
        ftp_dirs = {}  # Итоговый словарь

        for ftp_server in all_ftp_servers:
            # Подключаемся к каждому серверу
            try:
                ftp = ftp_login(ftp_server)  # Подключаемся к FTP серверу
                if not ftp:
                    continue  # Пропускаем сервер, к которому не удалось подключиться
                wd = ftp_server.workdir  # Рабочая директория FTP сервера
                dir_list = []  # Список из папок и файлов в рабочей директории FTP сервера
                ftp.retrlines(f'LIST {wd}', dir_list.append)  # Заполняем данными
                ftp_dirs[ftp_server.name] = {}  # Создаем словарь для FTP сервера
                # Backup группы

                for group in dir_list:  # Для каждого найденного файла в рабочей директории
                    # Определяем имя группы
                    gr = findall(r'^\S+\s+\S+\s+\S+\s+\S+\s+\d+\s+\S+\s+\d+\s+\S+\s+(.+)$', group)[0]

                    try:
                        # Определяем ID backup_group по имени группы у текущего сервера
                        bg_id = FtpGroup.objects.get(id=ftp_server.id).backupgroup_set.get(backup_group=gr).id
                    except BackupGroup.DoesNotExist:
                        # Если имя не найдено в базе
                        bg_id = 'none'

                    if group.startswith('d') and \
                            (bg_id in available_backup_groups_ids
                             or current_user.is_superuser):
                        # Сохраняем только папки и разрешенные для пользователя,
                        # Если суперпользователь, то все
                        ftp_dirs[ftp_server.name][gr] = {}

                # Проходимся по всем разрешенным группам
                for group in ftp_dirs[ftp_server.name]:
                    group_list = []  # Содержимое группы
                    ftp.retrlines(f'LIST {wd}/{group}', group_list.append)

                    # Создаем упорядоченный список папок для группы
                    group_list = sorted([findall(r'^\S+\s+\d+\s+\S+\s+\S+\s+\d+\s+\S+\s+\d+\s+\S+\s+(.+)$', g)[0]
                                         for g in group_list if g.startswith('d')])
                    for devs in group_list:  # Для каждого устройства в группе
                        ftp_dirs[ftp_server.name][group][devs] = []
                ftp.quit()

            except Exception as ftp_error:
                critical_log.critical(ftp_error)

        return render(
            request,
            'home.html',
            {
                "form": ftp_dirs,
                'superuser': request.user.is_superuser
            }
        )


@login_required(login_url='accounts/login/')
def download_file_(request):
    print('download', request.GET)
    check_user_permission(request)  # Проверяем, имеет ли пользователь полномочия скачивать файл из группы
    bg = request.GET.get('bg')  # Группа backup
    dn = request.GET.get('dn')  # Имя устройства
    fn = request.GET.get('fn')  # Имя файла
    fs = request.GET.get('fs')  # Имя FTP сервера
    try:
        # Находим FTP сервер, который относится к переданной backup group
        ftp_server = FtpGroup.objects.get(name=fs)
        ftp = ftp_login(ftp_server)

        # Проверяем папку для обмена файлами между ftp сервером и пользователем "./temp"
        if not os.path.exists(os.path.join(sys.path[0], 'temp')):
            os.mkdir(os.path.join(sys.path[0], 'temp'))  # Создаем, если нет

        temp_file_name = str(hash(f"{request.user}_{bg}_{dn}_{fn}"))

        # Проверяем, является ли объект файлом или папкой
        ftp_file = []
        ftp.retrlines(f"LIST {bg}/{dn}/{fn}", ftp_file.append)

        loc_file = os.path.join(sys.path[0], 'temp', temp_file_name)  # Полный путь к локальному файлу
        if ftp_file[0].startswith('d'):
            # Если папка
            # Скачиваем всё её содержимое рекурсивно в папку "./temp"
            download_ftp_tree(ftp, f"{bg}/{dn}/{fn}", 'temp')
            # Помещаем содержимое папки в архив
            shutil.make_archive(
                loc_file,   # файл архива
                'zip',      # тип
                os.path.join(sys.path[0], 'temp', bg, dn, fn)  # папка
            )
            loc_file += '.zip'
            file_name = f'{dn}_{fn}.zip'
            shutil.rmtree(os.path.join(sys.path[0], 'temp', bg), ignore_errors=True)  # Удаляем папку
        else:
            # Если файл
            # Создаем и открываем файл для записи
            file_name = f'{dn}_{fn}'
            with open(loc_file, 'wb') as temp_file:
                # Записываем удаленный файл в локальный
                ftp.retrbinary(f"RETR {bg}/{dn}/{fn}", temp_file.write)
            ftp.quit()

        # Отправляем пользователю файл
        if os.path.exists(loc_file):
            with open(loc_file, 'rb') as fh:
                response = HttpResponse(fh.read(), content_type="application/vnd.ms-excel")
            response['Content-Disposition'] = f'inline; filename={file_name}'
            os.remove(loc_file)
            return response

    except Exception as error:
        print(error)
        critical_log.critical(error)
    return HttpResponseRedirect(f'/config?bg={bg}&dn={dn}&fs={fs}')


@login_required(login_url='accounts/login/')
def list_config_files(request):

    def format_time(string: str):
        f = string.split()
        return DateConverter(f[1] + f[0] + f[2] if ':' not in f[2] else f[1] + f[0])

    def sizeof_fmt(num: int, suffix='Б'):
        for unit in ['', 'К', 'М', 'Г', 'Т']:
            if abs(num) < 1024.0:
                return "%3.1f %s%s" % (num, unit, suffix)
            num /= 1024.0
        return "%.1f %s%s" % (num, 'Yi', suffix)

    if request.method == 'GET':
        # Проверяем, имеет ли пользователь полномочия просматривать конфигурации в данной группе
        check_user_permission(request)
        backup_group = request.GET.get('bg')
        device_name = request.GET.get('dn')
        device = Equipment.objects.get(device_name=device_name)
        config_files = []
        # Находим FTP сервер, который относится к переданной backup group
        ftp_server = FtpGroup.objects.get(name=request.GET.get('fs'))

        ftp = ftp_login(ftp_server)

        config_files_list = []
        # Передаем все файлы конфигураций в массив
        ftp.retrlines(f'LIST {ftp_server.workdir}/{backup_group}/{device_name}', config_files_list.append)
        ftp.quit()

        for file in config_files_list:
            is_file = False if file.startswith('d') else True
            file_name = findall(r'^\S+\s+\d+\s+\S+\s+\S+\s+\d+\s+\S+\s+\d+\s+\S+\s+(.+)$', file)[0]
            file_create = format_time(findall(r'^\S+\s+\d+\s+\S+\s+\S+\s+\d+\s+(\S+\s+\d+\s+\S+)\s+.+$', file)[0])
            file_size = sizeof_fmt(int(findall(r'^\S+\s+\d+\s+\S+\s+\S+\s+(\d+)\s+\S+\s+\d+\s+\S+\s+.+$', file)[0])) if is_file else 'папка'
            config_files.append([file_name, file_create, file_size, is_file])
        # Сортируем файлы по дате создания
        config_files = sorted(config_files, key=lambda x: x[1].date.toordinal())
        config_files.reverse()  # По убыванию

        return render(request, 'devices_config_list.html',
                      {
                              "form": config_files,
                              "backup_group": backup_group,
                              "device_name": device_name,
                              "ftp_server": request.GET.get('fs'),
                              "superuser": request.user.is_superuser,
                              "device": device,
                          }
                      )

    # ЗАГРУЗКА ФАЙЛА
    elif request.method == 'POST' and request.FILES.get('file'):
        # Находим FTP сервер, который относится к переданной backup group
        ftp_server = FtpGroup.objects.get(name=request.GET.get('fs'))
        ftp = ftp_login(ftp_server)
        backup_group = request.POST.get('bg')
        device_name = request.POST.get('dn')
        # Проверяем папку для обмена файлами между ftp сервером и пользователем
        if not os.path.exists(os.path.join(sys.path[0], 'temp')):
            os.mkdir(os.path.join(sys.path[0], 'temp'))  # Создаем, если нет
        temp_file_name = str(hash(f"{request.user}_{backup_group}_{device_name}_{request.FILES['file'].name}"))

        with open(os.path.join(sys.path[0], 'temp', temp_file_name), 'wb+') as new_file:
            for chunk_ in request.FILES['file'].chunks():
                new_file.write(chunk_)

        with open(os.path.join(sys.path[0], 'temp', temp_file_name), 'rb') as ftp_file:
            ftp.storbinary('STOR ' + f"{ftp_server.workdir}/{backup_group}/{device_name}/"
                                     f"{str(request.FILES['file'].name).replace(' ', '_')}",
                           ftp_file, 1024)
        ftp.quit()  # Отключаемся от ftp сервера
        os.remove(os.path.join(sys.path[0], 'temp', temp_file_name))  # Удаляем временный файл
        return HttpResponsePermanentRedirect(f'/config?fs={request.GET.get("fs")}&bg={backup_group}&dn={device_name}')
    return HttpResponsePermanentRedirect('/')


@login_required(login_url='accounts/login/')
def show_config_file(request):
    # Проверяем, имеет ли пользователь полномочия просматривать конфигурацию в данной группе
    print(request.GET)
    check_user_permission(request)

    backup_group = request.GET.get('bg')
    device_name = request.GET.get('dn')
    config_file_name = request.GET.get('fn')
    ftp_server = FtpGroup.objects.get(name=request.GET.get('fs'))
    ftp = ftp_login(ftp_server)
    try:
        # Проверяем папку для обмена файлами между ftp сервером и пользователем
        if not os.path.exists(os.path.join(sys.path[0], 'temp')):
            os.mkdir(os.path.join(sys.path[0], 'temp'))  # Создаем, если нет

        temp_file_name = str(
            hash(f"{request.user}_{backup_group}_{device_name}_{config_file_name}"))
        # Создаем и открываем файл для записи
        with open(os.path.join(sys.path[0], 'temp', temp_file_name), 'wb') as temp_file:
            # Записываем удаленный файл в локальный
            ftp.retrbinary(f"RETR {ftp_server.workdir}/{backup_group}/{device_name}/{config_file_name}",
                           temp_file.write)
        ftp.quit()
        with open(os.path.join(sys.path[0], 'temp', temp_file_name)) as temp_file:
            file_output = temp_file.read()
        os.remove(os.path.join(sys.path[0], 'temp', temp_file_name))

    except UnicodeDecodeError:
        file_output = 'Невозможно прочитать данный файл в виде текста'
    return render(request, 'devices_config_show.html',
                  {
                          "form": file_output,
                          "device_name": device_name,
                          "backup_group": backup_group,
                          "ftp_server": request.GET.get('fs'),
                          "superuser": request.user.is_superuser
                      }
                  )


@login_required(login_url='accounts/login/')
def delete_file(request):
    print(request.GET)
    if not request.user.is_superuser:
        return HttpResponsePermanentRedirect('/')
    if request.method == 'GET':
        backup_group = request.GET.get('bg')
        device_name = request.GET.get('dn')
        file_name = request.GET.get('fn')
        ftp_server = FtpGroup.objects.get(name=request.GET.get('fs'))

        ftp = ftp_login(ftp_server)

        try:
            ftp.delete(f'{ftp_server.workdir}/{backup_group}/{device_name}/{file_name}')
        except Exception as e:
            critical_log.critical(f'delete file {ftp_server.workdir}/{backup_group}/{device_name}/{file_name}: {e}')

        return HttpResponsePermanentRedirect(f'config?fs={request.GET.get("fs")}&bg={backup_group}&dn={device_name}')

    else:
        return HttpResponsePermanentRedirect('/')

