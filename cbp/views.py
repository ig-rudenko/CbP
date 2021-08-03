from django.shortcuts import render
from django.contrib.auth.models import User
from django.core.files.storage import FileSystemStorage
from django.http import HttpResponse, HttpResponseNotFound, HttpResponsePermanentRedirect
from .forms import AuthGroupsForm, BackupGroupsForm, DevicesForm
from .models import AuthGroup, BackupGroup, Equipment
from configparser import ConfigParser
import sys
import os
from datetime import datetime


def get_create_time(file):
    return os.stat(file).st_atime


def get_backup_dir():
    cfg = ConfigParser()
    cfg.read(f'{sys.path[0]}/config')
    return cfg.get('dirs', 'backup_dir')  # Директория сохранения файлов конфигураций


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


def home(request):
    if str(request.user) == 'AnonymousUser':
        return HttpResponsePermanentRedirect('accounts/login/')

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

        dirs_list = {}
        backup_dir = get_backup_dir()
        for backup_group in os.listdir(backup_dir):   # Проходимся по элементам в директории для бэкапа

            if backup_group not in available_backup_groups and not current_user.is_superuser:
                print(backup_group)
                continue  # Пропускаем те группы, которые недопустимы

            backup_group_path = os.path.join(backup_dir, backup_group)
            if os.path.isdir(backup_group_path):     # Если найдена папка
                # if os.listdir(str(backup_group_path)):    # Если папка с профилем не пустая
                dirs_list[backup_group] = {}
                for dev in os.listdir(backup_group_path):
                    # группа.имя_устройства = кол-во сохраненных файлов конфигураций
                    if not os.path.isdir(os.path.join(backup_group_path, dev)):
                        continue
                    dirs_list[backup_group][dev] = [len(os.listdir(os.path.join(backup_group_path, dev)))]
                    # /backup_dir/backup_group/device_name/
                    config_files = os.listdir(os.path.join(backup_group_path, dev))
                    # Оставляем только файлы
                    config_files = [os.path.join(backup_group_path, dev, f)
                                    for f in config_files if os.path.isfile(os.path.join(backup_group_path, dev, f))]
                    if not config_files:
                        continue
                    # Ищем самый новый
                    last_date = os.stat(max(config_files, key=get_create_time)).st_mtime

                    dirs_list[backup_group][dev] += [datetime.fromtimestamp(last_date).strftime('%-d %b %Y %X')]
        return render(
            request,
            'home.html',
            {
                "form": dirs_list,
                'superuser': check_superuser(request)
            }
        )
    elif request.method == 'POST':

        groups = [g.backup_group for g in BackupGroup.objects.all()]
        for g in groups:
            if request.POST.get(g):
                try:
                    os.mkdir(f"{get_backup_dir()}/{g}/{request.POST.get(g)}", mode=0o777)
                except FileExistsError:
                    pass
        return HttpResponsePermanentRedirect('/')


def download_file(request):
    if str(request.user) == 'AnonymousUser':
        return HttpResponsePermanentRedirect('accounts/login/')

    current_user = User.objects.get(username=str(request.user))  # Текущий пользователь
    available_backup_groups = [g.backup_group for g in
                               BackupGroup.objects.filter(users__username=current_user.username)]

    if (not available_backup_groups or str(request.GET.get('bg')) not in available_backup_groups) \
            and not current_user.is_superuser:
        return HttpResponsePermanentRedirect('/')

    backup_dir = get_backup_dir()
    file_path = os.path.join(backup_dir, request.GET.get('bg'), request.GET.get('dn'), request.GET.get('fn'))
    if os.path.exists(file_path):
        with open(file_path, 'rb') as fh:
            response = HttpResponse(fh.read(), content_type="application/vnd.ms-excel")
            response['Content-Disposition'] = 'inline; filename=' + os.path.basename(file_path)
            return response


