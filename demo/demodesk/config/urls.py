"""django-helpdesk demodesk URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/1.10/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  url(r'^$', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  url(r'^$', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.conf.urls import url, include
    2. Add a URL to urlpatterns:  url(r'^blog/', include('blog.urls'))
"""
from django.conf.urls import url, include
from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static


# The following uses the static() helper function,
# which only works when in development mode (using DEBUG).
# For a real deployment, you'd have to properly configure a media server.
# For more information, see:
# https://docs.djangoproject.com/en/1.10/howto/static-files/

urlpatterns = [
    url(r'^admin/', admin.site.urls),
    url(r'^', include('helpdesk.urls', namespace='helpdesk')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
