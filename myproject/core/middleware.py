from django.shortcuts import redirect
from django.urls import reverse

from core.permissions import has_any_role
from core.models import UserProfile
from core.site_settings import get_maintenance_settings


class MaintenanceModeMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        settings_obj = get_maintenance_settings()
        if settings_obj.maintenance_enabled:
            maintenance_path = reverse("core:maintenance")

            if request.path.startswith("/static/") or request.path.startswith("/media/"):
                return self.get_response(request)

            if request.path == maintenance_path:
                return self.get_response(request)

            if request.path.startswith("/login/") or request.path.startswith("/logout/"):
                return self.get_response(request)

            if request.user.is_authenticated and has_any_role(request.user, UserProfile.ROLE_ADMIN):
                return self.get_response(request)

            return redirect("core:maintenance")

        return self.get_response(request)
