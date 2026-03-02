from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import CommunityPost, Document, Event, FAQ, News, Project, StudentCouncilMember

User = get_user_model()


class Command(BaseCommand):
    help = "Создает тестовые данные для портала студенческого совета МУИВ."

    def handle(self, *args, **options):
        now = timezone.now()

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

        for i in range(1, 4):
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
            author = User.objects.order_by("id").first()
            if author:
                CommunityPost.objects.create(
                    author=author,
                    title="Идеи для весеннего фестиваля",
                    body="Делимся предложениями по программе, площадкам и форматам проведения фестиваля.",
                    is_pinned=True,
                    is_published=True,
                )

        self.stdout.write(self.style.SUCCESS("Тестовые данные для студсовета успешно созданы."))
