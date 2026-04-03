from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone


class TimestampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class StudentCouncilMember(models.Model):
    full_name = models.CharField(max_length=150)
    position = models.CharField(max_length=150)
    bio = models.TextField(blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=32, blank=True)
    photo_url = models.URLField(blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "full_name"]

    def __str__(self):
        return f"{self.full_name} ({self.position})"


class News(TimestampedModel):
    title = models.CharField(max_length=200)
    summary = models.TextField()
    content = models.TextField()
    image_url = models.URLField(blank=True)
    is_published = models.BooleanField(default=True)
    published_at = models.DateTimeField(default=timezone.now)
    views_count = models.PositiveIntegerField(default=0, db_index=True)

    class Meta:
        ordering = ["-published_at"]
        verbose_name_plural = "News"

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("core:news_detail", kwargs={"pk": self.pk})


class Event(TimestampedModel):
    title = models.CharField(max_length=200)
    description = models.TextField()
    short_description = models.CharField(max_length=280)
    location = models.CharField(max_length=200)
    start_at = models.DateTimeField()
    end_at = models.DateTimeField(blank=True, null=True)
    registration_deadline = models.DateTimeField(blank=True, null=True)
    max_participants = models.PositiveIntegerField(blank=True, null=True)
    is_published = models.BooleanField(default=True)

    class Meta:
        ordering = ["start_at"]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("core:event_detail", kwargs={"pk": self.pk})

    @property
    def is_archived(self):
        return self.start_at < timezone.now()


class EventRegistration(TimestampedModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="registrations")
    comment = models.CharField(max_length=255, blank=True)

    class Meta:
        unique_together = ("user", "event")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user} -> {self.event}"


class Document(TimestampedModel):
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    file_url = models.URLField()
    is_published = models.BooleanField(default=True)
    published_at = models.DateField(default=timezone.localdate)

    class Meta:
        ordering = ["-published_at", "title"]

    def __str__(self):
        return self.title


class Project(TimestampedModel):
    STATUS_CHOICES = (
        ("active", "Текущий"),
        ("done", "Реализован"),
    )
    title = models.CharField(max_length=200)
    description = models.TextField()
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="active")
    is_published = models.BooleanField(default=True)

    class Meta:
        ordering = ["title"]

    def __str__(self):
        return self.title


class FAQ(models.Model):
    question = models.CharField(max_length=255)
    answer = models.TextField()
    order = models.PositiveIntegerField(default=0)
    is_published = models.BooleanField(default=True)

    class Meta:
        ordering = ["order", "question"]
        verbose_name = "FAQ item"
        verbose_name_plural = "FAQ items"

    def __str__(self):
        return self.question


class FeedbackMessage(TimestampedModel):
    STATUS_NEW = "new"
    STATUS_IN_PROGRESS = "in_progress"
    STATUS_RESOLVED = "resolved"
    STATUS_CHOICES = (
        (STATUS_NEW, "Новое"),
        (STATUS_IN_PROGRESS, "В работе"),
        (STATUS_RESOLVED, "Решено"),
    )

    name = models.CharField(max_length=150)
    email = models.EmailField()
    subject = models.CharField(max_length=200)
    message = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_NEW)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="feedback_messages",
        null=True,
        blank=True,
    )
    moderation_comment = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.subject


class UserProfile(models.Model):
    ROLE_ADMIN = "admin"
    ROLE_MANAGER = "manager"
    ROLE_STUDENT = "student"
    ROLE_CHOICES = (
        (ROLE_ADMIN, "Администратор"),
        (ROLE_MANAGER, "Менеджер"),
        (ROLE_STUDENT, "Студент"),
    )

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile")
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_STUDENT)
    photo_url = models.URLField(blank=True)
    faculty = models.CharField(max_length=120, blank=True)
    course = models.CharField(max_length=20, blank=True)
    telegram = models.CharField(max_length=60, blank=True)
    moderator_replies_seen_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Просмотр ответов модератора",
    )

    def __str__(self):
        return f"Профиль {self.user.username}"

    @property
    def is_admin(self):
        return self.role == self.ROLE_ADMIN

    @property
    def is_manager(self):
        return self.role == self.ROLE_MANAGER


