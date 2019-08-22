from django.conf import settings
from django.contrib.auth import views as auth_views
from django.contrib.auth.views import redirect_to_login
from django.shortcuts import resolve_url


default_login_view = auth_views.LoginView.as_view(
        template_name='helpdesk/registration/login.html')


def login(request):
    login_url = settings.LOGIN_URL
    # Prevent redirect loop by checking that LOGIN_URL is not this view's name
    if login_url and login_url != request.resolver_match.view_name:
        if 'next' in request.GET:
            return_to = request.GET['next']
        else:
            return_to = resolve_url('helpdesk:home')
        return redirect_to_login(return_to, login_url)
    else:
        return default_login_view(request)
