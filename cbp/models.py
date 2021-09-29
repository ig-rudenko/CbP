from django.db import models
from django.contrib.auth.models import User


class FtpGroup(models.Model):
    name = models.CharField(max_length=50, null=True)
    host = models.GenericIPAddressField()
    login = models.CharField(max_length=50, null=True)
    password = models.CharField(max_length=50, null=True)
    workdir = models.CharField(max_length=255, null=True)


class AuthGroup(models.Model):
    auth_group = models.CharField(max_length=50)
    login = models.CharField(max_length=50, null=True)
    password = models.CharField(max_length=50, null=True)
    privilege_mode_password = models.CharField(max_length=50, null=True)


class BackupGroup(models.Model):
    backup_group = models.CharField(max_length=50)
    users = models.ManyToManyField(User)
    ftp_server = models.ManyToManyField(FtpGroup)


class Equipment(models.Model):
    ip = models.GenericIPAddressField()
    device_name = models.CharField(max_length=100)
    vendor = models.CharField(max_length=50)
    protocol = models.CharField(max_length=50, default='telnet')
    auth_group = models.ForeignKey(AuthGroup, on_delete=models.SET_NULL, null=True)
    backup_group = models.ForeignKey(BackupGroup, on_delete=models.SET_NULL, null=True)
