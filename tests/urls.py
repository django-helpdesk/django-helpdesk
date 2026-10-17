from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("", include("helpdesk.urls", namespace="helpdesk")),
    path("admin/", admin.site.urls),
    path("i18n/", include("django.conf.urls.i18n")),
]