def user_file_upload_path(instance, filename):
    return f"user_files/user_{instance.owner_id}/{filename}"


class UserFile(TimestampedModel):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="uploaded_files",
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    file = models.FileField(upload_to=user_file_upload_path)
    is_private = models.BooleanField(default=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Файл пользователя"
        verbose_name_plural = "Файлы пользователей"

    def __str__(self):
        return f"{self.owner.username}: {self.title}"

    @property
    def filename(self):
        return self.file.name.rsplit("/", 1)[-1]


class CouncilJoinApplication(TimestampedModel):
    STATUS_NEW = "new"
    STATUS_IN_REVIEW = "in_review"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"
    STATUS_CHOICES = (
        (STATUS_NEW, "Новая"),
        (STATUS_IN_REVIEW, "На рассмотрении"),
        (STATUS_APPROVED, "Одобрена"),
        (STATUS_REJECTED, "Отклонена"),
    )

    FACULTY_CHOICES = (
        ("management", "Факультет управления"),
        ("it", "Факультет информационных технологий"),
        ("economics", "Факультет экономики и финансов"),
        ("law", "Юридический факультет"),
        ("psycho", "Факультет психолого-педагогического образования"),
        ("center", "Научно-образовательный центр устойчивого развития"),
        ("college", "Колледж"),
        ("postgraduate", "Аспирантура"),
        ("other", "Другое подразделение"),
    )

    full_name = models.CharField(max_length=150)
    email = models.EmailField()
    phone = models.CharField(max_length=32)
    faculty = models.CharField(max_length=32, choices=FACULTY_CHOICES)
    course = models.CharField(max_length=20, blank=True)
    motivation = models.TextField()
    experience = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_NEW)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="join_applications",
    )
    moderation_comment = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Заявка в студсовет"
        verbose_name_plural = "Заявки в студсовет"

    def __str__(self):
        return f"{self.full_name} ({self.get_status_display()})"


class CommunityPost(TimestampedModel):
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="community_posts",
    )
    title = models.CharField(max_length=180)
    body = models.TextField()
    is_pinned = models.BooleanField(default=False)
    is_published = models.BooleanField(default=True)

    class Meta:
        ordering = ["-is_pinned", "-created_at"]
        verbose_name = "Пост сообщества"
        verbose_name_plural = "Посты сообщества"

    def __str__(self):
        return self.title


class CommunityPostPin(TimestampedModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="community_post_pins",
    )
    post = models.ForeignKey(
        CommunityPost,
        on_delete=models.CASCADE,
        related_name="user_pins",
    )

    class Meta:
        unique_together = ("user", "post")
        ordering = ["-created_at"]
        verbose_name = "Персональное закрепление поста"
        verbose_name_plural = "Персональные закрепления постов"

    def __str__(self):
        return f"{self.user} pinned {self.post_id}"


class CommunityComment(TimestampedModel):
    post = models.ForeignKey(CommunityPost, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="community_comments",
    )
    body = models.TextField()
    is_published = models.BooleanField(default=True)

    class Meta:
        ordering = ["created_at"]
        verbose_name = "Комментарий сообщества"
        verbose_name_plural = "Комментарии сообщества"

    def __str__(self):
        return f"{self.author} -> {self.post_id}"


class ActivityLog(TimestampedModel):
    ACTION_MAX_LENGTH = 120

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="activity_logs",
        null=True,
        blank=True,
    )
    action = models.CharField(max_length=ACTION_MAX_LENGTH)
    details = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Лог активности"
        verbose_name_plural = "Логи активности"

    def __str__(self):
        actor = self.actor.username if self.actor_id else "anonymous"
        return f"{actor}: {self.action}"


class SiteMaintenance(models.Model):
    maintenance_enabled = models.BooleanField(default=False, verbose_name="Режим техобслуживания")
    maintenance_ends_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Ориентировочное окончание",
    )

    class Meta:
        verbose_name = "Техобслуживание сайта"
        verbose_name_plural = "Техобслуживание сайта"

    def __str__(self):
        status = "включено" if self.maintenance_enabled else "выключено"
        return f"Техобслуживание: {status}"
