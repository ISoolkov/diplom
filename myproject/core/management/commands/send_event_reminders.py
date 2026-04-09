from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import EventRegistration


class Command(BaseCommand):
    help = "Отправляет email-напоминания за 24 часа до начала мероприятия."

    def add_arguments(self, parser):
        parser.add_argument(
            "--window-minutes",
            type=int,
            default=60,
            help="Окно в минутах после отметки +24 часа (по умолчанию: 60).",
        )

    def handle(self, *args, **options):
        window_minutes = max(1, int(options["window_minutes"]))
        now = timezone.now()
        from_dt = now + timedelta(hours=24)
        to_dt = from_dt + timedelta(minutes=window_minutes)

        registrations = (
            EventRegistration.objects.select_related("event", "user")
            .filter(
                reminder_sent_at__isnull=True,
                user__is_active=True,
                event__is_published=True,
                event__start_at__gte=from_dt,
                event__start_at__lt=to_dt,
            )
            .exclude(user__email__isnull=True)
            .exclude(user__email__exact="")
        )

        sent_count = 0
        for registration in registrations:
            event = registration.event
            user = registration.user
            send_mail(
                subject=f"Напоминание: мероприятие «{event.title}» через 24 часа",
                message=(
                    f"Здравствуйте, {user.get_full_name().strip() or user.username}!\n\n"
                    "Напоминаем, что вы зарегистрированы на мероприятие студсовета.\n"
                    f"Название: {event.title}\n"
                    f"Дата и время: {event.start_at:%d.%m.%Y %H:%M}\n"
                    f"Место: {event.location}\n\n"
                    "До встречи!"
                ),
                from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@muiv.local"),
                recipient_list=[user.email],
                fail_silently=True,
            )
            registration.reminder_sent_at = now
            registration.save(update_fields=["reminder_sent_at", "updated_at"])
            sent_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Отправлено напоминаний: {sent_count}. "
                f"Окно: {from_dt:%d.%m.%Y %H:%M} - {to_dt:%d.%m.%Y %H:%M}."
            )
        )
