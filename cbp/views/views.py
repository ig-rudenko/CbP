from django.shortcuts import render
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseNotFound, HttpResponsePermanentRedirect, HttpResponseRedirect
from cbp.forms import AuthGroupsForm, BackupGroupsForm, DevicesForm
from cbp.models import AuthGroup, BackupGroup, Equipment, FtpGroup
from configparser import ConfigParser

from cbp.core.logs import critical_log
from cbp.core.ftp_login import ftp_login
from cbp.core.download_ftp_tree import download_ftp_tree
from dateconverter import DateConverter
from re import findall
import ftplib
import shutil
import sys
import os


def check_user_permission(request):
    current_user = User.objects.get(username=str(request.user))  # Текущий пользователь
    available_backup_groups = [g.backup_group for g in
                               BackupGroup.objects.filter(users__username=current_user.username)]
    if (not available_backup_groups or str(request.GET.get('bg')) not in available_backup_groups) \
            and not current_user.is_superuser:
        return HttpResponsePermanentRedirect('/')


def check_superuser(request):
    try:
        if not User.objects.get(username=str(request.user)).is_superuser:
            return 0
        else:
            return 1
    except Exception:
        return 0


def test(request):
    text = f"""
        Some attributes of the HttpRequest object:
        scheme: {request.scheme}
        path:   {request.path}
        method: {request.method}
        GET:    {request.GET}
        user:   {request.user}
    """
    return HttpResponse(text, content_type="text/plain")


@login_required(login_url='accounts/login/')
def home(request):

    if request.method == 'GET':

        current_user = User.objects.get(username=str(request.user))  # Текущий пользователь
        available_backup_groups = [g.backup_group for g in
                                   BackupGroup.objects.filter(users__username=current_user.username)]
        # Все доступные группы у пользователя
        if not available_backup_groups and not current_user.is_superuser:
            # Если у данного пользователя нет доступных групп и он не суперпользователь, то ничего не выводим
            return render(
                request,
                'home.html',
                {
                    "form": {},
                    'superuser': check_superuser(request)
                }
            )

        all_ftp_servers = FtpGroup.objects.all()  # Все доступные FTP сервера
        ftp_dirs = {}  # Итоговый словарь

        for ftp_server in all_ftp_servers:
            # Подключаемся к каждому серверу
            try:
                ftp = ftp_login(ftp_server)  # Подключаемся к FTP серверу
                wd = ftp_server.workdir  # Рабочая директория FTP сервера
                dir_list = []  # Список из папок и файлов в рабочей директории FTP сервера
                ftp.retrlines(f'LIST {wd}', dir_list.append)  # Заполняем данными

                ftp_dirs[ftp_server.name] = {}  # Создаем словарь для FTP сервера
                # Backup группы
                for group in dir_list:
                    # Определяем имя группы
                    gr = findall(r'^\S+\s+\d+\s+\S+\s+\d+\s+\d+\s+\S+\s+\d+\s+\S+\s+(.+)$', group)[0]
                    if group.startswith('d') and (gr in available_backup_groups or current_user.is_superuser):
                        # Сохраняем только папки и разрешенные для пользователя,
                        # Если суперпользователь, то все
                        ftp_dirs[ftp_server.name][gr] = {}

                # Проходимся по всем разрешенным группам
                for group in ftp_dirs[ftp_server.name]:
                    group_list = []  # Содержимое группы
                    ftp.retrlines(f'LIST {wd}/{group}', group_list.append)

                    # Создаем упорядоченный список папок для группы
                    group_list = sorted([findall(r'^\S+\s+\d+\s+\S+\s+\d+\s+\d+\s+\S+\s+\d+\s+\S+\s+(.+)$', g)[0]
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
                'superuser': check_superuser(request)
            }
        )

    elif request.method == 'POST':
        print(request.POST)
        groups = [g.backup_group for g in BackupGroup.objects.all()]  # Имена всех групп
        for g in groups:    # Проходимся по каждой
            if request.POST.get(g):  # Если переданная группа существует в базе, то создаем в ней папку
                try:
                    ftp_server = FtpGroup.objects.get(id=g.ftp_server_id)  # Находим FTP по id в Backup Group
                    ftp = ftplib.FTP(ftp_server.host)
                    ftp.login(ftp_server.login, ftp_server.password)
                    ftp.mkd(f"{ftp_server.workdir}/{g}/{request.POST.get(g)}")
                    ftp.quit()
                except Exception as ftp_error:
                    critical_log(ftp_error)
        return HttpResponsePermanentRedirect('/')


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
            file_name = findall(r'^\S+\s+\d+\s+\S+\s+\d+\s+\d+\s+\S+\s+\d+\s+\S+\s+(.+)$', file)[0]
            file_create = format_time(findall(r'^\S+\s+\d+\s+\S+\s+\d+\s+\d+\s+(\S+\s+\d+\s+\S+)\s+.+$', file)[0])
            file_size = sizeof_fmt(int(findall(r'^\S+\s+\d+\s+\S+\s+\d+\s+(\d+)\s+\S+\s+\d+\s+\S+\s+.+$', file)[0])) if is_file else 'папка'
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
                              "superuser": check_superuser(request)
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
                          "superuser": check_superuser(request)
                      }
                  )


