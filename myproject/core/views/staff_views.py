from django.contrib import messages
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Count
from django.http import FileResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from core.forms import FAQManageForm
from core.models import CouncilJoinApplication, Event, FAQ, FeedbackMessage, News, UserFile, UserProfile
from core.permissions import role_required
from core.services import (
    EVENT_REGISTRATION_SUBJECT_PREFIX,
    ServiceDependencyError,
    ServiceValidationError,
    build_events_docx,
    build_feedback_xlsx,
    update_feedback_status,
    update_join_request_status,
    update_user_role,
)

User = get_user_model()


def _normalize_faq_order():
    """Приводит порядок FAQ к последовательности 1..N без дублей."""
    items = list(FAQ.objects.order_by("order", "id"))
    for index, item in enumerate(items, start=1):
        if item.order != index:
            FAQ.objects.filter(pk=item.pk).update(order=index)


@role_required(UserProfile.ROLE_ADMIN, UserProfile.ROLE_MANAGER)
def staff_dashboard(request):
    role_rows = UserProfile.objects.values("role").annotate(total=Count("id")).order_by("role")
    role_stats = {row["role"]: row["total"] for row in role_rows}

    context = {
        "total_users": User.objects.count(),
        "total_news": News.objects.count(),
        "total_events": Event.objects.count(),
        "total_feedbacks": FeedbackMessage.objects.count(),
        "total_join_requests": CouncilJoinApplication.objects.count(),
        "total_files": UserFile.objects.count(),
        "role_stats": {
            "admin": role_stats.get(UserProfile.ROLE_ADMIN, 0),
            "manager": role_stats.get(UserProfile.ROLE_MANAGER, 0),
            "student": role_stats.get(UserProfile.ROLE_STUDENT, 0),
        },
        "latest_feedbacks": FeedbackMessage.objects.select_related("user")[:10],
        "latest_join_requests": CouncilJoinApplication.objects.select_related("user")[:10],
    }
    return render(request, "core/staff/dashboard.html", context)


@role_required(UserProfile.ROLE_ADMIN, UserProfile.ROLE_MANAGER)
def staff_feedbacks(request):
    if request.method == "POST":
        item = get_object_or_404(FeedbackMessage, pk=request.POST.get("feedback_id"))
        new_status = request.POST.get("status", "")
        moderation_comment = request.POST.get("moderation_comment", "")

        try:
            update_feedback_status(item, new_status, moderation_comment)
        except ServiceValidationError as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "Статус обращения обновлен.")
        return redirect("core:staff_feedbacks")

    items = FeedbackMessage.objects.select_related("user").exclude(
        subject__startswith=EVENT_REGISTRATION_SUBJECT_PREFIX
    )
    return render(request, "core/staff/feedbacks.html", {"items": items})


@role_required(UserProfile.ROLE_ADMIN, UserProfile.ROLE_MANAGER)
def staff_join_requests(request):
    if request.method == "POST":
        if request.POST.get("event_feedback_id"):
            item = get_object_or_404(
                FeedbackMessage,
                pk=request.POST.get("event_feedback_id"),
                subject__startswith=EVENT_REGISTRATION_SUBJECT_PREFIX,
            )
            new_status = request.POST.get("status", "")
            moderation_comment = request.POST.get("moderation_comment", "")

            try:
                update_feedback_status(item, new_status, moderation_comment)
            except ServiceValidationError as exc:
                messages.error(request, str(exc))
            else:
                messages.success(request, "Статус заявки на мероприятие обновлен.")
        else:
            item = get_object_or_404(CouncilJoinApplication, pk=request.POST.get("join_id"))
            new_status = request.POST.get("status", "")
            moderation_comment = request.POST.get("moderation_comment", "")

            try:
                update_join_request_status(item, new_status, moderation_comment)
            except ServiceValidationError as exc:
                messages.error(request, str(exc))
            else:
                messages.success(request, "Статус заявки обновлен.")
        return redirect("core:staff_join_requests")

    items = CouncilJoinApplication.objects.select_related("user")
    event_requests = FeedbackMessage.objects.select_related("user").filter(
        subject__startswith=EVENT_REGISTRATION_SUBJECT_PREFIX
    )
    return render(
        request,
        "core/staff/join_requests.html",
        {"items": items, "event_requests": event_requests},
    )


