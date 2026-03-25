from core.models import ActivityLog


def _extract_client_ip(request):
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def log_user_activity(request, action, details=""):
    user = request.user if getattr(request, "user", None) and request.user.is_authenticated else None
    user_agent = request.META.get("HTTP_USER_AGENT", "")[:255]
    ActivityLog.objects.create(
        actor=user,
        action=action[: ActivityLog.ACTION_MAX_LENGTH],
        details=details,
        ip_address=_extract_client_ip(request),
        user_agent=user_agent,
    )
