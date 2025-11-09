"""
URL configuration for Ieltsapp project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import path, include
from django.conf.urls.static import static
from django.conf import settings
from Mock.views import ckeditor_upload_image

urlpatterns = [
    path('admin/', admin.site.urls),
    path('ckeditor/upload/', ckeditor_upload_image, name='ckeditor_upload_image'),
    path('', include('Mock.urls')),
    path('select2/', include('django_select2.urls')),
]
# 💡 Bu qism har doim eng oxirida bo'lishi kerak!
if settings.DEBUG:
    # Media fayllarini Debug rejimida yuklash
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    # Static fayllarni ham yuklash (agar kerak bo'lsa)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)