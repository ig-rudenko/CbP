from django.shortcuts import render
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.http import HttpResponsePermanentRedirect
from cbp.models import BackupGroup


@login_required(login_url='accounts/login/')
def users(request):
    if not request.user.is_superuser:
        return HttpResponsePermanentRedirect('/')
    authenticate()
    u = User.objects.all()
    return render(request, "user_control/users.html", {"users": u})


@login_required(login_url='accounts/login/')
def user_access_edit(request, username):
    if not request.user.is_superuser:
        return HttpResponsePermanentRedirect('/')

    if request.method == 'GET':
        if not username:
            return HttpResponsePermanentRedirect('/users')

        data = {}

        for bg in BackupGroup.objects.all():
            try:
                is_enable = BackupGroup.objects.get(id=bg.id).users.get(username=username)
            except Exception:
                is_enable = 0

            data[bg.id] = {
                'name': bg.backup_group,
                'checked': is_enable,
                'ftp_servers': []
            }

            for fs in BackupGroup.objects.get(id=bg.id).ftp_server.all():
                data[bg.id]['ftp_servers'].append(fs)

        return render(
            request,
            'user_control/user_access_group.html',
            {
                'username': username,
                'data': data
            }
        )

    elif request.method == 'POST':
        user = User.objects.get(username=username)  # Пользователь
        for g in BackupGroup.objects.all():
            backup_gr = BackupGroup.objects.get(id=g.id)
            print(backup_gr.backup_group)
            if request.POST.get(f'bg_id_{g.id}'):    # Если данная группа была выбрана
                user.backupgroup_set.add(backup_gr)  # Добавляем пользователя в группу
            else:
                user.backupgroup_set.remove(backup_gr)  # Удаляем

        return HttpResponsePermanentRedirect('/users')
