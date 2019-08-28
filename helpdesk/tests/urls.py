from django.conf.urls import include, url
from django.contrib import admin

urlpatterns = [
    url(r'^helpdesk/', include('helpdesk.urls', namespace='helpdesk')),
    url(r'^admin/', admin.site.urls),
]
