from django.utils import timezone

from core.models import FeedbackMessage

from .exceptions import ServiceValidationError

EVENT_REGISTRATION_SUBJECT_PREFIX = "[EVENT_REG]"


def ensure_can_register(user, event, model_cls):
    """Проверяет, можно ли пользователю зарегистрироваться на мероприятие."""
    if event.registration_deadline and timezone.now() >= event.registration_deadline:
        raise ServiceValidationError("Регистрация на мероприятие закрыта.")

    if event.max_participants is not None:
        registrations_count = model_cls.objects.filter(event=event).count()
        if registrations_count >= event.max_participants:
            raise ServiceValidationError("Достигнут лимит участников мероприятия.")

    if model_cls.objects.filter(user=user, event=event).exists():
        raise ServiceValidationError("Вы уже зарегистрированы на это мероприятие.")


def _event_feedback_payload(user, event, comment):
    full_name = user.get_full_name().strip() or user.username
    email = user.email or f"{user.username}@muiv.local"
    subject = f"{EVENT_REGISTRATION_SUBJECT_PREFIX} Заявка на мероприятие: {event.title}"
    message = (
        f"Пользователь {full_name} хочет записаться на мероприятие \"{event.title}\".\n"
        f"Дата и время: {event.start_at:%d.%m.%Y %H:%M}.\n"
        f"Место проведения: {event.location}.\n"
        f"Комментарий пользователя: {comment or '-'}."
    )
    return {
        "name": full_name,
        "email": email,
        "subject": subject,
        "message": message,
    }


def register_for_event(user, event, comment, model_cls):
    """Создает регистрацию на мероприятие и служебную заявку для модерации."""
    ensure_can_register(user=user, event=event, model_cls=model_cls)
    registration = model_cls.objects.create(user=user, event=event, comment=comment)

    payload = _event_feedback_payload(user=user, event=event, comment=comment.strip())
    FeedbackMessage.objects.create(
        name=payload["name"],
        email=payload["email"],
        subject=payload["subject"],
        message=payload["message"],
        user=user,
    )
    return registration
