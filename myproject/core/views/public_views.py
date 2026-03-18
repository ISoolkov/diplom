import random
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.core.paginator import Paginator
from django.db.models import Exists, F, OuterRef
from django.shortcuts import get_object_or_404, redirect, render
from django.templatetags.static import static
from django.urls import reverse
from django.utils import timezone

from core.forms import (
    CommunityCommentForm,
    CommunityPostForm,
    CouncilJoinApplicationForm,
    EventManageForm,
    EventRegistrationForm,
    FeedbackForm,
    SignUpForm,
)
from core.models import (
    CommunityPostPin,
    CommunityPost,
    CouncilJoinApplication,
    Document,
    Event,
    EventRegistration,
    FAQ,
    News,
    Project,
    StudentCouncilMember,
    UserProfile,
)
from core.permissions import has_any_role
from core.services import ServiceValidationError, register_for_event


def _document_display_name(filename):
    names_map = {
        "Ustav-MUIV-ot-04.10.2023.pdf": "Устав МУИВ (редакция от 04.10.2023)",
        "лицензия на осуществеление образовательной деятельности.pdf": "Лицензия на осуществление образовательной деятельности",
        "выписка из реестра лицензий.pdf": "Выписка из реестра лицензий",
        "Reestrovaya-vypiska.pdf": "Реестровая выписка (госаккредитация)",
        "Pr.55.-Ob-utverzhdenii-Polozheniya-o-Studencheskom-sovete.pdf": "Положение о Студенческом совете (приказ №55)",
        "Pravila-vnutrennego-trudovogo-rasporyadka.pdf": "Правила внутреннего трудового распорядка",
        "Pravila-vnutrennego-rasporyadka-dlya-obuchayushchikhsya-_2_.pdf": "Правила внутреннего распорядка для обучающихся",
        "Pravila-vnutrennego-rasporyadka-dlya-obuchayushchikhsya-_2_ (1).pdf": "Правила внутреннего распорядка для обучающихся (копия)",
        "Pr.-59.-Pravila-priema-na-programmy-SPO-v-2025_2026-u.g.pdf": "Правила приема на программы СПО (2025/2026)",
        "Pr.12.-Ob-utverzhd.-Pravil-priema-na-programmy-VO-v-2025_2026-ucheb.-godu-_1_-_1_.pdf": "Правила приема на программы ВО (2025/2026)",
        "Pr.47.-Ob-utverzhd.-Pravil-priema-v-Universitet-na-obraz.programmy-SPO-v-....pdf": "Правила приема в Университет на программы СПО (приказ №47)",
        "Pravila-priema-VO-26_27ug.-doc.pdf": "Правила приема в Университет на программы ВО (2026/2027)",
        "d743f3286f2c80c2081223561bb0b61c.pdf": "Предписание Рособрнадзора об устранении нарушений",
        "201d80156b430f65e2ad4204d31382f7.pdf": "Официальный документ университета (скан №1)",
        "74f19e8d4ee006cd896408aa107a10c0.pdf": "Официальный документ университета (скан №2)",
    }
    return names_map.get(filename, filename.rsplit(".", 1)[0].replace("-", " "))


def _document_category(filename):
    lower_name = filename.lower()
    if any(token in lower_name for token in ("приема", "pravil-priema", "spo", "vo-")):
        return "Прием и поступление"
    if any(token in lower_name for token in ("лиценз", "выпис", "reestrovaya")):
        return "Лицензирование и аккредитация"
    if any(token in lower_name for token in ("устав", "trudovogo", "rasporyadka", "studencheskom-sovete")):
        return "Локальные нормативные акты"
    return "Прочие официальные документы"


def home(request):
    latest_news = News.objects.filter(is_published=True)[:6]
    upcoming_events = Event.objects.filter(is_published=True, start_at__gte=timezone.now())[:6]
    active_projects = Project.objects.filter(is_published=True)[:6]
    community_posts = CommunityPost.objects.filter(is_published=True).select_related("author")[:3]
    return render(
        request,
        "core/home.html",
        {
            "latest_news": latest_news,
            "upcoming_events": upcoming_events,
            "active_projects": active_projects,
            "community_posts": community_posts,
        },
    )


def news_list(request):
    queryset = News.objects.filter(is_published=True)
    paginator = Paginator(queryset, 10)
    page_obj = paginator.get_page(request.GET.get("page"))
    return render(request, "core/news_list.html", {"page_obj": page_obj})


def news_detail(request, pk):
    item = get_object_or_404(News, pk=pk, is_published=True)
    News.objects.filter(pk=item.pk).update(views_count=F("views_count") + 1)
    item.refresh_from_db(fields=["views_count"])
    return render(request, "core/news_detail.html", {"item": item})