@login_required(login_url='accounts/login/')
def delete_file(request):
    print(request.GET)
    if not check_superuser(request):
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


@login_required(login_url='accounts/login/')
def auth_groups(request):
    if not check_superuser(request):
        return HttpResponsePermanentRedirect('/')

    groups = AuthGroup.objects.all()
    return render(request, "device_control/auth_groups.html", {"form": AuthGroupsForm, "groups": groups})


@login_required(login_url='accounts/login/')
def auth_group_edit(request, id: int = 0):
    if not check_superuser(request):
        return HttpResponsePermanentRedirect('/')

    try:
        auth_group_form = AuthGroupsForm()
        if id:
            group = AuthGroup.objects.get(id=id)
            auth_group_form = AuthGroupsForm(initial={
                'group': group.auth_group,
                'login': group.login,
                'password': group.password,
                'privilege_mode_password': group.privilege_mode_password
            })
        else:
            group = AuthGroup()

        if request.method == "POST":
            group.auth_group = request.POST.get('group')
            group.login = request.POST.get('login')
            group.password = request.POST.get('password')
            group.privilege_mode_password = request.POST.get('privilege_mode_password')
            group.save()
            return HttpResponsePermanentRedirect("/auth_groups")
        else:
            return render(request, "device_control/auth_group_new.html", {"form": auth_group_form})
    except AuthGroup.DoesNotExist:
        return HttpResponseNotFound("<h2>Данная группа не найдена!</h2>")


@login_required(login_url='accounts/login/')
def auth_group_delete(request, id):
    if not check_superuser(request):
        return HttpResponsePermanentRedirect('/')

    try:
        group = AuthGroup.objects.get(id=id)
        group.delete()
        return HttpResponsePermanentRedirect('/auth_groups')
    except AuthGroup.DoesNotExist:
        return HttpResponseNotFound("<h2>Данная группа не найдена!</h2>")


@login_required(login_url='accounts/login/')
def backup_groups(request):
    if not check_superuser(request):
        return HttpResponsePermanentRedirect('/')

    groups = BackupGroup.objects.all()
    for bg in groups:
        if bg.ftp_server_id:
            ftp_server = FtpGroup.objects.get(id=bg.ftp_server_id)
            bg.ftp_server_id = f"{ftp_server.name} ({ftp_server.host})"
    return render(request, "device_control/backup_groups.html", {"form": BackupGroupsForm, "groups": groups})


@login_required(login_url='accounts/login/')
def backup_group_edit(request, bg_id: int = 0):
    if not check_superuser(request):
        return HttpResponsePermanentRedirect('/')

    try:
        backup_group_form = BackupGroupsForm()
        if bg_id:
            group = BackupGroup.objects.get(id=bg_id)  # Запись, которую необходимо редактировать
            # В форме задаем начальные значения, равные текущим сохраненным
            backup_group_form = BackupGroupsForm(initial={
                'group': group.backup_group,
                'ftp_server': group.ftp_server
            })
        else:
            group = BackupGroup()

        if request.method == "POST":
            group.backup_group = request.POST.get('group')
            group.save()
            # Находим запись ftp сервера по переданному id
            ftp_server = FtpGroup.objects.get(id=request.POST.get('ftp_server'))
            # Связываем записи
            ftp_server.backupgroup_set.add(group, bulk=False)
            # if not os.path.exists(os.path.join(get_backup_dir(), request.POST.get('group'))):
            #     os.mkdir(os.path.join(get_backup_dir(), request.POST.get('group')), mode=0o777)
            return HttpResponsePermanentRedirect("/backup_groups")
        else:
            return render(request, "device_control/backup_group_edit.html", {"form": backup_group_form})
    except AuthGroup.DoesNotExist:
        return HttpResponseNotFound("<h2>Данная группа не найдена!</h2>")


@login_required(login_url='accounts/login/')
def backup_group_delete(request, bg_id):
    if not check_superuser(request):
        return HttpResponsePermanentRedirect('/')

    try:
        group = BackupGroup.objects.get(id=bg_id)
        if os.path.exists(os.path.join(get_backup_dir(), group.backup_group)) and \
                not os.listdir(os.path.join(get_backup_dir(), group.backup_group)):  # Если папка пустая, то удаляем
            os.rmdir(os.path.join(get_backup_dir(), group.backup_group))
        group.delete()
        return HttpResponsePermanentRedirect('/backup_groups')
    except AuthGroup.DoesNotExist:
        return HttpResponseNotFound("<h2>Данная группа не найдена!</h2>")


