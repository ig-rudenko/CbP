from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseNotFound, HttpResponsePermanentRedirect
from cbp.models import AuthGroup, BackupGroup, FtpGroup
from cbp.views.user_checks import check_superuser


@login_required(login_url='accounts/login/')
def backup_groups(request):
    if not check_superuser(request):
        return HttpResponsePermanentRedirect('/')

    groups = []
    backup_groups = BackupGroup.objects.all()
    for bg in backup_groups:
        ftp_servers = BackupGroup.objects.get(id=bg.id).ftp_server.all()
        # for fs in ftp_servers:
        groups.append({
            'backup_group': bg.backup_group,
            'ftp_servers': [f'{fs.name} ({fs.host})' for fs in ftp_servers],
            'id': bg.id
        })
        # ftp_server = FtpGroup.objects.get(id=bg.ftp_server_id)
        # bg.ftp_server_id = f"{ftp_server.name} ({ftp_server.host})"
    return render(
        request,
        "device_control/backup_groups.html",
        {
            "groups": groups
        }
    )


@login_required(login_url='accounts/login/')
def backup_group_edit(request, bg_id: int = 0):
    if not check_superuser(request):
        return HttpResponsePermanentRedirect('/')
    try:
        if request.method == "GET":
            ftp_servers = FtpGroup.objects.all()
            bg = BackupGroup.objects.get(id=bg_id).backup_group if bg_id else ''  # Имя группы, если имелось
            ftp_servers_form = []
            for fs in ftp_servers:
                try:
                    if bg_id:
                        is_checked = FtpGroup.objects.get(host=fs.host).backupgroup_set.get(backup_group=bg)
                    else:
                        is_checked = 0
                except Exception as e:
                    print(e)
                    is_checked = 0
                workdir = fs.workdir[1:] if fs.workdir.startswith('/') else fs.workdir
                workdir = workdir+'/' if not workdir.endswith('/') and len(workdir) > 0 else workdir
                ftp_servers_form.append({
                    'is_checked': is_checked,
                    'ip': fs.host,
                    'name': fs.name,
                    'id': fs.id,
                    'wd': workdir
                })
            return render(
                request,
                'device_control/backup_group_edit.html',
                {
                    'backup_group': {'name': bg, 'id': bg_id or 'new'},
                    'ftp_servers': ftp_servers_form,
                    'create_new': not bg_id
                }
            )

        if request.method == "POST":
            if request.POST.get('bg_id') == 'new':
                bg = BackupGroup()
                bg.backup_group = request.POST.get('bg')
                bg.save()
            else:
                bg = BackupGroup.objects.get(id=request.POST.get('bg_id'))
            for fs in FtpGroup.objects.all():
                if request.POST.get(f"{fs.name}_{fs.host}"):
                    fs.backupgroup_set.add(bg)
                else:
                    fs.backupgroup_set.remove(bg)

            return HttpResponsePermanentRedirect("/backup_groups")

    except AuthGroup.DoesNotExist:
        return HttpResponseNotFound("<h2>Данная группа не найдена!</h2>")


@login_required(login_url='accounts/login/')
def backup_group_delete(request, bg_id):
    if not check_superuser(request):
        return HttpResponsePermanentRedirect('/')

    try:
        group = BackupGroup.objects.get(id=bg_id)
        group.delete()
        return HttpResponsePermanentRedirect('/backup_groups')
    except AuthGroup.DoesNotExist:
        return HttpResponseNotFound("<h2>Данная группа не найдена!</h2>")