def events_list(request):
    can_manage_events = has_any_role(
        request.user,
        UserProfile.ROLE_ADMIN,
        UserProfile.ROLE_MANAGER,
    )

    archive = request.GET.get("archive") == "1" or request.POST.get("archive") == "1"
    queryset = Event.objects.filter(is_published=True)
    if archive:
        queryset = queryset.filter(start_at__lt=timezone.now()).order_by("-start_at")
    else:
        queryset = queryset.filter(start_at__gte=timezone.now()).order_by("start_at")

    events = list(queryset)
    invalid_form_event_id = None

    if request.method == "POST":
        if not can_manage_events:
            messages.error(request, "Недостаточно прав для редактирования анонсов.")
            target_url = reverse("core:events_list")
            if archive:
                target_url = f"{target_url}?archive=1"
            return redirect(target_url)

        event = get_object_or_404(Event, pk=request.POST.get("event_id"), is_published=True)
        form = EventManageForm(request.POST, instance=event)
        if form.is_valid():
            form.save()
            messages.success(request, "Анонс мероприятия обновлен.")
            target_url = reverse("core:events_list")
            if archive:
                target_url = f"{target_url}?archive=1"
            return redirect(target_url)

        messages.error(request, "Проверьте поля формы и попробуйте снова.")
        invalid_form_event_id = event.pk

    if can_manage_events:
        for event in events:
            if event.pk == invalid_form_event_id and request.method == "POST":
                event.edit_form = form
            else:
                event.edit_form = EventManageForm(instance=event)

    return render(
        request,
        "core/events_list.html",
        {
            "events": events,
            "archive": archive,
            "can_manage_events": can_manage_events,
        },
    )


def event_detail(request, pk):
    event = get_object_or_404(Event, pk=pk, is_published=True)
    already_registered = False
    form = None

    if request.user.is_authenticated:
        already_registered = EventRegistration.objects.filter(user=request.user, event=event).exists()
        if request.method == "POST" and not already_registered:
            form = EventRegistrationForm(request.POST)
            if form.is_valid():
                try:
                    register_for_event(
                        user=request.user,
                        event=event,
                        comment=form.cleaned_data["comment"],
                        model_cls=EventRegistration,
                    )
                except ServiceValidationError as exc:
                    messages.error(request, str(exc))
                else:
                    messages.success(request, "Заявка на мероприятие отправлена.")
                    return redirect("core:event_detail", pk=event.pk)
        else:
            form = EventRegistrationForm()

    return render(
        request,
        "core/event_detail.html",
        {"event": event, "form": form, "already_registered": already_registered},
    )


def council_info(request):
    members = StudentCouncilMember.objects.all()
    return render(request, "core/council_info.html", {"members": members})


def documents_list(request):
    docs_folder = Path(settings.BASE_DIR) / "static" / "docs"
    grouped_documents = {}
    if docs_folder.exists():
        for file in sorted(docs_folder.glob("*.pdf")):
            category = _document_category(file.name)
            grouped_documents.setdefault(category, []).append(
                {
                    "title": _document_display_name(file.name),
                    "file_url": static(f"docs/{file.name}"),
                    "size_kb": round(file.stat().st_size / 1024, 1),
                    "filename": file.name,
                }
            )

    return render(
        request,
        "core/documents_list.html",
        {"grouped_documents": grouped_documents},
    )


def projects_list(request):
    projects = Project.objects.filter(is_published=True)
    return render(request, "core/projects_list.html", {"projects": projects})


def gallery(request):
    gallery_dir = Path(settings.BASE_DIR) / "static" / "img" / "gallery"
    all_images = []
    if gallery_dir.exists():
        all_images = sorted(
            [
                f"img/gallery/{file.name}"
                for file in gallery_dir.iterdir()
                if file.is_file() and file.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}
            ]
        )

    slider_images = []
    if all_images:
        system_random = random.SystemRandom()
        slider_size = min(7, len(all_images))
        previous_slider = request.session.get("gallery_slider_images", [])

        # Avoid showing the exact same slider set/order as on previous page load.
        for _ in range(10):
            candidate = system_random.sample(all_images, slider_size)
            if candidate != previous_slider:
                slider_images = candidate
                break

        if not slider_images:
            slider_images = system_random.sample(all_images, slider_size)

        request.session["gallery_slider_images"] = slider_images

    return render(
        request,
        "core/gallery.html",
        {"slider_images": slider_images, "all_images": all_images},
    )


def faq_list(request):
    faq_items = FAQ.objects.filter(is_published=True)
    return render(request, "core/faq_list.html", {"faq_items": faq_items})


def feedback_create(request):
    if request.method == "POST":
        form = FeedbackForm(request.POST)
        if form.is_valid():
            item = form.save(commit=False)
            if request.user.is_authenticated:
                item.user = request.user
            item.save()
            messages.success(request, "Ваше обращение отправлено. Спасибо за обратную связь.")
            return redirect("core:feedback")
    else:
        initial = {}
        if request.user.is_authenticated:
            full_name = f"{request.user.first_name} {request.user.last_name}".strip()
            initial = {"name": full_name or request.user.username, "email": request.user.email}
        form = FeedbackForm(initial=initial)
    return render(request, "core/feedback.html", {"form": form})


