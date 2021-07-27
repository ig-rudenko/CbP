from django.shortcuts import render
from django import forms
from django.http import HttpResponse, HttpResponseNotFound, HttpResponsePermanentRedirect
from .forms import Form, AuthGroupsForm, BackupGroupsForm, DevicesForm
from .models import AuthGroup, BackupGroup, Equipment


def index(request):
    if request.method == 'POST':
        file_to_read = request.POST.get('file')
        userform = Form()
        try:
            with open(file_to_read) as f:
                file = f.read()
        except UnicodeDecodeError:
            file = f"'utf-8' codec can't decode file: {file_to_read}"
        return render(request, 'index.html', {"form": userform, "file": file})
    else:
        userform = Form()
        return render(request, 'index.html', {"form": userform, "file": ''})


def auth_groups(request):
    groups = AuthGroup.objects.all()
    return render(request, "auth_groups.html", {"form": AuthGroupsForm, "groups": groups})


def auth_group_edit(request, id: int = 0):
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
            return render(request, "auth_group_new.html", {"form": auth_group_form})
    except AuthGroup.DoesNotExist:
        return HttpResponseNotFound("<h2>Данная группа не найдена!</h2>")


def auth_group_delete(request, id):
    try:
        group = AuthGroup.objects.get(id=id)
        group.delete()
        return HttpResponsePermanentRedirect('/auth_groups')
    except AuthGroup.DoesNotExist:
        return HttpResponseNotFound("<h2>Данная группа не найдена!</h2>")


def backup_groups(request):
    groups = BackupGroup.objects.all()
    return render(request, "backup_groups.html", {"form": BackupGroupsForm, "groups": groups})


def backup_group_edit(request, id: int = 0):
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
            return render(request, "backup_group_edit.html", {"form": backup_group_form})
    except AuthGroup.DoesNotExist:
        return HttpResponseNotFound("<h2>Данная группа не найдена!</h2>")


def backup_group_delete(request, id):
    try:
        group = BackupGroup.objects.get(id=id)
        group.delete()
        return HttpResponsePermanentRedirect('/backup_groups')
    except AuthGroup.DoesNotExist:
        return HttpResponseNotFound("<h2>Данная группа не найдена!</h2>")


def devices(request):
    devices_all = Equipment.objects.all()
    for d in devices_all:
        d.auth_group_id = AuthGroup.objects.get(id=d.auth_group_id).auth_group
        d.backup_group_id = BackupGroup.objects.get(id=d.backup_group_id).backup_group
    return render(request, "devices.html", {"devices": devices_all})


def device_edit(request, id: int = 0):
    try:
        device_form = DevicesForm()
        if id:
            device = Equipment.objects.get(id=id)
            device_form = DevicesForm(initial={
                'ip': device.ip,
                'device_name': device.device_name,
                'vendor': device.vendor
            })
        else:
            device = Equipment()

        if request.method == "POST":
            device.ip = request.POST.get('ip')
            device.device_name = request.POST.get('device_name')
            device.vendor = request.POST.get('vendor')
            device.save()
            auth_group = AuthGroup.objects.get(auth_group=request.POST.get('auth_group'))
            auth_group.equipment_set.add(device, bulk=False)
            backup_group = BackupGroup.objects.get(backup_group=request.POST.get('backup_group'))
            backup_group.equipment_set.add(device, bulk=False)
            return HttpResponsePermanentRedirect("/devices")
        else:

            return render(request, "device_edit.html", {"form": device_form})
    except AuthGroup.DoesNotExist:
        return HttpResponseNotFound("<h2>Данная группа не найдена!</h2>")


def device_delete(request, id):
    try:
        group = Equipment.objects.get(id=id)
        group.delete()
        return HttpResponsePermanentRedirect('/devices')
    except AuthGroup.DoesNotExist:
        return HttpResponseNotFound("<h2>Данная группа не найдена!</h2>")