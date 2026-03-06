from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import FileResponse
from django.shortcuts import get_object_or_404, redirect, render

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


@login_required
def cabinet(request):
    feedbacks = FeedbackMessage.objects.filter(user=request.user)[:5]
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
    items = FeedbackMessage.objects.filter(user=request.user)
    return render(request, "core/my_feedbacks.html", {"items": items})


@login_required
def my_events(request):
    items = EventRegistration.objects.filter(user=request.user).select_related("event")
    return render(request, "core/my_events.html", {"items": items})


@login_required
def my_join_requests(request):
    items = CouncilJoinApplication.objects.filter(user=request.user)
    return render(request, "core/my_join_requests.html", {"items": items})


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

    return FileResponse(item.file.open("rb"), as_attachment=True, filename=item.filename)