def list_config_files(request):
    if str(request.user) == 'AnonymousUser':
        return HttpResponsePermanentRedirect('accounts/login/')

    if request.method == 'GET':
        current_user = User.objects.get(username=str(request.user))  # Текущий пользователь
        available_backup_groups = [g.backup_group for g in
                                   BackupGroup.objects.filter(users__username=current_user.username)]

        if (not available_backup_groups or str(request.GET.get('bg')) not in available_backup_groups) \
                and not current_user.is_superuser:
            return HttpResponsePermanentRedirect('/')

        backup_group = request.GET.get('bg')
        device_name = request.GET.get('dn')
        config_files = []
        backup_dir = get_backup_dir()
        config_files_dir = os.path.join(backup_dir, backup_group, device_name)
        config_files_list = os.listdir(config_files_dir)
        # Полный путь до файлов конфигураций
        config_files_list = [os.path.join(config_files_dir, f)
                             for f in config_files_list
                             if os.path.isfile(os.path.join(config_files_dir, f))]

        config_files_list = sorted(config_files_list, key=get_create_time)
        config_files_list.reverse()
        for file in config_files_list:
            date_file = os.stat(file).st_mtime
            config_files.append([os.path.split(file)[1], datetime.fromtimestamp(date_file).strftime('%-d %b %Y %X')])
        return render(request, 'devices_config_list.html',
                          {
                              "form": config_files,
                              "backup_group": backup_group,
                              "device_name": device_name,
                              "superuser": check_superuser(request)
                          }
                      )

    # ЗАГРУЗКА ФАЙЛА
    elif request.method == 'POST' and request.FILES.get('file'):
        with open(
                os.path.join(
                    get_backup_dir(),
                    request.POST.get("backup_group"),
                    request.POST.get("device_name"),
                    str(request.FILES["file"].name).replace(" ", "_")),
                'wb+'
        ) as new_file:
            for chunk_ in request.FILES['file'].chunks():
                new_file.write(chunk_)
        return HttpResponsePermanentRedirect(f'/config?bg={request.POST.get("backup_group")}&dn={request.POST.get("device_name")}')


    else:
        return HttpResponsePermanentRedirect(f'/config?bg={request.POST.get("backup_group")}&dn={request.POST.get("device_name")}')


def show_config_file(request):
    if str(request.user) == 'AnonymousUser':
        return HttpResponsePermanentRedirect('accounts/login/')

    current_user = User.objects.get(username=str(request.user))  # Текущий пользователь
    available_backup_groups = [g.backup_group for g in
                               BackupGroup.objects.filter(users__username=current_user.username)]

    if (not available_backup_groups or str(request.GET.get('bg')) not in available_backup_groups) \
            and not current_user.is_superuser:
        return HttpResponsePermanentRedirect('/')

    backup_group = request.GET.get('bg')
    device_name = request.GET.get('dn')
    config_file_name = request.GET.get('fn')
    backup_dir = get_backup_dir()
    if not os.path.exists(os.path.join(backup_dir, backup_group, device_name, config_file_name)) or \
        not os.path.isfile(os.path.join(backup_dir, backup_group, device_name, config_file_name)):
        file_output = ''
    else:
        try:
            with open(os.path.join(backup_dir, backup_group, device_name, config_file_name)) as file:
                file_output = file.read()
        except UnicodeDecodeError:
            file_output = 'Невозможно прочитать данный файл в виде текста'
    return render(request, 'devices_config_show.html',
                      {
                          "form": file_output,
                          "device_name": device_name,
                          "backup_group": backup_group,
                          "superuser": check_superuser(request)
                      }
                  )


def delete_file(request):
    if str(request.user) == 'AnonymousUser':
        return HttpResponsePermanentRedirect('accounts/login/')

    if not check_superuser(request):
        return HttpResponsePermanentRedirect('/')

    if request.method == 'GET':
        backup_group = request.GET.get('bg')
        device_name = request.GET.get('dn')
        file_name = request.GET.get('fn')

        if os.path.exists(os.path.join(get_backup_dir(), backup_group, device_name, file_name)):

            os.remove(os.path.join(get_backup_dir(), backup_group, device_name, file_name))
            # except Exception:
            #     pass

        return HttpResponsePermanentRedirect(f'config?bg={backup_group}&dn={device_name}')

    else:
        return HttpResponsePermanentRedirect('/')


def auth_groups(request):
    if str(request.user) == 'AnonymousUser':
        return HttpResponsePermanentRedirect('accounts/login/')

    if not check_superuser(request):
        return HttpResponsePermanentRedirect('/')

    groups = AuthGroup.objects.all()
    return render(request, "device_control/auth_groups.html", {"form": AuthGroupsForm, "groups": groups})


def auth_group_edit(request, id: int = 0):
    if str(request.user) == 'AnonymousUser':
        return HttpResponsePermanentRedirect('accounts/login/')

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


def auth_group_delete(request, id):
    if str(request.user) == 'AnonymousUser':
        return HttpResponsePermanentRedirect('accounts/login/')

    if not check_superuser(request):
        return HttpResponsePermanentRedirect('/')

    try:
        group = AuthGroup.objects.get(id=id)
        group.delete()
        return HttpResponsePermanentRedirect('/auth_groups')
    except AuthGroup.DoesNotExist:
        return HttpResponseNotFound("<h2>Данная группа не найдена!</h2>")


def backup_groups(request):
    if str(request.user) == 'AnonymousUser':
        return HttpResponsePermanentRedirect('accounts/login/')

    if not check_superuser(request):
        return HttpResponsePermanentRedirect('/')

    groups = BackupGroup.objects.all()
    return render(request, "device_control/backup_groups.html", {"form": BackupGroupsForm, "groups": groups})


