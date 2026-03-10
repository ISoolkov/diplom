from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import Event, FeedbackMessage, UserProfile

User = get_user_model()


class SmokeTests(TestCase):
    def create_user(self, username, role=UserProfile.ROLE_STUDENT):
        user = User.objects.create_user(username=username, password="pass12345")
        profile = user.profile
        profile.role = role
        profile.save(update_fields=["role"])
        return user

    def test_staff_dashboard_forbidden_for_student(self):
        student = self.create_user("student")
        self.client.login(username=student.username, password="pass12345")

        response = self.client.get(reverse("core:staff_dashboard"))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("core:home"))

    def test_staff_dashboard_available_for_admin(self):
        admin = self.create_user("admin", role=UserProfile.ROLE_ADMIN)
        self.client.login(username=admin.username, password="pass12345")

        response = self.client.get(reverse("core:staff_dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "core/staff/dashboard.html")

    def test_staff_reports_available_for_manager(self):
        manager = self.create_user("manager", role=UserProfile.ROLE_MANAGER)
        self.client.login(username=manager.username, password="pass12345")

        response = self.client.get(reverse("core:staff_reports"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "core/staff/reports.html")

    def test_staff_users_forbidden_for_manager(self):
        manager = self.create_user("manager_limited", role=UserProfile.ROLE_MANAGER)
        self.client.login(username=manager.username, password="pass12345")

        response = self.client.get(reverse("core:staff_users"))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("core:home"))

    def test_feedback_form_creates_message(self):
        response = self.client.post(
            reverse("core:feedback"),
            {
                "name": "Тест",
                "email": "test@example.com",
                "subject": "Проверка",
                "message": "Сообщение для проверки формы.",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("core:feedback"))
        self.assertEqual(FeedbackMessage.objects.count(), 1)

    def test_export_events_docx_returns_file(self):
        admin = self.create_user("report_admin", role=UserProfile.ROLE_ADMIN)
        Event.objects.create(
            title="Мероприятие",
            description="Полное описание",
            short_description="Коротко",
            location="Аудитория 101",
            start_at=timezone.now() + timedelta(days=1),
            is_published=True,
        )
        self.client.login(username=admin.username, password="pass12345")

        response = self.client.get(reverse("core:export_events_docx"))

        self.assertEqual(response.status_code, 200)
        self.assertIn("application/vnd.openxmlformats-officedocument.wordprocessingml.document", response["Content-Type"])
        self.assertIn("events_report_", response["Content-Disposition"])

    def test_export_feedback_xlsx_returns_file(self):
        admin = self.create_user("xlsx_admin", role=UserProfile.ROLE_ADMIN)
        FeedbackMessage.objects.create(
            name="Тест",
            email="test@example.com",
            subject="Тема",
            message="Текст",
        )
        self.client.login(username=admin.username, password="pass12345")

        response = self.client.get(reverse("core:export_feedback_xlsx"))

        self.assertEqual(response.status_code, 200)
        self.assertIn("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", response["Content-Type"])
        self.assertIn("feedback_report_", response["Content-Disposition"])

    def test_cabinet_for_authorized_user(self):
        user = self.create_user("cabinet_user")
        self.client.login(username=user.username, password="pass12345")

        response = self.client.get(reverse("core:cabinet"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "core/cabinet.html")
