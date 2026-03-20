from django.urls import NoReverseMatch, reverse

from .models import CouncilJoinApplication, FeedbackMessage, UserProfile
from .permissions import get_user_role, has_any_role

AUTHOR_FULL_NAME = "Чубун Илья Валерьевич"

PAGE_TITLES = {
    "core:home": "Главная",
    "core:council": "Студсовет",
    "core:news_list": "Новости",
    "core:news_detail": "Новость",
    "core:events_list": "Мероприятия",
    "core:event_detail": "Мероприятие",
    "core:community": "Соцсеть",
    "core:join": "Вступить в студсовет",
    "core:documents": "Документы",
    "core:projects": "Проекты",
    "core:gallery": "Галерея",
    "core:faq": "FAQ",
    "core:feedback": "Обратная связь",
    "login": "Вход",
    "core:register": "Регистрация",
    "core:cabinet": "Личный кабинет",
    "core:profile_edit": "Профиль",
    "core:my_feedbacks": "Мои обращения",
    "core:my_events": "Мои мероприятия",
    "core:my_join_requests": "Мои заявки в студсовет",
    "core:moderator_replies": "Ответы модератора",
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
    ("core:gallery", "Галерея"),
    ("core:documents", "Документы"),
    ("core:faq", "FAQ"),
    ("core:community", "Соцсеть"),
    ("core:feedback", "Обратная связь"),
]

CABINET_MENU = [
    ("core:cabinet", "Обзор"),
    ("core:profile_edit", "Профиль"),
    ("core:my_events", "Мероприятия"),
    ("core:my_feedbacks", "Обращения"),
    ("core:my_join_requests", "Заявки"),
    ("core:moderator_replies", "Ответы"),
    ("core:my_posts", "Публикации"),
    ("core:my_files", "Файлы"),
]

STAFF_MENU_ADMIN = [
    ("core:staff_dashboard", "Дашборд"),
    ("core:staff_feedbacks", "Обращения"),
    ("core:staff_join_requests", "Заявки"),
    ("core:staff_users", "Пользователи"),
    ("core:staff_files", "Файлы"),
    ("core:staff_reports", "Отчеты"),
]

STAFF_MENU_MANAGER = [
    ("core:staff_dashboard", "Дашборд"),
    ("core:staff_feedbacks", "Обращения"),
    ("core:staff_join_requests", "Заявки"),
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
    user_role = get_user_role(request.user)
    is_staff_admin = has_any_role(request.user, UserProfile.ROLE_ADMIN)
    is_staff_panel = has_any_role(request.user, UserProfile.ROLE_ADMIN, UserProfile.ROLE_MANAGER)

    has_active_join_request = False
    unread_moderation_count = 0
    if request.user.is_authenticated:
        has_active_join_request = CouncilJoinApplication.objects.filter(
            user=request.user,
            status__in=[
                CouncilJoinApplication.STATUS_NEW,
                CouncilJoinApplication.STATUS_IN_REVIEW,
                CouncilJoinApplication.STATUS_APPROVED,
            ],
        ).exists()
        if not is_staff_panel:
            profile = getattr(request.user, "profile", None)
            seen_at = profile.moderator_replies_seen_at if profile else None

            feedback_qs = FeedbackMessage.objects.filter(
                user=request.user,
                moderation_comment__isnull=False,
            ).exclude(moderation_comment__exact="")
            join_qs = CouncilJoinApplication.objects.filter(
                user=request.user,
                moderation_comment__isnull=False,
            ).exclude(moderation_comment__exact="")

            if seen_at:
                feedback_qs = feedback_qs.filter(updated_at__gt=seen_at)
                join_qs = join_qs.filter(updated_at__gt=seen_at)

            unread_moderation_count = feedback_qs.count() + join_qs.count()

    show_join_cta = (
        not request.user.is_authenticated
        or (not is_staff_panel and not has_active_join_request)
    )

    if is_staff_admin:
        staff_menu_items = STAFF_MENU_ADMIN
    elif user_role == UserProfile.ROLE_MANAGER:
        staff_menu_items = STAFF_MENU_MANAGER
    else:
        staff_menu_items = []

    breadcrumbs = [{"title": "Главная", "url": reverse("core:home")}]
    if view_name and view_name != "core:home":
        breadcrumbs.append({"title": PAGE_TITLES.get(view_name, "Страница"), "url": None})

    main_menu_items = MAIN_MENU
    if not request.user.is_authenticated:
        main_menu_items = [item for item in MAIN_MENU if item[0] != "core:community"]

    return {
        "main_menu": _resolve_menu(main_menu_items),
        "cabinet_menu": _resolve_menu(CABINET_MENU),
        "staff_menu": _resolve_menu(staff_menu_items),
        "breadcrumbs": breadcrumbs,
        "author_full_name": AUTHOR_FULL_NAME,
        "user_role": user_role,
        "is_staff_admin": is_staff_admin,
        "is_staff_panel": is_staff_panel,
        "show_join_cta": show_join_cta,
        "has_active_join_request": has_active_join_request,
        "unread_moderation_count": unread_moderation_count,
    }

