from django.conf import settings
from django.core.mail import send_mail

from .exceptions import ServiceValidationError


def _validate_choice(value, choices, message):
    valid_values = {choice[0] for choice in choices}
    if value not in valid_values:
        raise ServiceValidationError(message)


def _choice_label(value, choices):
    for current_value, label in choices:
        if current_value == value:
            return label
    return value


def _send_status_email(email, subject, body):
    if not email:
        return
    send_mail(
        subject=subject,
        message=body,
        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@muiv.local"),
        recipient_list=[email],
        fail_silently=True,
    )


def update_feedback_status(feedback, new_status, moderation_comment):
    _validate_choice(new_status, feedback.STATUS_CHOICES, "Передан некорректный статус обращения.")
    feedback.status = new_status
    feedback.moderation_comment = moderation_comment.strip()
    feedback.save(update_fields=["status", "moderation_comment", "updated_at"])

    status_label = _choice_label(new_status, feedback.STATUS_CHOICES)
    _send_status_email(
        email=feedback.email,
        subject=f"Обновлен статус обращения: {feedback.subject}",
        body=(
            "Ваше обращение обновлено.\n"
            f"Новый статус: {status_label}.\n"
            f"Комментарий модератора: {feedback.moderation_comment or '-'}."
        ),
    )


def update_join_request_status(join_request, new_status, moderation_comment):
    _validate_choice(new_status, join_request.STATUS_CHOICES, "Передан некорректный статус заявки.")
    join_request.status = new_status
    join_request.moderation_comment = moderation_comment.strip()
    join_request.save(update_fields=["status", "moderation_comment", "updated_at"])

    status_label = _choice_label(new_status, join_request.STATUS_CHOICES)
    _send_status_email(
        email=join_request.email,
        subject="Обновлен статус заявки в студсовет",
        body=(
            "Статус вашей заявки обновлен.\n"
            f"Новый статус: {status_label}.\n"
            f"Комментарий модератора: {join_request.moderation_comment or '-'}."
        ),
    )


def update_user_role(profile, new_role):
    _validate_choice(new_role, profile.ROLE_CHOICES, "Передано недопустимое значение роли.")
    profile.role = new_role
    profile.save(update_fields=["role"])