@role_required(UserProfile.ROLE_ADMIN)
def staff_users(request):
    if request.method == "POST":
        profile = get_object_or_404(UserProfile, pk=request.POST.get("profile_id"))
        new_role = request.POST.get("role", "")

        try:
            update_user_role(profile, new_role)
        except ServiceValidationError as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, f"Роль пользователя {profile.user.username} обновлена.")
        return redirect("core:staff_users")

    profiles = UserProfile.objects.select_related("user").order_by("user__username")
    return render(request, "core/staff/users.html", {"profiles": profiles})


@role_required(UserProfile.ROLE_ADMIN)
def staff_files(request):
    if request.method == "POST" and request.POST.get("action") == "delete":
        item = get_object_or_404(UserFile, pk=request.POST.get("file_id"))
        item.file.delete(save=False)
        item.delete()
        messages.success(request, "Файл удален из хранилища.")
        return redirect("core:staff_files")

    items = UserFile.objects.select_related("owner", "owner__profile")
    return render(request, "core/staff/files.html", {"items": items})


@role_required(UserProfile.ROLE_ADMIN, UserProfile.ROLE_MANAGER)
def staff_reports(request):
    context = {
        "events_total": Event.objects.count(),
        "feedbacks_total": FeedbackMessage.objects.count(),
        "generated_at": timezone.now(),
    }
    return render(request, "core/staff/reports.html", context)


@role_required(UserProfile.ROLE_ADMIN, UserProfile.ROLE_MANAGER)
def staff_faqs(request):
    _normalize_faq_order()

    if request.method == "POST":
        action = request.POST.get("action", "create")

        if action == "delete":
            item = get_object_or_404(FAQ, pk=request.POST.get("faq_id"))
            item.delete()
            _normalize_faq_order()
            messages.success(request, "Пункт FAQ удален.")
            return redirect("core:staff_faqs")

        if action in {"move_up", "move_down"}:
            item = get_object_or_404(FAQ, pk=request.POST.get("faq_id"))
            if action == "move_up":
                swap_with = FAQ.objects.filter(order__lt=item.order).order_by("-order", "-id").first()
            else:
                swap_with = FAQ.objects.filter(order__gt=item.order).order_by("order", "id").first()

            if swap_with:
                with transaction.atomic():
                    item_order = item.order
                    item.order = swap_with.order
                    swap_with.order = item_order
                    item.save(update_fields=["order"])
                    swap_with.save(update_fields=["order"])
                _normalize_faq_order()
                messages.success(request, "Порядок FAQ обновлен.")
            else:
                messages.info(request, "Перемещение невозможно.")
            return redirect("core:staff_faqs")

        form = FAQManageForm(request.POST)
        if form.is_valid():
            faq_item = form.save(commit=False)
            faq_item.order = FAQ.objects.count() + 1
            faq_item.save()
            _normalize_faq_order()
            messages.success(request, "Раздел FAQ добавлен.")
            return redirect("core:staff_faqs")
        messages.error(request, "Проверьте поля формы FAQ.")
    else:
        form = FAQManageForm()

    items = FAQ.objects.order_by("order", "id")
    return render(request, "core/staff/faqs.html", {"form": form, "items": items})


@role_required(UserProfile.ROLE_ADMIN, UserProfile.ROLE_MANAGER)
def export_events_docx(request):
    try:
        output = build_events_docx(Event.objects.order_by("start_at"))
    except ServiceDependencyError as exc:
        messages.error(request, str(exc))
        return redirect("core:staff_reports")

    filename = f"events_report_{timezone.localdate().isoformat()}.docx"
    return FileResponse(output, as_attachment=True, filename=filename)


@role_required(UserProfile.ROLE_ADMIN, UserProfile.ROLE_MANAGER)
def export_feedback_xlsx(request):
    try:
        output = build_feedback_xlsx(FeedbackMessage.objects.order_by("-created_at"))
    except ServiceDependencyError as exc:
        messages.error(request, str(exc))
        return redirect("core:staff_reports")

    filename = f"feedback_report_{timezone.localdate().isoformat()}.xlsx"
    return FileResponse(output, as_attachment=True, filename=filename)


