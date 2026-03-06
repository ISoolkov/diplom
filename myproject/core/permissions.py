from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect

from .models import UserProfile


def get_user_role(user):
    if not user.is_authenticated:
        return None
    profile = getattr(user, "profile", None)
    if profile:
        return profile.role
    return UserProfile.ROLE_STUDENT


def has_any_role(user, *allowed_roles):
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return get_user_role(user) in allowed_roles


def role_required(*allowed_roles):
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def _wrapped_view(request, *args, **kwargs):
            if has_any_role(request.user, *allowed_roles):
                return view_func(request, *args, **kwargs)
            messages.error(request, "Недостаточно прав для доступа к разделу.")
            return redirect("core:home")

        return _wrapped_view

    return decorator

