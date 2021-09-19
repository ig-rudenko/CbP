from django.shortcuts import render
from django.contrib.auth.models import User
from django.http import HttpResponsePermanentRedirect
from django.contrib.auth.decorators import login_required
from pyzabbix import ZabbixAPI
import configparser
from cbp.core import logs
from cbp.models import AuthGroup, BackupGroup, Equipment
import sys


def check_superuser(request):
    try:
        if not User.objects.get(username=str(request.user)).is_superuser:
            return 0
        else:
            return 1
    except Exception:
        return 0


def get_zabbix_config():
    try:
        cfg = configparser.ConfigParser()
        cfg.read(f'{sys.path[0]}/cbp.conf')
        return {
            'host': cfg.get('zabbix', 'host'),
            'user': cfg.get('zabbix', 'user'),
            'password': cfg.get('zabbix', 'password')
        }
    except Exception as error:
        logs.critical_log.critical(error)


@login_required(login_url='accounts/login/')
def get_groups(request):
    if not check_superuser(request):
        return HttpResponsePermanentRedirect('/')

    zbx_auth = get_zabbix_config()
    try:
        zbx = ZabbixAPI(server=zbx_auth['host'])
        zbx.login(zbx_auth['user'], zbx_auth['password'])

        if request.GET.get('g'):

            def device_exist(ips, devices):
                for ip in ips:
                    if ip['ip'] in devices:
                        return 1
                return 0

            if request.method == 'GET':
                # Просмотр узлов сети Zabbix в группе
                zbx_hosts = zbx.host.get(
                    groupids=int(request.GET.get('g')),
                    output=['interfaces', 'name', 'status'],
                    selectInterfaces=['ip']
                )
                devices_all = Equipment.objects.all()

                hosts = [
                    {
                        'hostid': line['hostid'],
                        'name': line['name'],
                        'ip': line['interfaces'][0]['ip'],
                        'status': device_exist(line['interfaces'], [d.ip for d in devices_all])
                    }
                    for line in zbx_hosts
                ]
                return render(
                    request,
                    'zabbix/zabbix_hosts.html',
                    {
                        'hosts': hosts,
                        'superuser': check_superuser(request),
                        'group_name': request.GET.get('gn')
                    }
                )
            elif request.method == 'POST':
                # Добавление узлов сети из Zabbix в базу данных
                hosts_ids = list(request.POST.keys())[1:]   # Отмеченные узлы сети на странице
                zbx_hosts = zbx.host.get(
                    groupids=int(request.GET.get('g')),
                    hostids=hosts_ids,
                    output=['interfaces', 'name', 'status'],
                    selectInterfaces=['ip']
                )

                for host in zbx_hosts:
                    device = Equipment()
                    device.ip = host['interfaces'][0]['ip']
                    device.device_name = host['name']
                    device.vendor = ''
                    device.protocol = 'telnet'
                    device.save()
                    auth_group = AuthGroup.objects.first()
                    auth_group.equipment_set.add(device, bulk=False)
                    backup_group = BackupGroup.objects.first()
                    backup_group.equipment_set.add(device, bulk=False)
                return HttpResponsePermanentRedirect(f"groups?g={int(request.GET.get('g'))}&gn={request.GET.get('gn')}")

        # Просмотр групп узлов сети Zabbix
        groups = zbx.hostgroup.get()
        return render(
            request,
            "zabbix/zabbix_groups.html",
            {
                'groups': groups,
                'superuser': check_superuser(request)
            }
        )

    except Exception as error:
        logs.critical_log.critical(error)
        return render(
            request,
            "zabbix/zabbix_groups.html",
            {
                'groups': [],
                'superuser': check_superuser(request)
            }
        )
