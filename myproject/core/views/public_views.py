from django.contrib import messages
from django.contrib.auth import login
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from core.forms import (
    CommunityCommentForm,
    CommunityPostForm,
    CouncilJoinApplicationForm,
    EventRegistrationForm,
    FeedbackForm,
    SignUpForm,
)
from core.models import (
    CommunityPost,
    Document,
    Event,
    EventRegistration,
    FAQ,
    News,
    Project,
    StudentCouncilMember,
    UserProfile,
)
from core.services import ServiceValidationError, register_for_event


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
    return render(request, "core/news_detail.html", {"item": item})


def events_list(request):
    queryset = Event.objects.filter(is_published=True)
    archive = request.GET.get("archive")
    if archive == "1":
        queryset = queryset.filter(start_at__lt=timezone.now()).order_by("-start_at")
    else:
        queryset = queryset.filter(start_at__gte=timezone.now()).order_by("start_at")
    return render(request, "core/events_list.html", {"events": queryset, "archive": archive == "1"})


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
    docs = Document.objects.filter(is_published=True)
    return render(request, "core/documents_list.html", {"documents": docs})


def projects_list(request):
    projects = Project.objects.filter(is_published=True)
    return render(request, "core/projects_list.html", {"projects": projects})


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
    post_form = CommunityPostForm()
    comment_form = CommunityCommentForm()

    if request.method == "POST":
        if not request.user.is_authenticated:
            messages.error(request, "Для публикации и комментариев выполните вход.")
            return redirect(f"{reverse('login')}?next={reverse('core:community')}")

        if "create_post" in request.POST:
            post_form = CommunityPostForm(request.POST)
            if post_form.is_valid():
                post = post_form.save(commit=False)
                post.author = request.user
                post.save()
                messages.success(request, "Публикация добавлена в сообщество.")
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

    posts = (
        CommunityPost.objects.filter(is_published=True)
        .select_related("author")
        .prefetch_related("comments__author")
    )

    return render(
        request,
        "core/community_feed.html",
        {
            "posts": posts,
            "post_form": post_form,
            "comment_form": comment_form,
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
