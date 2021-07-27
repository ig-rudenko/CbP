from django import forms
from .models import AuthGroup, BackupGroup


class Form(forms.Form):
    file = forms.FilePathField(path=f'/home/irudenko/PycharmProjects/CbP/')


class AuthGroupsForm(forms.Form):
    group = forms.CharField(max_length=50, label='Имя группы')
    login = forms.CharField(max_length=50, label='Имя пользователя')
    password = forms.CharField(max_length=50, label='Пароль пользователя')
    privilege_mode_password = forms.CharField(max_length=50, label='Пароль от привилегированного режима', required=False)


class BackupGroupsForm(forms.Form):
    group = forms.CharField(max_length=50, label='Имя папки, для сохранения')


class DevicesForm(forms.Form):

    ip = forms.GenericIPAddressField(label='IP адрес')
    device_name = forms.CharField(max_length=50, label='Имя устройства')
    vendor = forms.CharField(max_length=50, label='Vendor: (Cisco, Huawei и т.д.)', required=False)
    auth_list = [(g.auth_group, g.auth_group) for g in AuthGroup.objects.all()]
    auth_group = forms.ChoiceField(choices=(tuple(auth_list)))
    backup_list = [(g.backup_group, g.backup_group) for g in BackupGroup.objects.all()]
    backup_group = forms.ChoiceField(choices=(tuple(backup_list)))
