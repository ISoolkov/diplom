from difflib import get_close_matches

from django.conf import settings
from django.shortcuts import render
from django.urls import reverse


KNOWN_SECTIONS = {
    "news": ("Новости", "core:news_list"),
    "events": ("Мероприятия", "core:events_list"),
    "documents": ("Документы", "core:documents"),
    "projects": ("Проекты", "core:projects"),
    "gallery": ("Галерея", "core:gallery"),
    "faq": ("FAQ", "core:faq"),
    "feedback": ("Обратная связь", "core:feedback"),
    "council": ("О студсовете", "core:council"),
    "community": ("Соцсеть", "core:community"),
    "cabinet": ("Личный кабинет", "core:cabinet"),
    "staff": ("Панель управления", "core:staff_dashboard"),
}

RESTRICTED_SECTIONS = {"community", "cabinet", "staff"}


def _build_404_diagnostics(request, exception):
    path = request.path
    cleaned_path = path.strip("/")
    parts = [part for part in cleaned_path.split("/") if part]
    first_part = parts[0] if parts else ""
    exception_text = str(exception) if exception else ""

    reason_title = "Страница не найдена"
    reason_text = "Ссылка устарела, введен неверный адрес или нужная страница была перемещена."

    suggestions = [
        {
            "text": "Перейти на главную страницу и открыть нужный раздел через меню.",
            "url": reverse("core:home"),
            "label": "Открыть главную",
        },
        {
            "text": "Проверьте адрес в строке браузера: часто ошибка в одной букве или символе.",
            "url": "",
            "label": "",
        },
    ]

    static_url = settings.STATIC_URL.rstrip("/")
    media_url = settings.MEDIA_URL.rstrip("/")

    if static_url and path.startswith(f"{static_url}/"):
        reason_title = "Не найден статический файл"
        reason_text = "Браузер запросил CSS, JS или изображение, которого нет по указанному пути."
        suggestions.append(
            {
                "text": "Проверьте имя файла и путь в шаблоне через тег {% static %}.",
                "url": "",
                "label": "",
            }
        )
    elif media_url and path.startswith(f"{media_url}/"):
        reason_title = "Не найден пользовательский файл"
        reason_text = "Файл был удален, перемещен или ссылка на него сформирована некорректно."
        suggestions.append(
            {
                "text": "Откройте раздел файлов и проверьте, существует ли нужный документ.",
                "url": reverse("core:my_files") if request.user.is_authenticated else reverse("login"),
                "label": "Проверить файлы",
            }
        )
    elif first_part in RESTRICTED_SECTIONS and not request.user.is_authenticated:
        reason_title = "Раздел доступен только после авторизации"
        reason_text = "Вы открыли страницу, которая требует входа в систему."
        suggestions.append(
            {
                "text": "Войдите в аккаунт и повторите переход.",
                "url": f"{reverse('login')}?next={request.path}",
                "label": "Войти",
            }
        )
    elif first_part and first_part not in KNOWN_SECTIONS:
        close_match = get_close_matches(first_part, KNOWN_SECTIONS.keys(), n=1, cutoff=0.6)
        reason_title = "В адресе указан неизвестный раздел"
        reason_text = f"Раздел «{first_part}» не существует в текущей структуре сайта."
        if close_match:
            _, view_name = KNOWN_SECTIONS[close_match[0]]
            suggestions.append(
                {
                    "text": f"Возможно, вы имели в виду «{close_match[0]}».",
                    "url": reverse(view_name),
                    "label": "Открыть похожий раздел",
                }
            )
    elif first_part in {"news", "events"} and parts and parts[-1].isdigit():
        reason_title = "Запись не найдена"
        reason_text = "Страница новости или мероприятия с таким ID отсутствует."
        _, view_name = KNOWN_SECTIONS[first_part]
        suggestions.append(
            {
                "text": "Вернитесь к общему списку и выберите существующую запись.",
                "url": reverse(view_name),
                "label": "Открыть список",
            }
        )
    elif exception_text:
        reason_title = "Маршрут не распознан"
        reason_text = f"Сервер не смог сопоставить адрес с маршрутом: {exception_text}"

    return {
        "reason_title": reason_title,
        "reason_text": reason_text,
        "request_path": path,
        "suggestions": suggestions,
    }


def custom_404(request, exception):
    context = _build_404_diagnostics(request, exception)
    return render(request, "404.html", context, status=404)
