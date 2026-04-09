from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail


User = get_user_model()


def _collect_event_announcement_recipients(actor=None):
    recipients = (
        User.objects.filter(is_active=True)
        .exclude(email__isnull=True)
        .exclude(email__exact="")
        .values_list("email", flat=True)
        .distinct()
    )
    recipient_list = list(recipients)
    if actor and actor.email:
        recipient_list = [email for email in recipient_list if email.lower() != actor.email.lower()]
    return recipient_list


def send_new_event_announcement(event, actor=None):
    """Sends email announcement to active users about a newly published event."""
    recipient_list = _collect_event_announcement_recipients(actor=actor)
    if not recipient_list:
        return 0

    subject = f"Новый анонс мероприятия: {event.title}"
    body = (
        "Опубликован новый анонс мероприятия студсовета.\n\n"
        f"Название: {event.title}\n"
        f"Дата и время: {event.start_at:%d.%m.%Y %H:%M}\n"
        f"Место: {event.location}\n"
        f"Описание: {event.short_description}\n"
    )

    sent = 0
    for email in recipient_list:
        send_mail(
            subject=subject,
            message=body,
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@muiv.local"),
            recipient_list=[email],
            fail_silently=True,
        )
        sent += 1
    return sent
