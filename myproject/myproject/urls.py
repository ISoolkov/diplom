"""
URL configuration for myproject project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
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
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.views.generic.base import RedirectView
from django.urls import include, path

from core import views as core_views

handler404 = "core.views.error_views.custom_404"

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('core.urls')),
    path(
        'favicon.ico',
        RedirectView.as_view(url='/static/img/faviconV2.png', permanent=True),
    ),
    path(
        'login/',
        core_views.login_view,
        name='login',
    ),
    path('login/2fa/', core_views.admin_2fa_verify, name='admin_2fa_verify'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
