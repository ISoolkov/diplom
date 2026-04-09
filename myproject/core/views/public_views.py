import random
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import REDIRECT_FIELD_NAME, get_user_model, login
from django.contrib.auth.forms import AuthenticationForm
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Exists, F, OuterRef
from django.shortcuts import get_object_or_404, redirect, render
from django.templatetags.static import static
from django.urls import reverse
from django.utils import timezone

from core.forms import (
    AdminOTPForm,
    CommunityCommentForm,
    CommunityPostForm,
    CouncilJoinApplicationForm,
    EventManageForm,
    EventRegistrationForm,
    FeedbackForm,
    PollCreateForm,
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
    FeedbackMessage,
    News,
    Poll,
    PollOption,
    PollVote,
    Project,
    StudentCouncilMember,
    UserProfile,
)
from core.permissions import has_any_role
from core.security.totp import build_otpauth_uri, generate_totp_secret, verify_totp
from core.site_settings import get_maintenance_settings
from core.services import (
    ServiceValidationError,
    log_user_activity,
    register_for_event,
    send_new_event_announcement,
)

User = get_user_model()
SUBMISSION_COOLDOWN = timedelta(minutes=1)


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
    create_form = EventManageForm()
    invalid_form_event_id = None

    if request.method == "POST":
        if not can_manage_events:
            messages.error(request, "Недостаточно прав для редактирования анонсов.")
            target_url = reverse("core:events_list")
            if archive:
                target_url = f"{target_url}?archive=1"
            return redirect(target_url)

        action = request.POST.get("action", "update")
        if action == "create":
            create_form = EventManageForm(request.POST, request.FILES)
            if create_form.is_valid():
                event = create_form.save(commit=False)
                # Полное описание заполняем базовым текстом из анонса.
                event.description = event.short_description
                event.is_published = True
                event.save()
                send_new_event_announcement(event=event, actor=request.user)
                messages.success(request, "Новое мероприятие добавлено.")
                log_user_activity(request, "event.announcement.created", f"event_id={event.id}")
                return redirect("core:events_list")
            messages.error(request, "Проверьте поля формы нового мероприятия.")
        else:
            event = get_object_or_404(Event, pk=request.POST.get("event_id"), is_published=True)
            form = EventManageForm(request.POST, request.FILES, instance=event)
            if form.is_valid():
                form.save()
                messages.success(request, "Анонс мероприятия обновлен.")
                log_user_activity(request, "event.announcement.updated", f"event_id={event.id}")
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
            "create_form": create_form,
        },
    )


