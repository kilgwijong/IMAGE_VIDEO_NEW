from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path("", include("generator.urls")),
    path("accounts/", include("accounts.urls")),   # ← 있어야 합니다
    path("admin/", admin.site.urls),               # (Django 기본 admin은 그대로 두셔도 됩니다)
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
