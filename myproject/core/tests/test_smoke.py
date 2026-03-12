from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import CommunityPost, CouncilJoinApplication, Event, EventRegistration, FeedbackMessage, UserProfile
from core.services import EVENT_REGISTRATION_SUBJECT_PREFIX

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

    def test_event_registration_forbidden_after_deadline(self):
        user = self.create_user("deadline_user")
        event = Event.objects.create(
            title="Событие с прошедшим дедлайном",
            description="Описание",
            short_description="Коротко",
            location="Аудитория 101",
            start_at=timezone.now() + timedelta(days=1),
            registration_deadline=timezone.now() - timedelta(hours=1),
            is_published=True,
        )
        self.client.login(username=user.username, password="pass12345")

        response = self.client.post(reverse("core:event_detail", kwargs={"pk": event.pk}), {"comment": "Хочу участвовать"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Регистрация на мероприятие закрыта.")
        self.assertEqual(EventRegistration.objects.filter(event=event, user=user).count(), 0)

    def test_event_registration_forbidden_when_limit_reached(self):
        event = Event.objects.create(
            title="Событие с лимитом",
            description="Описание",
            short_description="Коротко",
            location="Аудитория 204",
            start_at=timezone.now() + timedelta(days=2),
            registration_deadline=timezone.now() + timedelta(days=1),
            max_participants=1,
            is_published=True,
        )
        first_user = self.create_user("first_user")
        EventRegistration.objects.create(user=first_user, event=event, comment="")

        second_user = self.create_user("second_user")
        self.client.login(username=second_user.username, password="pass12345")

        response = self.client.post(reverse("core:event_detail", kwargs={"pk": event.pk}), {"comment": "Успеть бы"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Достигнут лимит участников мероприятия.")
        self.assertEqual(EventRegistration.objects.filter(event=event).count(), 1)

    def test_manager_can_update_event_from_events_list(self):
        manager = self.create_user("events_manager", role=UserProfile.ROLE_MANAGER)
        event = Event.objects.create(
            title="Тестовое событие",
            description="Описание",
            short_description="Старый анонс",
            location="Аудитория 101",
            start_at=timezone.now() + timedelta(days=3),
            is_published=True,
        )
        self.client.login(username=manager.username, password="pass12345")

        new_deadline = (timezone.now() + timedelta(days=2)).replace(second=0, microsecond=0)
        response = self.client.post(
            reverse("core:events_list"),
            {
                "event_id": event.pk,
                "archive": "0",
                "title": event.title,
                "short_description": "Обновленный анонс",
                "location": event.location,
                "start_at": event.start_at.strftime("%Y-%m-%dT%H:%M"),
                "registration_deadline": new_deadline.strftime("%Y-%m-%dT%H:%M"),
                "max_participants": "150",
            },
        )

        self.assertEqual(response.status_code, 302)
        event.refresh_from_db()
        self.assertEqual(event.short_description, "Обновленный анонс")
        self.assertEqual(event.max_participants, 150)
        self.assertIsNotNone(event.registration_deadline)

    def test_event_registration_creates_auto_moderation_request(self):
        user = self.create_user("student_event")
        user.first_name = "Илья"
        user.last_name = "Чубун"
        user.email = "student@example.com"
        user.save(update_fields=["first_name", "last_name", "email"])

        event = Event.objects.create(
            title="Форум лидеров",
            description="Описание",
            short_description="Коротко",
            location="Корпус А, актовый зал",
            start_at=timezone.now() + timedelta(days=4),
            is_published=True,
        )

        self.client.login(username=user.username, password="pass12345")
        response = self.client.post(
            reverse("core:event_detail", kwargs={"pk": event.pk}),
            {"comment": "Хочу участвовать"},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(EventRegistration.objects.filter(user=user, event=event).count(), 1)

        feedback = FeedbackMessage.objects.get(user=user, subject__startswith=EVENT_REGISTRATION_SUBJECT_PREFIX)
        self.assertIn(event.title, feedback.subject)
        self.assertIn(event.location, feedback.message)
        self.assertIn("Илья Чубун", feedback.message)

    def test_event_requests_hidden_in_feedbacks_and_shown_in_join_requests(self):
        manager = self.create_user("mod_manager", role=UserProfile.ROLE_MANAGER)
        FeedbackMessage.objects.create(
            name="Студент",
            email="student@example.com",
            subject=f"{EVENT_REGISTRATION_SUBJECT_PREFIX} Заявка на мероприятие: Тест",
            message="Тестовая заявка",
        )
        FeedbackMessage.objects.create(
            name="Пользователь",
            email="user@example.com",
            subject="Обычное обращение",
            message="Текст обращения",
        )
        self.client.login(username=manager.username, password="pass12345")

        feedbacks_response = self.client.get(reverse("core:staff_feedbacks"))
        self.assertEqual(feedbacks_response.status_code, 200)
        self.assertContains(feedbacks_response, "Обычное обращение")
        self.assertNotContains(feedbacks_response, "Заявка на мероприятие: Тест")

        join_response = self.client.get(reverse("core:staff_join_requests"))
        self.assertEqual(join_response.status_code, 200)
        self.assertContains(join_response, "Заявка на мероприятие: Тест")

    def test_student_cannot_create_community_post(self):
        student = self.create_user("student_community", role=UserProfile.ROLE_STUDENT)
        self.client.login(username=student.username, password="pass12345")

        response = self.client.post(
            reverse("core:community"),
            {"create_post": "1", "title": "Пост студента", "body": "Текст поста"},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(CommunityPost.objects.count(), 0)

    def test_manager_can_create_and_pin_community_post(self):
        manager = self.create_user("manager_community", role=UserProfile.ROLE_MANAGER)
        self.client.login(username=manager.username, password="pass12345")

        create_response = self.client.post(
            reverse("core:community"),
            {"create_post": "1", "title": "Пост менеджера", "body": "Текст поста"},
        )
        self.assertEqual(create_response.status_code, 302)

        post = CommunityPost.objects.get(title="Пост менеджера")
        self.assertFalse(post.is_pinned)

        pin_response = self.client.post(
            reverse("core:community"),
            {"toggle_global_pin": "1", "post_id": post.id},
        )
        self.assertEqual(pin_response.status_code, 302)
        post.refresh_from_db()
        self.assertTrue(post.is_pinned)

    def test_student_can_pin_post_only_for_self(self):
        manager = self.create_user("manager_post_owner", role=UserProfile.ROLE_MANAGER)
        post = CommunityPost.objects.create(
            author=manager,
            title="Общий пост",
            body="Общее содержание",
            is_published=True,
            is_pinned=False,
        )

        student = self.create_user("student_pin_self", role=UserProfile.ROLE_STUDENT)
        self.client.login(username=student.username, password="pass12345")

        response = self.client.post(
            reverse("core:community"),
            {"toggle_pin": "1", "post_id": post.id},
        )

        self.assertEqual(response.status_code, 302)
        post.refresh_from_db()
        self.assertFalse(post.is_pinned)
        self.assertContains(self.client.get(reverse("core:community")), "Закреплено у вас")

    def test_staff_cabinet_splits_feedbacks_and_requests(self):
        manager = self.create_user("manager_cabinet", role=UserProfile.ROLE_MANAGER)
        student = self.create_user("student_cabinet", role=UserProfile.ROLE_STUDENT)

        FeedbackMessage.objects.create(
            name="Студент",
            email="student@example.com",
            subject="Вопрос по расписанию",
            message="Текст из формы обратной связи",
            user=student,
        )
        FeedbackMessage.objects.create(
            name="Студент",
            email="student@example.com",
            subject=f"{EVENT_REGISTRATION_SUBJECT_PREFIX} Заявка на мероприятие: Тест",
            message="Текст заявки на мероприятие",
            user=student,
        )
        CouncilJoinApplication.objects.create(
            full_name="Иван Петров",
            email="ivan@example.com",
            phone="+79000000000",
            faculty="it",
            course="2",
            motivation="Хочу участвовать",
            experience="",
            user=student,
        )

        self.client.login(username=manager.username, password="pass12345")

        feedbacks_response = self.client.get(reverse("core:my_feedbacks"))
        self.assertEqual(feedbacks_response.status_code, 200)
        self.assertContains(feedbacks_response, "Вопрос по расписанию")
        self.assertNotContains(feedbacks_response, "Заявка на мероприятие: Тест")

        requests_response = self.client.get(reverse("core:my_join_requests"))
        self.assertEqual(requests_response.status_code, 200)
        self.assertContains(requests_response, "Иван Петров")
        self.assertNotContains(requests_response, "Заявка на мероприятие: Тест")

        events_response = self.client.get(reverse("core:my_events"))
        self.assertEqual(events_response.status_code, 200)
        self.assertContains(events_response, "Заявка на мероприятие: Тест")