def event_detail(request, pk):
    event = get_object_or_404(Event, pk=pk, is_published=True)
    already_registered = False
    form = None

    if request.user.is_authenticated:
        already_registered = EventRegistration.objects.filter(user=request.user, event=event).exists()
        if request.method == "POST" and not already_registered:
            if EventRegistration.objects.filter(
                user=request.user,
                created_at__gte=timezone.now() - SUBMISSION_COOLDOWN,
            ).exists():
                messages.error(request, "Регистрация на мероприятия доступна не чаще одного раза в минуту.")
                return redirect("core:event_detail", pk=event.pk)

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
                    log_user_activity(request, "event.registration.created", f"event_id={event.id}")
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
        if request.user.is_authenticated:
            if FeedbackMessage.objects.filter(
                user=request.user,
                created_at__gte=timezone.now() - SUBMISSION_COOLDOWN,
            ).exists():
                messages.error(request, "Отправлять обращения можно не чаще одного раза в минуту.")
                return redirect("core:feedback")
        else:
            last_sent_ts = request.session.get("feedback_last_sent_ts")
            if last_sent_ts:
                try:
                    last_sent = timezone.datetime.fromisoformat(last_sent_ts)
                    if timezone.is_naive(last_sent):
                        last_sent = timezone.make_aware(last_sent, timezone.get_current_timezone())
                    if timezone.now() - last_sent < SUBMISSION_COOLDOWN:
                        messages.error(request, "Отправлять обращения можно не чаще одного раза в минуту.")
                        return redirect("core:feedback")
                except (ValueError, TypeError):
                    pass

        form = FeedbackForm(request.POST, request.FILES)
        if form.is_valid():
            item = form.save(commit=False)
            if request.user.is_authenticated:
                item.user = request.user
            item.save()
            request.session["feedback_last_sent_ts"] = timezone.now().isoformat()
            messages.success(request, "Ваше обращение отправлено. Спасибо за обратную связь.")
            log_user_activity(request, "feedback.created", f"feedback_id={item.id}")
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
            log_user_activity(request, "join_request.created", f"join_id={item.id}")
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
                log_user_activity(request, "community.post.created", f"post_id={post.id}")
                return redirect(f"{reverse('core:community')}#post-{post.id}")

        if "toggle_pin" in request.POST:
            post = get_object_or_404(CommunityPost, pk=request.POST.get("post_id"), is_published=True)
            pin, created = CommunityPostPin.objects.get_or_create(user=request.user, post=post)
            if created:
                messages.success(request, "Публикация закреплена у вас.")
                log_user_activity(request, "community.post.pinned_personal", f"post_id={post.id}")
            else:
                pin.delete()
                messages.success(request, "Публикация откреплена у вас.")
                log_user_activity(request, "community.post.unpinned_personal", f"post_id={post.id}")
            return redirect(f"{reverse('core:community')}#post-{post.id}")

        if "toggle_global_pin" in request.POST:
            if not can_manage_posts:
                messages.error(request, "Глобальное закрепление доступно только администратору и менеджеру.")
                return redirect(reverse("core:community"))
            post = get_object_or_404(CommunityPost, pk=request.POST.get("post_id"), is_published=True)
            post.is_pinned = not post.is_pinned
            post.save(update_fields=["is_pinned", "updated_at"])
            messages.success(request, "Глобальное закрепление публикации обновлено.")
            log_user_activity(
                request,
                "community.post.pinned_global_toggled",
                f"post_id={post.id}; pinned={post.is_pinned}",
            )
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
                log_user_activity(request, "community.comment.created", f"comment_id={comment.id}; post_id={post.id}")
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
            log_user_activity(request, "user.registered", f"user={user.username}")
            return redirect("core:cabinet")
    else:
        form = SignUpForm()
    return render(request, "registration/register.html", {"form": form})


def login_view(request):
    if request.user.is_authenticated:
        return redirect("core:cabinet")

    redirect_to = request.GET.get(REDIRECT_FIELD_NAME) or request.POST.get(REDIRECT_FIELD_NAME) or ""
    form = AuthenticationForm(request, data=request.POST or None)

    if request.method == "POST" and form.is_valid():
        user = form.get_user()
        role = getattr(getattr(user, "profile", None), "role", UserProfile.ROLE_STUDENT)

        if role == UserProfile.ROLE_ADMIN or user.is_superuser:
            request.session["pending_2fa_user_id"] = user.id
            request.session["pending_2fa_next"] = redirect_to
            request.session["pending_2fa_backend"] = getattr(user, "backend", "")
            return redirect("admin_2fa_verify")

        login(request, user)
        return redirect(redirect_to or settings.LOGIN_REDIRECT_URL)

    return render(
        request,
        "registration/login.html",
        {"form": form, REDIRECT_FIELD_NAME: redirect_to},
    )


def admin_2fa_verify(request):
    pending_user_id = request.session.get("pending_2fa_user_id")
    if not pending_user_id:
        return redirect("login")

    user = get_object_or_404(User, pk=pending_user_id)
    profile, _ = UserProfile.objects.get_or_create(user=user)

    if not profile.totp_secret:
        profile.totp_secret = generate_totp_secret()
        profile.save(update_fields=["totp_secret"])

    form = AdminOTPForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        token = form.cleaned_data["token"]
        if verify_totp(profile.totp_secret, token):
            if not profile.totp_enabled:
                profile.totp_enabled = True
                profile.save(update_fields=["totp_enabled"])

            backend = request.session.get("pending_2fa_backend") or "django.contrib.auth.backends.ModelBackend"
            login(request, user, backend=backend)
            request.session.pop("pending_2fa_user_id", None)
            request.session.pop("pending_2fa_backend", None)
            next_url = request.session.pop("pending_2fa_next", None)
            log_user_activity(request, "auth.admin_2fa.success", f"user={user.username}")
            messages.success(request, "Вход подтвержден через Google Authenticator.")
            return redirect(next_url or settings.LOGIN_REDIRECT_URL)

        log_user_activity(request, "auth.admin_2fa.failed", f"user={user.username}")
        messages.error(request, "Неверный код. Проверьте приложение Google Authenticator.")

    setup_uri = build_otpauth_uri(profile.totp_secret, user.username, issuer="MUIV StudCouncil")
    return render(
        request,
        "registration/admin_2fa_verify.html",
        {
            "form": form,
            "totp_secret": profile.totp_secret,
            "setup_uri": setup_uri,
            "is_first_setup": not profile.totp_enabled,
            "username": user.username,
        },
    )


