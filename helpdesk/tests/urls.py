from django.urls import include, path
from django.contrib import admin

urlpatterns = [
    path('', include('helpdesk.urls', namespace='helpdesk')),
    path('admin/', admin.site.urls),
]