def backup_group_edit(request, id: int = 0):
    if str(request.user) == 'AnonymousUser':
        return HttpResponsePermanentRedirect('accounts/login/')

    if not check_superuser(request):
        return HttpResponsePermanentRedirect('/')

    try:
        backup_group_form = BackupGroupsForm()
        if id:
            group = BackupGroup.objects.get(id=id)
            backup_group_form = BackupGroupsForm(initial={
                'group': group.backup_group
            })
        else:
            group = BackupGroup()

        if request.method == "POST":
            group.backup_group = request.POST.get('group')
            group.save()
            if not os.path.exists(os.path.join(get_backup_dir(), request.POST.get('group'))):
                os.mkdir(os.path.join(get_backup_dir(), request.POST.get('group')), mode=0o777)
            return HttpResponsePermanentRedirect("/backup_groups")
        else:
            return render(request, "device_control/backup_group_edit.html", {"form": backup_group_form})
    except AuthGroup.DoesNotExist:
        return HttpResponseNotFound("<h2>Данная группа не найдена!</h2>")


def backup_group_delete(request, id):
    if str(request.user) == 'AnonymousUser':
        return HttpResponsePermanentRedirect('accounts/login/')

    if not check_superuser(request):
        return HttpResponsePermanentRedirect('/')

    try:
        group = BackupGroup.objects.get(id=id)
        if os.path.exists(os.path.join(get_backup_dir(), group.backup_group)) and \
                not os.listdir(os.path.join(get_backup_dir(), group.backup_group)):  # Если папка пустая, то удаляем
            os.rmdir(os.path.join(get_backup_dir(), group.backup_group))
        group.delete()
        return HttpResponsePermanentRedirect('/backup_groups')
    except AuthGroup.DoesNotExist:
        return HttpResponseNotFound("<h2>Данная группа не найдена!</h2>")


def devices(request):
    if str(request.user) == 'AnonymousUser':
        return HttpResponsePermanentRedirect('accounts/login/')

    if not check_superuser(request):
        return HttpResponsePermanentRedirect('/')

    devices_all = Equipment.objects.all()
    for d in devices_all:
        if d.auth_group_id:
            d.auth_group_id = AuthGroup.objects.get(id=d.auth_group_id).auth_group
        if d.backup_group_id:
            d.backup_group_id = BackupGroup.objects.get(id=d.backup_group_id).backup_group
    return render(request, "device_control/devices.html", {"devices": devices_all})


def device_edit(request, id: int = 0):
    if str(request.user) == 'AnonymousUser':
        return HttpResponsePermanentRedirect('accounts/login/')

    if not check_superuser(request):
        return HttpResponsePermanentRedirect('/')

    check_superuser(request)
    try:

        if id:
            device = Equipment.objects.get(id=id)
            device_form = DevicesForm(initial={
                'ip': device.ip,
                'device_name': device.device_name,
                'vendor': device.vendor
            })
        else:
            device_form = DevicesForm()
            device = Equipment()

        if request.method == "POST":
            device.ip = request.POST.get('ip')
            device.device_name = request.POST.get('device_name')
            device.vendor = request.POST.get('vendor')
            device.save()
            auth_group = AuthGroup.objects.get(id=request.POST.get('auth_group'))
            auth_group.equipment_set.add(device, bulk=False)
            backup_group = BackupGroup.objects.get(id=request.POST.get('backup_group'))
            backup_group.equipment_set.add(device, bulk=False)
            return HttpResponsePermanentRedirect("/devices")
        else:

            return render(request, "device_control/device_edit.html", {"form": device_form})
    except AuthGroup.DoesNotExist or BackupGroup.DoesNotExist:
        return HttpResponseNotFound("<h2>Данная группа не найдена!</h2>")


def device_delete(request, id):
    if str(request.user) == 'AnonymousUser':
        return HttpResponsePermanentRedirect('accounts/login/')

    if not check_superuser(request):
        return HttpResponsePermanentRedirect('/')

    check_superuser(request)
    try:
        group = Equipment.objects.get(id=id)
        group.delete()
        return HttpResponsePermanentRedirect('/devices')
    except AuthGroup.DoesNotExist:
        return HttpResponseNotFound("<h2>Данная группа не найдена!</h2>")


def users(request):
    if str(request.user) == 'AnonymousUser':
        return HttpResponsePermanentRedirect('accounts/login/')

    if not check_superuser(request):
        return HttpResponsePermanentRedirect('/')

    u = User.objects.all()
    return render(request, "user_control/users.html", {"users": u})


def user_access_edit(request, username):
    if str(request.user) == 'AnonymousUser':
        return HttpResponsePermanentRedirect('accounts/login/')

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
