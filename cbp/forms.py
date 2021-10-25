from django import forms
from .models import AuthGroup, BackupGroup, FtpGroup
from django.utils.safestring import mark_safe


class FtpModelChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return obj.name


class AuthModelChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return obj.auth_group


class BackupModelChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return obj.backup_group


class FtpServersForm(forms.Form):
    name = forms.CharField(max_length=50, label='Имя сервера')
    ip = forms.GenericIPAddressField(label='IP адрес')
    login = forms.CharField(max_length=50, label='Имя пользователя')
    password = forms.CharField(max_length=50, label='Пароль пользователя')
    workdir = forms.CharField(max_length=255, label='Рабочая директория')
    protocol = forms.ChoiceField(
        choices=[('FTP', 'FTP'), ('SFTP', 'SFTP')],
        label='Тип протокола для подключения'
    )
    sftp_port = forms.IntegerField(min_value=1, max_value=65535, label='Порт для подключения (только для SFTP)')


class AuthGroupsForm(forms.Form):
    group = forms.CharField(max_length=50, label='Имя группы')
    login = forms.CharField(max_length=50, label='Имя пользователя')
    password = forms.CharField(max_length=50, label='Пароль пользователя')
    privilege_mode_password = forms.CharField(max_length=50, label='Пароль от привилегированного режима', required=False)


class BackupGroupsForm(forms.Form):
    group = forms.CharField(max_length=50, label='Уникальное имя папки, для сохранения файлов конфигураций')
    ftp_server = FtpModelChoiceField(
        required=True,
        widget=forms.Select,
        queryset=FtpGroup.objects.all(),
        label=mark_safe('<a class="no_decoration" href="/ftp_servers">Удаленный FTP сервер ⭐</a>')
    )


class DevicesForm(forms.Form):
    ip = forms.GenericIPAddressField(label='IP адрес')
    device_name = forms.CharField(max_length=50, label='Имя устройства')
    vendor = forms.CharField(max_length=50, label='Vendor: (Cisco, Huawei и т.д.)', required=False)
    protocol = forms.ChoiceField(
        choices=[('telnet', 'telnet'), ('ssh', 'ssh')],
        label='Тип протокола для подключения'
    )
    auth_group = AuthModelChoiceField(
        required=True,
        widget=forms.Select,
        queryset=AuthGroup.objects.all(),
        label=mark_safe('<a class="no_decoration" href="/auth_groups">Группа Авторизации ⭐</a>')
    )

    backup_group = BackupModelChoiceField(
        required=True,
        widget=forms.Select,
        queryset=BackupGroup.objects.all(),
        label=mark_safe('<a class="no_decoration" href="/backup_groups">Группа Бэкапа ⭐</a>')
    )
