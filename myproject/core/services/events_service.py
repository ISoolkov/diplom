from django.utils import timezone

from .exceptions import ServiceValidationError


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


def register_for_event(user, event, comment, model_cls):
    """Создает регистрацию пользователя на мероприятие после всех проверок."""
    ensure_can_register(user=user, event=event, model_cls=model_cls)
    return model_cls.objects.create(user=user, event=event, comment=comment)