@login_required(login_url='accounts/login/')
def devices(request):
    if not check_superuser(request):
        return HttpResponsePermanentRedirect('/')

    devices_all = Equipment.objects.all()
    for d in devices_all:
        if d.auth_group_id:
            d.auth_group_id = AuthGroup.objects.get(id=d.auth_group_id).auth_group
        if d.backup_group_id:
            d.backup_group_id = BackupGroup.objects.get(id=d.backup_group_id).backup_group

    sorted_by = request.GET.get('sorted')
    sorted_order = request.GET.get('sortorder')
    devices_all = sorted(
        [
            {
                'id': d.id,
                'ip': d.ip,
                'device_name': d.device_name,
                'vendor': d.vendor,
                'protocol': d.protocol,
                'auth_group_id': d.auth_group_id,
                'backup_group_id': d.backup_group_id
            }
            for d in devices_all
        ],
        key=lambda x: x[sorted_by or 'device_name'],
        reverse=True if sorted_order == 'up' else False
    )
    return render(
        request,
        "device_control/devices.html",
        {
            "devices": devices_all,
            "sorted_by": sorted_by,
            "sorted_order": sorted_order
        }
    )


@login_required(login_url='accounts/login/')
def device_edit(request, id: int = 0):
    if not check_superuser(request):
        return HttpResponsePermanentRedirect('/')

    check_superuser(request)
    try:

        if id:  # Если редактируем существующую запись
            device = Equipment.objects.get(id=id)   # Запись, которую необходимо редактировать
            # В форме задаем начальные значения, равные текущим сохраненным
            device_form = DevicesForm(initial={
                'ip': device.ip,
                'device_name': device.device_name,
                'vendor': device.vendor,
                'protocol': device.protocol,
                'auth_group': device.auth_group,
                'backup_group': device.backup_group
            })
        else:   # Если запись новая
            device_form = DevicesForm()     # Пустая форма
            device = Equipment()            # Создаем экземпляр для записи

        if request.method == "POST":
            # Заполняем данные, которые были переданы
            device.ip = request.POST.get('ip')
            device.device_name = request.POST.get('device_name')
            device.vendor = request.POST.get('vendor')
            device.protocol = request.POST.get('protocol')
            device.save()  # Сохраняем запись
            # Определяем группу Авторизации, согласно её переданному id
            auth_group = AuthGroup.objects.get(id=request.POST.get('auth_group'))
            # Связываем записи
            auth_group.equipment_set.add(device, bulk=False)
            backup_group = BackupGroup.objects.get(id=request.POST.get('backup_group'))
            backup_group.equipment_set.add(device, bulk=False)
            return HttpResponsePermanentRedirect("/devices")
        else:

            return render(request, "device_control/device_edit.html", {"form": device_form})
    except AuthGroup.DoesNotExist or BackupGroup.DoesNotExist:
        return HttpResponseNotFound("<h2>Данная группа не найдена!</h2>")


@login_required(login_url='accounts/login/')
def device_delete(request, id):
    if not check_superuser(request):
        return HttpResponsePermanentRedirect('/')

    check_superuser(request)
    try:
        group = Equipment.objects.get(id=id)
        group.delete()
        return HttpResponsePermanentRedirect('/devices')
    except AuthGroup.DoesNotExist:
        return HttpResponseNotFound("<h2>Данная группа не найдена!</h2>")


@login_required(login_url='accounts/login/')
def users(request):
    if not check_superuser(request):
        return HttpResponsePermanentRedirect('/')

    u = User.objects.all()
    return render(request, "user_control/users.html", {"users": u})


@login_required(login_url='accounts/login/')
def user_access_edit(request, username):
    if not check_superuser(request):
        return HttpResponsePermanentRedirect('/')

    if request.method == 'GET':
        if not username:
            return HttpResponsePermanentRedirect('/users')

        gr = BackupGroup.objects.all()
        backup_groups = {}
        for g in gr:
            # Проверяем, доступна ли данная группа у пользователя
            try:
                is_enable = BackupGroup.objects.get(backup_group=g.backup_group).users.get(username=username)
            except Exception:
                is_enable = 0
            backup_groups[g.backup_group] = is_enable
        return render(
            request,
            'user_control/user_access_group.html',
            {
                'username': username,
                'backup_groups': backup_groups
            }
        )

    elif request.method == 'POST':
        gr = BackupGroup.objects.all()  # Все backup_groups
        user = User.objects.get(username=username)  # Пользователь
        for g in gr:
            backup_gr = BackupGroup.objects.get(backup_group=g.backup_group)

            if request.POST.get(g.backup_group):    # Если данная группа была выбрана

                user.backupgroup_set.add(backup_gr)  # Добавляем пользователя в группу
            else:
                user.backupgroup_set.remove(backup_gr)  # Удаляем

        return HttpResponsePermanentRedirect('/users')
