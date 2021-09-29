from django.contrib.auth.models import User
from django.http import HttpResponsePermanentRedirect
from cbp.models import BackupGroup


def check_user_permission(request):
    current_user = User.objects.get(username=str(request.user))  # Текущий пользователь
    available_backup_groups = [g.backup_group for g in
                               BackupGroup.objects.filter(users__username=current_user.username)]
    if (not available_backup_groups or str(request.GET.get('bg')) not in available_backup_groups) \
            and not current_user.is_superuser:
        return HttpResponsePermanentRedirect('/')


def check_superuser(request):
    try:
        if not User.objects.get(username=str(request.user)).is_superuser:
            return 0
        else:
            return 1
    except Exception:
        return 0