def join_request_create(request):
    if request.user.is_authenticated:
        has_active_join_request = CouncilJoinApplication.objects.filter(
            user=request.user,
            status__in=[
                CouncilJoinApplication.STATUS_NEW,
                CouncilJoinApplication.STATUS_IN_REVIEW,
                CouncilJoinApplication.STATUS_APPROVED,
            ],
        ).exists()
        if has_active_join_request:
            messages.info(request, "У вас уже есть активная заявка на вступление в студсовет.")
            return redirect("core:my_join_requests")

    if request.method == "POST":
        form = CouncilJoinApplicationForm(request.POST)
        if form.is_valid():
            item = form.save(commit=False)
            if request.user.is_authenticated:
                item.user = request.user
            item.save()
            messages.success(request, "Заявка на вступление в студсовет отправлена.")
            return redirect("core:join")
    else:
        initial = {}
        if request.user.is_authenticated:
            full_name = f"{request.user.first_name} {request.user.last_name}".strip()
            profile = getattr(request.user, "profile", None)
            initial = {
                "full_name": full_name or request.user.username,
                "email": request.user.email,
                "course": profile.course if profile else "",
            }
        form = CouncilJoinApplicationForm(initial=initial)
    return render(request, "core/join_request.html", {"form": form})


def community_feed(request):
    if not request.user.is_authenticated:
        messages.error(request, "Раздел соцсети доступен только авторизованным пользователям.")
        return redirect(f"{reverse('login')}?next={reverse('core:community')}")

    can_manage_posts = has_any_role(
        request.user,
        UserProfile.ROLE_ADMIN,
        UserProfile.ROLE_MANAGER,
    )
    post_form = CommunityPostForm()
    comment_form = CommunityCommentForm()

    if request.method == "POST":
        if "create_post" in request.POST:
            if not can_manage_posts:
                messages.error(request, "Публиковать посты могут только администратор и менеджер.")
                return redirect(reverse("core:community"))
            post_form = CommunityPostForm(request.POST)
            if post_form.is_valid():
                post = post_form.save(commit=False)
                post.author = request.user
                post.save()
                messages.success(request, "Публикация добавлена в соцсеть.")
                return redirect(f"{reverse('core:community')}#post-{post.id}")

        if "toggle_pin" in request.POST:
            post = get_object_or_404(CommunityPost, pk=request.POST.get("post_id"), is_published=True)
            pin, created = CommunityPostPin.objects.get_or_create(user=request.user, post=post)
            if created:
                messages.success(request, "Публикация закреплена у вас.")
            else:
                pin.delete()
                messages.success(request, "Публикация откреплена у вас.")
            return redirect(f"{reverse('core:community')}#post-{post.id}")

        if "toggle_global_pin" in request.POST:
            if not can_manage_posts:
                messages.error(request, "Глобальное закрепление доступно только администратору и менеджеру.")
                return redirect(reverse("core:community"))
            post = get_object_or_404(CommunityPost, pk=request.POST.get("post_id"), is_published=True)
            post.is_pinned = not post.is_pinned
            post.save(update_fields=["is_pinned", "updated_at"])
            messages.success(request, "Глобальное закрепление публикации обновлено.")
            return redirect(f"{reverse('core:community')}#post-{post.id}")

        if "add_comment" in request.POST:
            post_id = request.POST.get("post_id")
            post = get_object_or_404(CommunityPost, pk=post_id, is_published=True)
            comment_form = CommunityCommentForm(request.POST)
            if comment_form.is_valid():
                comment = comment_form.save(commit=False)
                comment.author = request.user
                comment.post = post
                comment.save()
                messages.success(request, "Комментарий опубликован.")
                return redirect(f"{reverse('core:community')}#post-{post.id}")

    posts = CommunityPost.objects.filter(is_published=True).select_related("author").prefetch_related("comments__author")
    pinned_post_ids = set()
    if request.user.is_authenticated:
        pinned_subquery = CommunityPostPin.objects.filter(user=request.user, post_id=OuterRef("pk"))
        posts = posts.annotate(is_user_pinned=Exists(pinned_subquery)).order_by(
            "-is_user_pinned", "-is_pinned", "-created_at"
        )
        pinned_post_ids = set(
            CommunityPostPin.objects.filter(user=request.user).values_list("post_id", flat=True)
        )
    return render(
        request,
        "core/community_feed.html",
        {
            "posts": posts,
            "post_form": post_form,
            "comment_form": comment_form,
            "can_manage_posts": can_manage_posts,
            "pinned_post_ids": pinned_post_ids,
        },
    )


def register(request):
    if request.user.is_authenticated:
        return redirect("core:cabinet")
    if request.method == "POST":
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            profile, _ = UserProfile.objects.get_or_create(user=user)
            profile.role = UserProfile.ROLE_STUDENT
            profile.save(update_fields=["role"])
            login(request, user)
            messages.success(request, "Регистрация выполнена успешно.")
            return redirect("core:cabinet")
    else:
        form = SignUpForm()
    return render(request, "registration/register.html", {"form": form})


