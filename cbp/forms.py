from django import forms
from .models import AuthGroup, BackupGroup


class HomeForm(forms.Form):
    pass


class AuthGroupsForm(forms.Form):
    group = forms.CharField(max_length=50, label='Имя группы')
    login = forms.CharField(max_length=50, label='Имя пользователя')
    password = forms.CharField(max_length=50, label='Пароль пользователя')
    privilege_mode_password = forms.CharField(max_length=50, label='Пароль от привилегированного режима', required=False)


class BackupGroupsForm(forms.Form):
    group = forms.CharField(max_length=50, label='Имя папки, для сохранения')


class AuthModelChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return obj.auth_group


class BackupModelChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return obj.backup_group


class DevicesForm(forms.Form):
    ip = forms.GenericIPAddressField(label='IP адрес')
    device_name = forms.CharField(max_length=50, label='Имя устройства')
    vendor = forms.CharField(max_length=50, label='Vendor: (Cisco, Huawei и т.д.)', required=False)
    auth_group = AuthModelChoiceField(
        required=True,
        widget=forms.Select,
        queryset=AuthGroup.objects.all()
    )

    backup_group = BackupModelChoiceField(
        required=True,
        widget=forms.Select,
        queryset=BackupGroup.objects.all()
    )