def polls_page(request):
    if not request.user.is_authenticated:
        messages.error(request, "Раздел опросов доступен только авторизованным пользователям.")
        return redirect(f"{reverse('login')}?next={reverse('core:polls')}")

    can_create = has_any_role(
        request.user,
        UserProfile.ROLE_ADMIN,
        UserProfile.ROLE_MANAGER,
    )
    create_form = PollCreateForm()

    if request.method == "POST":
        if "create_poll" in request.POST:
            if not can_create:
                messages.error(request, "Создавать опросы могут только администратор и менеджер.")
                return redirect("core:polls")

            create_form = PollCreateForm(request.POST)
            if create_form.is_valid():
                options = []
                for key in ("option_1", "option_2", "option_3", "option_4", "option_5"):
                    value = create_form.cleaned_data.get(key, "").strip()
                    if value:
                        options.append(value)

                if len(options) < 2:
                    messages.error(request, "Добавьте минимум два варианта ответа.")
                else:
                    with transaction.atomic():
                        poll = Poll.objects.create(
                            title=create_form.cleaned_data["title"].strip(),
                            description=create_form.cleaned_data["description"].strip(),
                            created_by=request.user,
                            is_active=True,
                        )
                        for index, option_text in enumerate(options, start=1):
                            PollOption.objects.create(poll=poll, text=option_text, order=index)
                    log_user_activity(request, "poll.created", f"poll_id={poll.id}")
                    messages.success(request, "Опрос опубликован.")
                    return redirect("core:polls")

        elif "vote_poll" in request.POST:
            poll = get_object_or_404(Poll, pk=request.POST.get("poll_id"), is_active=True)
            option = get_object_or_404(PollOption, pk=request.POST.get("option_id"), poll=poll)
            vote, created = PollVote.objects.get_or_create(
                poll=poll,
                user=request.user,
                defaults={"option": option},
            )
            if not created and vote.option_id != option.id:
                vote.option = option
                vote.save(update_fields=["option", "updated_at"])
                messages.success(request, "Ваш голос обновлен.")
                log_user_activity(request, "poll.vote.updated", f"poll_id={poll.id}; option_id={option.id}")
            else:
                messages.success(request, "Ваш голос принят.")
                log_user_activity(request, "poll.vote.created", f"poll_id={poll.id}; option_id={option.id}")
            return redirect("core:polls")

    polls = Poll.objects.filter(is_active=True).prefetch_related("options__votes", "created_by")
    user_votes = {vote.poll_id: vote.option_id for vote in PollVote.objects.filter(user=request.user)}

    poll_rows = []
    for poll in polls:
        option_rows = []
        total_votes = 0
        for option in poll.options.all():
            votes_count = option.votes.count()
            total_votes += votes_count
            option_rows.append({"id": option.id, "text": option.text, "votes_count": votes_count})

        poll_rows.append(
            {
                "id": poll.id,
                "title": poll.title,
                "description": poll.description,
                "created_at": poll.created_at,
                "created_by": poll.created_by,
                "total_votes": total_votes,
                "user_option_id": user_votes.get(poll.id),
                "options": option_rows,
            }
        )

    return render(
        request,
        "core/polls.html",
        {
            "polls": poll_rows,
            "can_create_polls": can_create,
            "poll_create_form": create_form,
        },
    )


def maintenance_page(request):
    settings_obj = get_maintenance_settings()
    return render(
        request,
        "core/maintenance.html",
        {
            "maintenance_enabled": settings_obj.maintenance_enabled,
            "maintenance_ends_at": settings_obj.maintenance_ends_at,
        },
    )


