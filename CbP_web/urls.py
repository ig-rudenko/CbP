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
from cbp.views import views, zabbix_view, backup_control_view

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('django.contrib.auth.urls')),
    path('test/', views.test),
    path('', views.home, name='home'),

    # AUTH GROUP
    path('auth_groups', views.auth_groups),
    path('auth_group/edit/<int:id>', views.auth_group_edit),
    path('auth_group/edit', views.auth_group_edit),
    path('auth_group/delete/<int:id>', views.auth_group_delete),

    # BACKUP GROUP
    path('backup_groups', views.backup_groups),
    path('backup_group/edit/<int:id>', views.backup_group_edit),
    path('backup_group/edit', views.backup_group_edit),
    path('backup_group/delete/<int:id>', views.backup_group_delete),

    # DEVICES
    path('devices', views.devices),
    path('device/edit/<int:id>', views.device_edit),
    path('device/edit', views.device_edit),
    path('device/delete/<int:id>', views.device_delete),

    # DEVICE CONFIG FILES
    path('config', views.list_config_files),
    path('download', views.download_file),
    path('show', views.show_config_file),

    # USER CONTROL
    path('users', views.users),
    path('users/<str:username>', views.user_access_edit),

    # DELETE FILE
    path('delete_file', views.delete_file),

    # ZABBIX
    path('zabbix/groups', zabbix_view.get_groups),

    # BACKUP CONTROL
    path('backup_control', backup_control_view.show_logs),
    path('backup_control/logs', backup_control_view.show_logs),
    path('backup_control/tasks', backup_control_view.show_logs),

    # AJAX
    path('backup_control/ajax/logs', backup_control_view.get_logs)
]
