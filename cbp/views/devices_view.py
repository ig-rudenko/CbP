from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseNotFound, HttpResponsePermanentRedirect
from cbp.forms import DevicesForm
from cbp.models import AuthGroup, BackupGroup, Equipment
from cbp.views.user_checks import check_superuser


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
