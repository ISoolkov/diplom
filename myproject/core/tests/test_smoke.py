from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core.models import (
    ActivityLog,
    CommunityPost,
    CouncilJoinApplication,
    Event,
    EventRegistration,
    FeedbackMessage,
    SiteMaintenance,
    Poll,
    PollOption,
    PollVote,
    UserProfile,
)
from core.security.totp import current_totp_token
from core.services import EVENT_REGISTRATION_SUBJECT_PREFIX

User = get_user_model()


class SmokeTests(TestCase):
    def create_user(self, username, role=UserProfile.ROLE_STUDENT):
        user = User.objects.create_user(username=username)
        profile = user.profile
        profile.role = role
        profile.save(update_fields=["role"])
        return user

    def test_staff_dashboard_forbidden_for_student(self):
        student = self.create_user("student")
        self.client.force_login(student)

        response = self.client.get(reverse("core:staff_dashboard"))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("core:home"))

    def test_admin_login_requires_totp_code(self):
        user = User.objects.create_user(username="admin_2fa", password="StrongPass123!")
        profile = user.profile
        profile.role = UserProfile.ROLE_ADMIN
        profile.save(update_fields=["role"])

        login_response = self.client.post(
            reverse("login"),
            {"username": "admin_2fa", "password": "StrongPass123!"},
        )
        self.assertEqual(login_response.status_code, 302)
        self.assertEqual(login_response.url, reverse("admin_2fa_verify"))
        self.assertNotIn("_auth_user_id", self.client.session)

        setup_response = self.client.get(reverse("admin_2fa_verify"))
        self.assertEqual(setup_response.status_code, 200)
        profile.refresh_from_db()
        self.assertTrue(profile.totp_secret)

        token = current_totp_token(profile.totp_secret)
        verify_response = self.client.post(reverse("admin_2fa_verify"), {"token": token})
        self.assertEqual(verify_response.status_code, 302)
        self.assertEqual(verify_response.url, reverse("core:cabinet"))
        self.assertEqual(str(user.id), self.client.session.get("_auth_user_id"))

    def test_student_login_without_totp(self):
        user = User.objects.create_user(username="student_plain", password="StrongPass123!")
        profile = user.profile
        profile.role = UserProfile.ROLE_STUDENT
        profile.save(update_fields=["role"])

        response = self.client.post(
            reverse("login"),
            {"username": "student_plain", "password": "StrongPass123!"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("core:cabinet"))
        self.assertEqual(str(user.id), self.client.session.get("_auth_user_id"))

    def test_staff_dashboard_available_for_admin(self):
        admin = self.create_user("admin", role=UserProfile.ROLE_ADMIN)
        self.client.force_login(admin)

        response = self.client.get(reverse("core:staff_dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "core/staff/dashboard.html")

    def test_staff_reports_available_for_manager(self):
        manager = self.create_user("manager", role=UserProfile.ROLE_MANAGER)
        self.client.force_login(manager)

        response = self.client.get(reverse("core:staff_reports"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "core/staff/reports.html")

    def test_staff_faqs_available_for_manager_and_can_create_item(self):
        manager = self.create_user("faq_manager", role=UserProfile.ROLE_MANAGER)
        self.client.force_login(manager)

        page_response = self.client.get(reverse("core:staff_faqs"))
        self.assertEqual(page_response.status_code, 200)
        self.assertTemplateUsed(page_response, "core/staff/faqs.html")

        create_response = self.client.post(
            reverse("core:staff_faqs"),
            {
                "question": "Как записаться на мероприятие?",
                "answer": "Откройте карточку события и нажмите кнопку регистрации.",
                "order": 10,
                "is_published": "on",
            },
        )
        self.assertEqual(create_response.status_code, 302)

        from core.models import FAQ

        self.assertTrue(FAQ.objects.filter(question="Как записаться на мероприятие?").exists())

    def test_staff_faqs_manager_can_reorder_and_delete_items(self):
        from core.models import FAQ

        manager = self.create_user("faq_manager_actions", role=UserProfile.ROLE_MANAGER)
        self.client.force_login(manager)

        first = FAQ.objects.create(question="Q1", answer="A1", order=1, is_published=True)
        second = FAQ.objects.create(question="Q2", answer="A2", order=2, is_published=True)

        move_response = self.client.post(
            reverse("core:staff_faqs"),
            {"action": "move_down", "faq_id": first.id},
        )
        self.assertEqual(move_response.status_code, 302)
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual(first.order, 2)
        self.assertEqual(second.order, 1)

        delete_response = self.client.post(
            reverse("core:staff_faqs"),
            {"action": "delete", "faq_id": first.id},
        )
        self.assertEqual(delete_response.status_code, 302)
        self.assertFalse(FAQ.objects.filter(pk=first.id).exists())

    def test_staff_users_forbidden_for_manager(self):
        manager = self.create_user("manager_limited", role=UserProfile.ROLE_MANAGER)
        self.client.force_login(manager)

        response = self.client.get(reverse("core:staff_users"))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("core:home"))

    def test_staff_activity_logs_available_only_for_admin(self):
        admin = self.create_user("logs_admin", role=UserProfile.ROLE_ADMIN)
        manager = self.create_user("logs_manager", role=UserProfile.ROLE_MANAGER)

        self.client.force_login(admin)
        admin_response = self.client.get(reverse("core:staff_activity_logs"))
        self.assertEqual(admin_response.status_code, 200)
        self.assertTemplateUsed(admin_response, "core/staff/activity_logs.html")

        self.client.force_login(manager)
        manager_response = self.client.get(reverse("core:staff_activity_logs"))
        self.assertEqual(manager_response.status_code, 302)
        self.assertEqual(manager_response.url, reverse("core:home"))

    def test_staff_activity_log_created_after_faq_create(self):
        admin = self.create_user("faq_log_admin", role=UserProfile.ROLE_ADMIN)
        self.client.force_login(admin)

        response = self.client.post(
            reverse("core:staff_faqs"),
            {
                "question": "Логируемый вопрос",
                "answer": "Логируемый ответ",
                "order": 1,
                "is_published": "on",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(ActivityLog.objects.filter(action="staff.faq.created", actor=admin).exists())

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

    def test_feedback_form_accepts_attachment(self):
        attachment = SimpleUploadedFile(
            "request.txt",
            b"test attachment content",
            content_type="text/plain",
        )

        response = self.client.post(
            reverse("core:feedback"),
            {
                "name": "Тест",
                "email": "test@example.com",
                "subject": "Проверка с файлом",
                "message": "Сообщение с вложением",
                "attachment": attachment,
            },
        )

        self.assertEqual(response.status_code, 302)
        item = FeedbackMessage.objects.get(subject="Проверка с файлом")
        self.assertTrue(bool(item.attachment))

    def test_feedback_form_rate_limited_to_once_per_minute(self):
        user = self.create_user("feedback_rate_user")
        self.client.force_login(user)

        first = self.client.post(
            reverse("core:feedback"),
            {
                "name": "Тест",
                "email": "test@example.com",
                "subject": "Первое обращение",
                "message": "Первое сообщение",
            },
        )
        self.assertEqual(first.status_code, 302)
        self.assertEqual(FeedbackMessage.objects.filter(user=user).count(), 1)

        second = self.client.post(
            reverse("core:feedback"),
            {
                "name": "Тест",
                "email": "test@example.com",
                "subject": "Второе обращение",
                "message": "Второе сообщение",
            },
            follow=True,
        )
        self.assertEqual(second.status_code, 200)
        self.assertContains(second, "не чаще одного раза в минуту")
        self.assertEqual(FeedbackMessage.objects.filter(user=user).count(), 1)

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
        self.client.force_login(admin)

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
        self.client.force_login(admin)

        response = self.client.get(reverse("core:export_feedback_xlsx"))

        self.assertEqual(response.status_code, 200)
        self.assertIn("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", response["Content-Type"])
        self.assertIn("feedback_report_", response["Content-Disposition"])

    def test_cabinet_for_authorized_user(self):
        user = self.create_user("cabinet_user")
        self.client.force_login(user)

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
        self.client.force_login(user)

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
        self.client.force_login(second_user)

        response = self.client.post(reverse("core:event_detail", kwargs={"pk": event.pk}), {"comment": "Успеть бы"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Достигнут лимит участников мероприятия.")
        self.assertEqual(EventRegistration.objects.filter(event=event).count(), 1)

    def test_event_registration_rate_limited_to_once_per_minute(self):
        user = self.create_user("event_rate_user")
        event_1 = Event.objects.create(
            title="Событие 1",
            description="Описание",
            short_description="Коротко",
            location="Аудитория 301",
            start_at=timezone.now() + timedelta(days=3),
            is_published=True,
        )
        event_2 = Event.objects.create(
            title="Событие 2",
            description="Описание",
            short_description="Коротко",
            location="Аудитория 302",
            start_at=timezone.now() + timedelta(days=4),
            is_published=True,
        )
        self.client.force_login(user)

        first = self.client.post(
            reverse("core:event_detail", kwargs={"pk": event_1.pk}),
            {"comment": "Первый запрос"},
        )
        self.assertEqual(first.status_code, 302)
        self.assertEqual(EventRegistration.objects.filter(user=user).count(), 1)

        second = self.client.post(
            reverse("core:event_detail", kwargs={"pk": event_2.pk}),
            {"comment": "Второй запрос"},
            follow=True,
        )
        self.assertEqual(second.status_code, 200)
        self.assertContains(second, "не чаще одного раза в минуту")
        self.assertEqual(EventRegistration.objects.filter(user=user).count(), 1)

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
        self.client.force_login(manager)

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

    def test_admin_and_manager_can_create_event_from_events_list(self):
        for username, role in (
            ("events_admin_create", UserProfile.ROLE_ADMIN),
            ("events_manager_create", UserProfile.ROLE_MANAGER),
        ):
            with self.subTest(role=role):
                user = self.create_user(username, role=role)
                self.client.force_login(user)
                response = self.client.post(
                    reverse("core:events_list"),
                    {
                        "action": "create",
                        "title": f"Новое событие {role}",
                        "short_description": "Краткий анонс",
                        "location": "Аудитория 100",
                        "start_at": (timezone.now() + timedelta(days=5)).strftime("%Y-%m-%dT%H:%M"),
                        "registration_deadline": (timezone.now() + timedelta(days=4)).strftime("%Y-%m-%dT%H:%M"),
                        "max_participants": "120",
                    },
                )
                self.assertEqual(response.status_code, 302)
                self.assertTrue(Event.objects.filter(title=f"Новое событие {role}").exists())

    def test_manager_can_create_event_with_uploaded_image(self):
        manager = self.create_user("events_manager_image", role=UserProfile.ROLE_MANAGER)
        self.client.force_login(manager)

        image_file = SimpleUploadedFile(
            "event.gif",
            (
                b"GIF87a\x01\x00\x01\x00\x80\x00\x00"
                b"\x00\x00\x00\xff\xff\xff!\xf9\x04\x00\x00\x00\x00\x00,"
                b"\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;"
            ),
            content_type="image/gif",
        )

        response = self.client.post(
            reverse("core:events_list"),
            {
                "action": "create",
                "title": "Событие с фото",
                "short_description": "Анонс с фото",
                "location": "Аудитория 203",
                "start_at": (timezone.now() + timedelta(days=5)).strftime("%Y-%m-%dT%H:%M"),
                "registration_deadline": (timezone.now() + timedelta(days=4)).strftime("%Y-%m-%dT%H:%M"),
                "max_participants": "100",
                "image": image_file,
            },
        )

        self.assertEqual(response.status_code, 302)
        event = Event.objects.get(title="Событие с фото")
        self.assertTrue(bool(event.image))

    def test_admin_can_enable_maintenance_mode(self):
        admin = self.create_user("maintenance_admin", role=UserProfile.ROLE_ADMIN)
        self.client.force_login(admin)

        response = self.client.post(
            reverse("core:staff_dashboard"),
            {
                "action": "enable_maintenance",
                "maintenance_ends_at": (timezone.now() + timedelta(hours=3)).strftime("%Y-%m-%dT%H:%M:%S"),
            },
        )

        self.assertEqual(response.status_code, 302)
        settings_obj = SiteMaintenance.objects.get(pk=1)
        self.assertTrue(settings_obj.maintenance_enabled)
        self.assertIsNotNone(settings_obj.maintenance_ends_at)

    def test_non_admin_redirected_to_maintenance_when_enabled(self):
        SiteMaintenance.objects.update_or_create(
            pk=1,
            defaults={
                "maintenance_enabled": True,
                "maintenance_ends_at": timezone.now() + timedelta(hours=2),
            },
        )

        response = self.client.get(reverse("core:home"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("core:maintenance"))

        manager = self.create_user("maintenance_manager", role=UserProfile.ROLE_MANAGER)
        self.client.force_login(manager)
        manager_response = self.client.get(reverse("core:staff_dashboard"))
        self.assertEqual(manager_response.status_code, 302)
        self.assertEqual(manager_response.url, reverse("core:maintenance"))

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

        self.client.force_login(user)
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
        self.client.force_login(manager)

        feedbacks_response = self.client.get(reverse("core:staff_feedbacks"))
        self.assertEqual(feedbacks_response.status_code, 200)
        self.assertContains(feedbacks_response, "Обычное обращение")
        self.assertNotContains(feedbacks_response, "Заявка на мероприятие: Тест")

        join_response = self.client.get(reverse("core:staff_join_requests"))
        self.assertEqual(join_response.status_code, 200)
        self.assertContains(join_response, "Заявка на мероприятие: Тест")

    def test_manager_can_attach_file_in_feedback_response_and_student_can_download(self):
        student = self.create_user("student_feedback_file", role=UserProfile.ROLE_STUDENT)
        feedback = FeedbackMessage.objects.create(
            user=student,
            name="Студент",
            email="student_feedback_file@example.com",
            subject="Нужна справка",
            message="Прошу прислать образец.",
        )

        manager = self.create_user("manager_feedback_file", role=UserProfile.ROLE_MANAGER)
        self.client.force_login(manager)
        mod_file = SimpleUploadedFile(
            "answer.txt",
            b"moderator attachment",
            content_type="text/plain",
        )
        response = self.client.post(
            reverse("core:staff_feedbacks"),
            {
                "feedback_id": feedback.id,
                "status": FeedbackMessage.STATUS_RESOLVED,
                "moderation_comment": "Файл приложен.",
                "moderation_attachment": mod_file,
            },
        )
        self.assertEqual(response.status_code, 302)

        feedback.refresh_from_db()
        self.assertTrue(bool(feedback.moderation_attachment))

        self.client.force_login(student)
        my_feedbacks = self.client.get(reverse("core:my_feedbacks"))
        self.assertEqual(my_feedbacks.status_code, 200)
        self.assertContains(my_feedbacks, "Скачать файл от модератора")

    def test_resolved_feedback_cannot_be_changed_manually(self):
        manager = self.create_user("manager_closed_feedback", role=UserProfile.ROLE_MANAGER)
        feedback = FeedbackMessage.objects.create(
            name="Пользователь",
            email="closed_feedback@example.com",
            subject="Закрытое обращение",
            message="Текст",
            status=FeedbackMessage.STATUS_RESOLVED,
            moderation_comment="Первичный комментарий",
        )
        self.client.force_login(manager)

        response = self.client.post(
            reverse("core:staff_feedbacks"),
            {
                "feedback_id": feedback.id,
                "status": FeedbackMessage.STATUS_IN_PROGRESS,
                "moderation_comment": "Пытаюсь изменить закрытое обращение",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Обращение уже закрыто")
        feedback.refresh_from_db()
        self.assertEqual(feedback.status, FeedbackMessage.STATUS_RESOLVED)
        self.assertEqual(feedback.moderation_comment, "Первичный комментарий")

    def test_student_cannot_create_community_post(self):
        student = self.create_user("student_community", role=UserProfile.ROLE_STUDENT)
        self.client.force_login(student)

        response = self.client.post(
            reverse("core:community"),
            {"create_post": "1", "title": "Пост студента", "body": "Текст поста"},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(CommunityPost.objects.count(), 0)

    def test_manager_can_create_and_pin_community_post(self):
        manager = self.create_user("manager_community", role=UserProfile.ROLE_MANAGER)
        self.client.force_login(manager)

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
        self.client.force_login(student)

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

        self.client.force_login(manager)

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

    def test_join_cta_hidden_when_student_has_active_join_request(self):
        student = self.create_user("student_join_guard", role=UserProfile.ROLE_STUDENT)
        CouncilJoinApplication.objects.create(
            full_name="Тест Студент",
            email="student_guard@example.com",
            phone="+79000001111",
            faculty="it",
            course="2",
            motivation="Хочу в студсовет",
            experience="",
            status=CouncilJoinApplication.STATUS_IN_REVIEW,
            user=student,
        )
        self.client.force_login(student)

        council_response = self.client.get(reverse("core:council"))
        self.assertEqual(council_response.status_code, 200)
        self.assertNotContains(council_response, "Мы ждем тебя в нашей дружной семье")
        self.assertNotContains(council_response, "Подать заявку")

        join_response = self.client.get(reverse("core:join"))
        self.assertEqual(join_response.status_code, 302)
        self.assertEqual(join_response.url, reverse("core:my_join_requests"))

    def test_community_visible_only_for_authenticated_users(self):
        anon_response = self.client.get(reverse("core:community"))
        self.assertEqual(anon_response.status_code, 302)
        self.assertIn(reverse("login"), anon_response.url)

        home_response = self.client.get(reverse("core:home"))
        menu_items = home_response.context["main_menu"]
        self.assertFalse(any(item["view_name"] == "core:community" for item in menu_items))

        student = self.create_user("community_student", role=UserProfile.ROLE_STUDENT)
        self.client.force_login(student)
        auth_home_response = self.client.get(reverse("core:home"))
        auth_menu_items = auth_home_response.context["main_menu"]
        self.assertTrue(any(item["view_name"] == "core:community" for item in auth_menu_items))

    def test_polls_visible_only_for_authenticated_users(self):
        anon_response = self.client.get(reverse("core:polls"))
        self.assertEqual(anon_response.status_code, 302)
        self.assertIn(reverse("login"), anon_response.url)

        home_response = self.client.get(reverse("core:home"))
        menu_items = home_response.context["main_menu"]
        self.assertFalse(any(item["view_name"] == "core:polls" for item in menu_items))

        student = self.create_user("poll_student", role=UserProfile.ROLE_STUDENT)
        self.client.force_login(student)
        auth_home_response = self.client.get(reverse("core:home"))
        auth_menu_items = auth_home_response.context["main_menu"]
        self.assertTrue(any(item["view_name"] == "core:polls" for item in auth_menu_items))

    def test_manager_can_create_poll_and_student_can_vote(self):
        manager = self.create_user("poll_manager", role=UserProfile.ROLE_MANAGER)
        self.client.force_login(manager)

        create_response = self.client.post(
            reverse("core:polls"),
            {
                "create_poll": "1",
                "title": "Какой формат мероприятий выбрать?",
                "description": "Выберите один вариант",
                "option_1": "Оффлайн",
                "option_2": "Онлайн",
                "option_3": "Смешанный",
            },
        )
        self.assertEqual(create_response.status_code, 302)
        poll = Poll.objects.get(title="Какой формат мероприятий выбрать?")
        self.assertEqual(poll.options.count(), 3)

        student = self.create_user("poll_student_vote", role=UserProfile.ROLE_STUDENT)
        self.client.force_login(student)
        option = poll.options.first()
        vote_response = self.client.post(
            reverse("core:polls"),
            {"vote_poll": "1", "poll_id": poll.id, "option_id": option.id},
        )
        self.assertEqual(vote_response.status_code, 302)
        self.assertTrue(PollVote.objects.filter(poll=poll, user=student, option=option).exists())

    def test_student_cannot_create_poll(self):
        student = self.create_user("student_no_poll_create", role=UserProfile.ROLE_STUDENT)
        self.client.force_login(student)

        response = self.client.post(
            reverse("core:polls"),
            {
                "create_poll": "1",
                "title": "Недопустимый опрос",
                "option_1": "Да",
                "option_2": "Нет",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(Poll.objects.filter(title="Недопустимый опрос").exists())

    def test_gallery_page_available(self):
        response = self.client.get(reverse("core:gallery"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "core/gallery.html")

    def test_documents_page_uses_pdf_buttons(self):
        response = self.client.get(reverse("core:documents"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "core/documents_list.html")
        self.assertContains(response, "Открыть PDF")

    def test_news_detail_increments_views_count(self):
        from core.models import News

        news = News.objects.create(
            title="Тестовая новость",
            summary="Кратко",
            content="Полный текст",
            is_published=True,
        )

        self.client.get(reverse("core:news_detail", kwargs={"pk": news.pk}))
        self.client.get(reverse("core:news_detail", kwargs={"pk": news.pk}))

        news.refresh_from_db()
        self.assertEqual(news.views_count, 2)

    def test_unread_moderator_replies_badge_in_header(self):
        student = self.create_user("student_notify", role=UserProfile.ROLE_STUDENT)
        FeedbackMessage.objects.create(
            user=student,
            name="Студент",
            email="student_notify@example.com",
            subject="Проверка уведомления",
            message="Текст обращения",
            moderation_comment="Ответ модератора",
            status=FeedbackMessage.STATUS_RESOLVED,
        )
        self.client.force_login(student)

        response = self.client.get(reverse("core:home"))

        self.assertContains(response, "header-notify-badge")
        self.assertEqual(response.context["unread_moderation_count"], 1)

    def test_moderator_replies_page_marks_notifications_as_seen(self):
        student = self.create_user("student_seen", role=UserProfile.ROLE_STUDENT)
        FeedbackMessage.objects.create(
            user=student,
            name="Студент",
            email="student_seen@example.com",
            subject="Тест ответа",
            message="Текст обращения",
            moderation_comment="Обращение обработано",
            status=FeedbackMessage.STATUS_RESOLVED,
        )
        self.client.force_login(student)

        self.client.get(reverse("core:home"))
        replies_response = self.client.get(reverse("core:moderator_replies"))
        self.assertEqual(replies_response.status_code, 200)
        self.assertContains(replies_response, "Ответы модератора")
        self.assertContains(replies_response, "Обращение обработано")

        home_response = self.client.get(reverse("core:home"))
        self.assertNotContains(home_response, "header-notify-badge")

    @override_settings(DEBUG=False)
    def test_custom_404_page_shows_reason_and_suggestions(self):
        response = self.client.get("/unknowwwn-section/")

        self.assertEqual(response.status_code, 404)
        self.assertTemplateUsed(response, "404.html")
        self.assertContains(response, "Ошибка 404", status_code=404)
        self.assertContains(response, "В адресе указан неизвестный раздел", status_code=404)



