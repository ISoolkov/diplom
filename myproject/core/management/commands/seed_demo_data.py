from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import (
    CommunityPost,
    Document,
    Event,
    FAQ,
    News,
    Project,
    StudentCouncilMember,
    UserProfile,
)

User = get_user_model()


class Command(BaseCommand):
    help = "Создает тестовые данные для портала студенческого совета МУИВ."

    def _ensure_user(self, *, username, password, first_name, last_name, email, role, is_superuser=False):
        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                "first_name": first_name,
                "last_name": last_name,
                "email": email,
                "is_staff": is_superuser,
                "is_superuser": is_superuser,
            },
        )

        changed = created
        if user.first_name != first_name:
            user.first_name = first_name
            changed = True
        if user.last_name != last_name:
            user.last_name = last_name
            changed = True
        if user.email != email:
            user.email = email
            changed = True
        if user.is_staff != is_superuser:
            user.is_staff = is_superuser
            changed = True
        if user.is_superuser != is_superuser:
            user.is_superuser = is_superuser
            changed = True

        if not user.check_password(password):
            user.set_password(password)
            changed = True

        if changed:
            user.save()

        profile, _ = UserProfile.objects.get_or_create(user=user)
        if profile.role != role:
            profile.role = role
            profile.save(update_fields=["role"])

        return user

    def handle(self, *args, **options):
        now = timezone.now()

        admin_user = self._ensure_user(
            username="admin_demo",
            password="AdminDemo123!",
            first_name="Админ",
            last_name="Демо",
            email="admin_demo@example.com",
            role=UserProfile.ROLE_ADMIN,
            is_superuser=True,
        )
        manager_user = self._ensure_user(
            username="manager_demo",
            password="ManagerDemo123!",
            first_name="Менеджер",
            last_name="Демо",
            email="manager_demo@example.com",
            role=UserProfile.ROLE_MANAGER,
        )
        self._ensure_user(
            username="student_demo",
            password="StudentDemo123!",
            first_name="Студент",
            last_name="Демо",
            email="student_demo@example.com",
            role=UserProfile.ROLE_STUDENT,
        )

        for i in range(1, 6):
            News.objects.get_or_create(
                title=f"Новости студсовета №{i}",
                defaults={
                    "summary": f"Краткий анонс новости студсовета №{i}.",
                    "content": (
                        f"Подробная новость студсовета №{i}. "
                        "Здесь публикуются решения, инициативы и отчеты о мероприятиях."
                    ),
                    "published_at": now - timedelta(days=i),
                    "is_published": True,
                },
            )

        for i in range(1, 5):
            Event.objects.get_or_create(
                title=f"Мероприятие студсовета №{i}",
                defaults={
                    "short_description": f"Анонс мероприятия студсовета №{i}.",
                    "description": (
                        "Подробная информация о событии: программа, формат участия и контакты организаторов."
                    ),
                    "location": "Москва, 2-й Кожуховский пр-д, 12, стр. 1",
                    "start_at": now + timedelta(days=i * 5),
                    "registration_deadline": now + timedelta(days=i * 5 - 1),
                    "is_published": True,
                },
            )

        Document.objects.get_or_create(
            title="Положение о Студенческом совете",
            defaults={
                "description": "Официальное положение о деятельности студенческого совета МУИВ.",
                "file_url": "https://example.com/polozhenie-studsovet.pdf",
                "is_published": True,
            },
        )
        Document.objects.get_or_create(
            title="Регламент работы студсовета",
            defaults={
                "description": "Порядок работы, заседаний и рассмотрения инициатив студентов.",
                "file_url": "https://example.com/reglament-studsovet.pdf",
                "is_published": True,
            },
        )

        Project.objects.get_or_create(
            title="Школа актива",
            defaults={
                "description": "Обучение активистов проектной работе, коммуникациям и лидерству.",
                "status": "active",
                "is_published": True,
            },
        )
        Project.objects.get_or_create(
            title="Волонтерский корпус",
            defaults={
                "description": "Организация и координация добровольческих инициатив студентов.",
                "status": "done",
                "is_published": True,
            },
        )

        FAQ.objects.get_or_create(
            question="Как вступить в студсовет?",
            defaults={
                "answer": "Заполните форму в разделе «Вступить», после чего с вами свяжется команда студсовета.",
                "order": 1,
                "is_published": True,
            },
        )
        FAQ.objects.get_or_create(
            question="Где смотреть анонсы мероприятий?",
            defaults={
                "answer": "В разделе «Мероприятия», а также в ленте социальной сети студсовета.",
                "order": 2,
                "is_published": True,
            },
        )
        FAQ.objects.get_or_create(
            question="Как предложить инициативу?",
            defaults={
                "answer": "Опубликуйте идею в соцсети студсовета или отправьте обращение через форму обратной связи.",
                "order": 3,
                "is_published": True,
            },
        )

        StudentCouncilMember.objects.get_or_create(
            full_name="Пекарусь Ярослав Олегович",
            defaults={
                "position": "Начальник отдела молодежной политики",
                "bio": "Координация молодежной политики и воспитательной деятельности.",
                "order": 1,
            },
        )
        StudentCouncilMember.objects.get_or_create(
            full_name="Фандей Анна Руслановна",
            defaults={
                "position": "Заместитель начальника",
                "bio": "Сопровождение студенческих инициатив и коммуникаций.",
                "order": 2,
            },
        )

        if not CommunityPost.objects.filter(is_published=True).exists():
            CommunityPost.objects.create(
                author=manager_user,
                title="Идеи для весеннего фестиваля",
                body="Делимся предложениями по программе, площадкам и форматам проведения фестиваля.",
                is_pinned=True,
                is_published=True,
            )

        if not CommunityPost.objects.filter(author=admin_user, is_published=True).exists():
            CommunityPost.objects.create(
                author=admin_user,
                title="План встреч на месяц",
                body="Публикуем календарь собраний и проектных сессий студенческого совета.",
                is_pinned=False,
                is_published=True,
            )

        self.stdout.write(self.style.SUCCESS("Тестовые данные и роли пользователей успешно созданы."))

