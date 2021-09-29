from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseNotFound, HttpResponsePermanentRedirect
from cbp.forms import AuthGroupsForm
from cbp.models import AuthGroup
from cbp.views.user_checks import check_superuser


@login_required(login_url='accounts/login/')
def auth_groups(request):
    if not check_superuser(request):
        return HttpResponsePermanentRedirect('/')

    groups = AuthGroup.objects.all()
    return render(request, "device_control/auth_groups.html", {"form": AuthGroupsForm, "groups": groups})


@login_required(login_url='accounts/login/')
def auth_group_edit(request, id: int = 0):
    if not check_superuser(request):
        return HttpResponsePermanentRedirect('/')

    try:
        auth_group_form = AuthGroupsForm()
        if id:
            group = AuthGroup.objects.get(id=id)
            auth_group_form = AuthGroupsForm(initial={
                'group': group.auth_group,
                'login': group.login,
                'password': group.password,
                'privilege_mode_password': group.privilege_mode_password
            })
        else:
            group = AuthGroup()

        if request.method == "POST":
            group.auth_group = request.POST.get('group')
            group.login = request.POST.get('login')
            group.password = request.POST.get('password')
            group.privilege_mode_password = request.POST.get('privilege_mode_password')
            group.save()
            return HttpResponsePermanentRedirect("/auth_groups")
        else:
            return render(request, "device_control/auth_group_new.html", {"form": auth_group_form})
    except AuthGroup.DoesNotExist:
        return HttpResponseNotFound("<h2>Данная группа не найдена!</h2>")


@login_required(login_url='accounts/login/')
def auth_group_delete(request, id):
    if not check_superuser(request):
        return HttpResponsePermanentRedirect('/')

    try:
        group = AuthGroup.objects.get(id=id)
        group.delete()
        return HttpResponsePermanentRedirect('/auth_groups')
    except AuthGroup.DoesNotExist:
        return HttpResponseNotFound("<h2>Данная группа не найдена!</h2>")

