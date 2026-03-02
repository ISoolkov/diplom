from django.contrib import admin

from .models import (
    CommunityComment,
    CommunityPost,
    CouncilJoinApplication,
    Document,
    Event,
    EventRegistration,
    FAQ,
    FeedbackMessage,
    News,
    Project,
    StudentCouncilMember,
    UserProfile,
)


@admin.register(News)
class NewsAdmin(admin.ModelAdmin):
    list_display = ("title", "published_at", "is_published")
    list_filter = ("is_published", "published_at")
    search_fields = ("title", "summary", "content")


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("title", "start_at", "location", "is_published")
    list_filter = ("is_published", "start_at")
    search_fields = ("title", "description", "location")


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ("title", "published_at", "is_published")
    list_filter = ("is_published", "published_at")
    search_fields = ("title", "description")


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("title", "status", "is_published")
    list_filter = ("status", "is_published")
    search_fields = ("title", "description")


@admin.register(FAQ)
class FAQAdmin(admin.ModelAdmin):
    list_display = ("question", "order", "is_published")
    list_filter = ("is_published",)
    search_fields = ("question", "answer")


@admin.register(FeedbackMessage)
class FeedbackMessageAdmin(admin.ModelAdmin):
    list_display = ("subject", "name", "email", "status", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("subject", "name", "email", "message")


@admin.register(StudentCouncilMember)
class StudentCouncilMemberAdmin(admin.ModelAdmin):
    list_display = ("full_name", "position", "order")
    search_fields = ("full_name", "position", "bio")
    ordering = ("order",)


@admin.register(EventRegistration)
class EventRegistrationAdmin(admin.ModelAdmin):
    list_display = ("user", "event", "created_at")
    search_fields = ("user__username", "event__title")


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "faculty", "course", "telegram")
    search_fields = ("user__username", "faculty", "telegram")


@admin.register(CouncilJoinApplication)
class CouncilJoinApplicationAdmin(admin.ModelAdmin):
    list_display = ("full_name", "faculty", "course", "status", "created_at")
    list_filter = ("status", "faculty", "created_at")
    search_fields = ("full_name", "email", "phone", "motivation")


@admin.register(CommunityPost)
class CommunityPostAdmin(admin.ModelAdmin):
    list_display = ("title", "author", "is_pinned", "is_published", "created_at")
    list_filter = ("is_pinned", "is_published", "created_at")
    search_fields = ("title", "body", "author__username")


@admin.register(CommunityComment)
class CommunityCommentAdmin(admin.ModelAdmin):
    list_display = ("post", "author", "is_published", "created_at")
    list_filter = ("is_published", "created_at")
    search_fields = ("post__title", "author__username", "body")
