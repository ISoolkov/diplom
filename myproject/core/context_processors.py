from django.urls import NoReverseMatch, reverse

from .models import UserProfile
from .permissions import get_user_role, has_any_role

AUTHOR_FULL_NAME = "Иванов Иван Иванович"

PAGE_TITLES = {
    "core:home": "Главная",
    "core:council": "Студсовет",
    "core:news_list": "Новости",
    "core:news_detail": "Новость",
    "core:events_list": "Мероприятия",
    "core:event_detail": "Мероприятие",
    "core:community": "Сообщество",
    "core:join": "Вступить в студсовет",
    "core:documents": "Документы",
    "core:projects": "Проекты",
    "core:faq": "FAQ",
    "core:feedback": "Обратная связь",
    "login": "Вход",
    "core:register": "Регистрация",
    "core:cabinet": "Личный кабинет",
    "core:profile_edit": "Профиль",
    "core:my_feedbacks": "Мои обращения",
    "core:my_events": "Мои мероприятия",
    "core:my_join_requests": "Мои заявки в студсовет",
    "core:my_posts": "Мои публикации",
    "core:my_files": "Мои файлы",
    "core:staff_dashboard": "Админ-панель",
    "core:staff_feedbacks": "Модерация обращений",
    "core:staff_join_requests": "Модерация заявок",
    "core:staff_users": "Пользователи и роли",
    "core:staff_files": "Файловое хранилище",
    "core:staff_reports": "Экспорт отчетов",
}

MAIN_MENU = [
    ("core:home", "Главная"),
    ("core:council", "Студсовет"),
    ("core:news_list", "Новости"),
    ("core:events_list", "Мероприятия"),
    ("core:projects", "Проекты"),
    ("core:documents", "Документы"),
    ("core:faq", "FAQ"),
    ("core:community", "Сообщество"),
    ("core:feedback", "Обратная связь"),
    ("core:join", "Вступить"),
]

CABINET_MENU = [
    ("core:cabinet", "Обзор"),
    ("core:profile_edit", "Профиль"),
    ("core:my_events", "Мероприятия"),
    ("core:my_feedbacks", "Обращения"),
    ("core:my_join_requests", "Заявки"),
    ("core:my_posts", "Публикации"),
    ("core:my_files", "Файлы"),
]

STAFF_MENU = [
    ("core:staff_dashboard", "Дашборд"),
    ("core:staff_feedbacks", "Обращения"),
    ("core:staff_join_requests", "Заявки"),
    ("core:staff_users", "Пользователи"),
    ("core:staff_files", "Файлы"),
    ("core:staff_reports", "Отчеты"),
]


def _resolve_menu(items):
    resolved = []
    for view_name, label in items:
        try:
            url = reverse(view_name)
        except NoReverseMatch:
            continue
        resolved.append({"view_name": view_name, "label": label, "url": url})
    return resolved


def navigation_context(request):
    resolver = request.resolver_match
    view_name = resolver.view_name if resolver else ""

    breadcrumbs = [{"title": "Главная", "url": reverse("core:home")}]
    if view_name and view_name != "core:home":
        breadcrumbs.append({"title": PAGE_TITLES.get(view_name, "Страница"), "url": None})

    return {
        "main_menu": _resolve_menu(MAIN_MENU),
        "cabinet_menu": _resolve_menu(CABINET_MENU),
        "staff_menu": _resolve_menu(STAFF_MENU),
        "breadcrumbs": breadcrumbs,
        "author_full_name": AUTHOR_FULL_NAME,
        "user_role": get_user_role(request.user),
        "is_staff_admin": has_any_role(request.user, UserProfile.ROLE_ADMIN),
    }

