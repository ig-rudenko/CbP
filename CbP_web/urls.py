"""CbP_web URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/3.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from cbp.views import *

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('django.contrib.auth.urls')),
    path('', config_files_view.home, name='home'),

    # AUTH GROUP
    path('auth_groups', auth_group_view.auth_groups),
    path('auth_group/edit/<int:id>', auth_group_view.auth_group_edit),
    path('auth_group/edit', auth_group_view.auth_group_edit),
    path('auth_group/delete/<int:id>', auth_group_view.auth_group_delete),

    # BACKUP GROUP
    path('backup_groups', backup_group_view.backup_groups),
    path('backup_group/edit', backup_group_view.backup_group_edit),
    path('backup_group/edit/<int:bg_id>', backup_group_view.backup_group_edit),
    path('backup_group/delete/<int:bg_id>', backup_group_view.backup_group_delete),

    # DEVICES
    path('devices', devices_view.devices),
    path('device/edit/<int:id>', devices_view.device_edit),
    path('device/edit', devices_view.device_edit),
    path('device/delete/<int:id>', devices_view.device_delete),

    # DEVICE CONFIG FILES
    path('config', config_files_view.list_config_files),
    path('download', config_files_view.download_file_),
    path('show', config_files_view.show_config_file),

    # USER CONTROL
    path('users', user_control_view.users),
    path('users/<str:username>', user_control_view.user_access_edit),

    # DELETE FILE
    path('delete_file', config_files_view.delete_file),

    # ZABBIX
    path('zabbix/groups', zabbix_view.get_groups),

    # BACKUP CONTROL
    path('backup_control', backup_control_view.show_logs),
    path('backup_control/logs', backup_control_view.show_logs),
    path('backup_control/tasks', backup_control_view.tasks),

    # AJAX
    path('backup_control/ajax/logs', backup_control_view.get_logs),

    # FTP SERVERS
    path('ftp_servers', ftp_servers_views.ftp_servers),
    path('ftp_servers/edit', ftp_servers_views.ftp_servers_edit),
    path('ftp_servers/edit/<int:fs_id>', ftp_servers_views.ftp_servers_edit),
    path('ftp_servers/delete/<int:fs_id>', ftp_servers_views.ftp_server_delete),
]
