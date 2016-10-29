from django.conf.urls import include, url

urlpatterns = [
    url(r'^helpdesk/', include('helpdesk.urls', namespace='helpdesk')),
]
