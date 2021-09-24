from django.shortcuts import render
from django.contrib.auth.models import User
from django.http import HttpResponsePermanentRedirect, HttpResponseNotFound
from django.contrib.auth.decorators import login_required
import configparser
from cbp.core import logs
from cbp.models import FtpGroup, BackupGroup
from cbp.forms import FtpServersForm
import sys


def check_superuser(request):
    try:
        if not User.objects.get(username=str(request.user)).is_superuser:
            return 0
        else:
            return 1
    except Exception:
        return 0


@login_required(login_url='accounts/login/')
def ftp_servers(request):
    if not check_superuser(request):
        return HttpResponsePermanentRedirect('/')
    ftp_servers_all = FtpGroup.objects.all()
    return render(request, "backup_control/ftp_servers.html", {"ftp_servers": ftp_servers_all})


@login_required(login_url='accounts/login/')
def ftp_server_delete(request, fs_id):
    try:
        if not check_superuser(request):
            return HttpResponsePermanentRedirect('/')
        fs = FtpGroup.objects.get(id=fs_id)
        fs.delete()
        return HttpResponsePermanentRedirect('/ftp_servers')
    except FtpGroup.DoesNotExist:
        return HttpResponseNotFound("<h2>Данная группа не найдена!</h2>")


def ftp_servers_edit(request, fs_id: int = 0):
    try:
        if fs_id:
            ftp_server = FtpGroup.objects.get(id=fs_id)
            ftp_server_form = FtpServersForm(initial={
                'name': ftp_server.name,
                'ip': ftp_server.host,
                'login': ftp_server.login,
                'password': ftp_server.password,
                'workdir': ftp_server.workdir,
            })
        else:
            ftp_server_form = FtpServersForm()
            ftp_server = FtpGroup()

        if request.method == "POST":
            ftp_server.name = request.POST.get('name')
            ftp_server.host = request.POST.get('ip')
            ftp_server.login = request.POST.get('login')
            ftp_server.password = request.POST.get('password')
            ftp_server.workdir = request.POST.get('workdir')
            ftp_server.save()

            return HttpResponsePermanentRedirect("/ftp_servers")
        else:
            return render(request, "backup_control/ftp_servers_edit.html", {"form": ftp_server_form})
    except FtpGroup.DoesNotExist or BackupGroup.DoesNotExist:
        return HttpResponseNotFound("<h2>Данная группа не найдена!</h2>")
