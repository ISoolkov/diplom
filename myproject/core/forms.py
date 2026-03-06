from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from .models import (
    CommunityComment,
    CommunityPost,
    CouncilJoinApplication,
    EventRegistration,
    FeedbackMessage,
    UserFile,
    UserProfile,
)


class SignUpForm(UserCreationForm):
    email = forms.EmailField(required=True, label="Email")
    first_name = forms.CharField(required=True, max_length=150, label="Имя")
    last_name = forms.CharField(required=True, max_length=150, label="Фамилия")
    consent = forms.BooleanField(
        required=True,
        label="Согласен(на) на обработку персональных данных",
    )

    class Meta:
        model = User
        fields = (
            "username",
            "first_name",
            "last_name",
            "email",
            "password1",
            "password2",
            "consent",
        )


class UserUpdateForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ("first_name", "last_name", "email")
        labels = {
            "first_name": "Имя",
            "last_name": "Фамилия",
            "email": "Email",
        }


class ProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ("photo_url", "faculty", "course", "telegram")
        labels = {
            "photo_url": "Ссылка на фото",
            "faculty": "Факультет",
            "course": "Курс",
            "telegram": "Telegram",
        }


class FeedbackForm(forms.ModelForm):
    class Meta:
        model = FeedbackMessage
        fields = ("name", "email", "subject", "message")
        labels = {
            "name": "Ваше имя",
            "email": "Email",
            "subject": "Тема",
            "message": "Сообщение",
        }


class EventRegistrationForm(forms.ModelForm):
    class Meta:
        model = EventRegistration
        fields = ("comment",)
        labels = {
            "comment": "Комментарий",
        }
        widgets = {
            "comment": forms.TextInput(
                attrs={"placeholder": "Комментарий (необязательно)"}
            )
        }


class CouncilJoinApplicationForm(forms.ModelForm):
    class Meta:
        model = CouncilJoinApplication
        fields = (
            "full_name",
            "email",
            "phone",
            "faculty",
            "course",
            "motivation",
            "experience",
        )
        labels = {
            "full_name": "ФИО",
            "email": "Email",
            "phone": "Телефон",
            "faculty": "Факультет / подразделение",
            "course": "Курс",
            "motivation": "Почему хотите вступить?",
            "experience": "Опыт и достижения",
        }
        widgets = {
            "motivation": forms.Textarea(
                attrs={"rows": 4, "placeholder": "Почему вы хотите вступить в студсовет?"}
            ),
            "experience": forms.Textarea(
                attrs={"rows": 3, "placeholder": "Опыт участия в проектах, волонтерстве, организации событий"}
            ),
        }


class CommunityPostForm(forms.ModelForm):
    class Meta:
        model = CommunityPost
        fields = ("title", "body")
        labels = {
            "title": "Тема",
            "body": "Текст публикации",
        }
        widgets = {
            "title": forms.TextInput(attrs={"placeholder": "Тема публикации"}),
            "body": forms.Textarea(attrs={"rows": 4, "placeholder": "Поделитесь идеей, вопросом или новостью"}),
        }


class CommunityCommentForm(forms.ModelForm):
    class Meta:
        model = CommunityComment
        fields = ("body",)
        labels = {
            "body": "Комментарий",
        }
        widgets = {
            "body": forms.Textarea(attrs={"rows": 2, "placeholder": "Ваш комментарий"}),
        }


class UserFileUploadForm(forms.ModelForm):
    class Meta:
        model = UserFile
        fields = ("title", "description", "file", "is_private")
        labels = {
            "title": "Название файла",
            "description": "Описание",
            "file": "Файл",
            "is_private": "Доступен только мне",
        }
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
        }
