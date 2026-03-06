from .exceptions import ServiceValidationError


def ensure_can_register(user, event, model_cls):
    if model_cls.objects.filter(user=user, event=event).exists():
        raise ServiceValidationError("Вы уже зарегистрированы на это мероприятие.")


def register_for_event(user, event, comment, model_cls):
    ensure_can_register(user=user, event=event, model_cls=model_cls)
    return model_cls.objects.create(user=user, event=event, comment=comment)
