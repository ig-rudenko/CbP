from django.shortcuts import render
from django.contrib.auth.models import User
from django.http import HttpResponse, HttpResponseNotFound, HttpResponsePermanentRedirect
from .forms import HomeForm, AuthGroupsForm, BackupGroupsForm, DevicesForm
from .models import AuthGroup, BackupGroup, Equipment
from configparser import ConfigParser
import sys
import os
from re import findall
from datetime import date


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

    current_user = User.objects.get(username=str(request.user))  # Текущий пользователь
    available_backup_groups = [g.backup_group for g in BackupGroup.objects.filter(users__username=current_user.username)]
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
    cfg = ConfigParser()

    cfg.read(f'{sys.path[0]}/config')
    backup_dir = cfg.get('dirs', 'backup_dir')  # Директория сохранения файлов конфигураций
    for backup_group in os.listdir(backup_dir):   # Проходимся по элементам в директории для бэкапа

        if backup_group not in available_backup_groups and not current_user.is_superuser:
            print(backup_group)
            continue  # Пропускаем те группы, которые недопустимы

        backup_group_path = os.path.join(backup_dir, backup_group)
        if os.path.isdir(backup_group_path):     # Если найдена папка
            if os.listdir(str(backup_group_path)):    # Если папка с профилем не пустая
                dirs_list[backup_group] = {}
                for dev in os.listdir(backup_group_path):
                    # группа.имя_устройства = кол-во сохраненных файлов конфигураций
                    dirs_list[backup_group][dev] = [len(os.listdir(os.path.join(backup_group_path, dev)))]
                    last_date = ''
                    for conf_file in os.listdir(os.path.join(backup_group_path, dev)):  # Перебираем файлы конфигураций
                        if os.path.isfile(os.path.join(backup_group_path, dev, conf_file)):  # Если это файл
                            # Ищем самую новую конфигурацию
                            date_file = findall(r'(\d{4})-(\d{2})-(\d{2})', conf_file)
                            date_file = date(int(date_file[0][0]), int(date_file[0][1]), int(date_file[0][2]))
                            if not date_file:
                                continue
                            if not last_date or date_file > last_date:
                                last_date = date_file
                    dirs_list[backup_group][dev] += [last_date]
    return render(
        request,
        'home.html',
        {
            "form": dirs_list,
            'superuser': check_superuser(request)
        }
    )


def download_file(request):
    if str(request.user) == 'AnonymousUser':
        return HttpResponsePermanentRedirect('accounts/login/')

    current_user = User.objects.get(username=str(request.user))  # Текущий пользователь
    available_backup_groups = [g.backup_group for g in
                               BackupGroup.objects.filter(users__username=current_user.username)]

    if (not available_backup_groups or str(request.GET.get('bg')) not in available_backup_groups) \
            and not current_user.is_superuser:
        return HttpResponsePermanentRedirect('/')

    cfg = ConfigParser()
    cfg.read(f'{sys.path[0]}/config')
    backup_dir = cfg.get('dirs', 'backup_dir')  # Директория сохранения файлов конфигураций
    file_path = os.path.join(backup_dir, request.GET.get('bg'), request.GET.get('dn'), request.GET.get('fn'))
    if os.path.exists(file_path):
        with open(file_path, 'rb') as fh:
            response = HttpResponse(fh.read(), content_type="application/vnd.ms-excel")
            response['Content-Disposition'] = 'inline; filename=' + os.path.basename(file_path)
            return response


def list_config_files(request):
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
    cfg = ConfigParser()
    cfg.read(f'{sys.path[0]}/config')
    config_files = []
    backup_dir = cfg.get('dirs', 'backup_dir')  # Директория сохранения файлов конфигураций
    for file in os.listdir(os.path.join(backup_dir, backup_group, device_name)):
        if not os.path.isfile(os.path.join(backup_dir, backup_group, device_name, file)):
            continue
        date_file = findall(r'(\d{4})-(\d{2})-(\d{2})', file)
        date_file = date(int(date_file[0][0]), int(date_file[0][1]), int(date_file[0][2]))
        config_files.append([file, date_file])
    return render(request, 'devices_config_list.html',
                      {
                          "form": config_files,
                          "backup_group": backup_group,
                          "device_name": device_name
                      }
                  )


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
