from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import FileResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from core.forms import ProfileUpdateForm, UserFileUploadForm, UserUpdateForm
from core.models import (
    CommunityPost,
    CouncilJoinApplication,
    EventRegistration,
    FeedbackMessage,
    UserFile,
    UserProfile,
)
from core.permissions import has_any_role
from core.services import EVENT_REGISTRATION_SUBJECT_PREFIX, log_user_activity


@login_required
def cabinet(request):
    is_staff_panel = has_any_role(request.user, UserProfile.ROLE_ADMIN, UserProfile.ROLE_MANAGER)

    if is_staff_panel:
        feedbacks = FeedbackMessage.objects.exclude(subject__startswith=EVENT_REGISTRATION_SUBJECT_PREFIX)[:5]
        registrations = EventRegistration.objects.select_related("event", "user")[:5]
        join_requests = CouncilJoinApplication.objects.select_related("user")[:5]
    else:
        feedbacks = FeedbackMessage.objects.filter(user=request.user).exclude(
            subject__startswith=EVENT_REGISTRATION_SUBJECT_PREFIX
        )[:5]
        registrations = EventRegistration.objects.filter(user=request.user).select_related("event")[:5]
        join_requests = CouncilJoinApplication.objects.filter(user=request.user)[:5]

    my_posts = CommunityPost.objects.filter(author=request.user)[:5]
    my_files = UserFile.objects.filter(owner=request.user)[:5]
    return render(
        request,
        "core/cabinet.html",
        {
            "feedbacks": feedbacks,
            "registrations": registrations,
            "join_requests": join_requests,
            "my_posts": my_posts,
            "my_files": my_files,
        },
    )


@login_required
def profile_edit(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    if request.method == "POST":
        user_form = UserUpdateForm(request.POST, instance=request.user)
        profile_form = ProfileUpdateForm(request.POST, instance=profile)
        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile_form.save()
            messages.success(request, "Профиль обновлен.")
            log_user_activity(request, "cabinet.profile.updated")
            return redirect("core:profile_edit")
    else:
        user_form = UserUpdateForm(instance=request.user)
        profile_form = ProfileUpdateForm(instance=profile)
    return render(
        request,
        "core/profile_edit.html",
        {"user_form": user_form, "profile_form": profile_form},
    )


@login_required
def my_feedbacks(request):
    is_staff_panel = has_any_role(request.user, UserProfile.ROLE_ADMIN, UserProfile.ROLE_MANAGER)
    if is_staff_panel:
        items = FeedbackMessage.objects.exclude(subject__startswith=EVENT_REGISTRATION_SUBJECT_PREFIX)
    else:
        items = FeedbackMessage.objects.filter(user=request.user).exclude(
            subject__startswith=EVENT_REGISTRATION_SUBJECT_PREFIX
        )
    return render(request, "core/my_feedbacks.html", {"items": items, "is_staff_panel": is_staff_panel})


@login_required
def my_events(request):
    is_staff_panel = has_any_role(request.user, UserProfile.ROLE_ADMIN, UserProfile.ROLE_MANAGER)
    if is_staff_panel:
        items = EventRegistration.objects.select_related("event", "user")
        event_requests = FeedbackMessage.objects.select_related("user").filter(
            subject__startswith=EVENT_REGISTRATION_SUBJECT_PREFIX
        )
    else:
        items = EventRegistration.objects.filter(user=request.user).select_related("event")
        event_requests = FeedbackMessage.objects.none()
    return render(
        request,
        "core/my_events.html",
        {"items": items, "event_requests": event_requests, "is_staff_panel": is_staff_panel},
    )


@login_required
def my_join_requests(request):
    is_staff_panel = has_any_role(request.user, UserProfile.ROLE_ADMIN, UserProfile.ROLE_MANAGER)
    if is_staff_panel:
        items = CouncilJoinApplication.objects.select_related("user")
    else:
        items = CouncilJoinApplication.objects.filter(user=request.user)
    return render(
        request,
        "core/my_join_requests.html",
        {"items": items, "is_staff_panel": is_staff_panel},
    )



@login_required
def moderator_replies(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)

    feedback_items = FeedbackMessage.objects.filter(
        user=request.user,
        moderation_comment__isnull=False,
    ).exclude(moderation_comment__exact="")
    join_items = CouncilJoinApplication.objects.filter(
        user=request.user,
        moderation_comment__isnull=False,
    ).exclude(moderation_comment__exact="")

    replies = []
    for item in feedback_items:
        replies.append(
            {
                "kind": "Обращение",
                "title": item.subject,
                "status": item.get_status_display(),
                "comment": item.moderation_comment,
                "updated_at": item.updated_at,
            }
        )

    for item in join_items:
        replies.append(
            {
                "kind": "Заявка в студсовет",
                "title": item.full_name,
                "status": item.get_status_display(),
                "comment": item.moderation_comment,
                "updated_at": item.updated_at,
            }
        )

    replies.sort(key=lambda row: row["updated_at"], reverse=True)

    profile.moderator_replies_seen_at = timezone.now()
    profile.save(update_fields=["moderator_replies_seen_at"])

    return render(request, "core/moderator_replies.html", {"replies": replies})

@login_required
def my_posts(request):
    items = CommunityPost.objects.filter(author=request.user).prefetch_related("comments")
    return render(request, "core/my_posts.html", {"items": items})


@login_required
def my_files(request):
    if request.method == "POST":
        form = UserFileUploadForm(request.POST, request.FILES)
        if form.is_valid():
            item = form.save(commit=False)
            item.owner = request.user
            item.save()
            messages.success(request, "Файл загружен в хранилище.")
            log_user_activity(request, "cabinet.file.uploaded", f"file_id={item.id}")
            return redirect("core:my_files")
    else:
        form = UserFileUploadForm()

    items = UserFile.objects.filter(owner=request.user)
    return render(request, "core/my_files.html", {"items": items, "form": form})


@login_required
def download_user_file(request, pk):
    item = get_object_or_404(UserFile, pk=pk)
    is_owner = item.owner_id == request.user.id
    is_admin = has_any_role(request.user, UserProfile.ROLE_ADMIN)
    if not is_owner and not is_admin:
        messages.error(request, "Недостаточно прав для скачивания этого файла.")
        return redirect("core:my_files")

    log_user_activity(request, "cabinet.file.downloaded", f"file_id={item.id}")
    return FileResponse(item.file.open("rb"), as_attachment=True, filename=item.filename)



