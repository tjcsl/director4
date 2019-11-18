from django.contrib.auth import logout
from django.shortcuts import redirect, render

# Create your views here.


def index_view(request):
    if request.user.is_authenticated:
        return login_view(request)
    else:
        return login_view(request)


def login_view(request):
    return render(request, "auth/login.html")


def logout_view(request):
    logout(request)
    return redirect("auth:index")
