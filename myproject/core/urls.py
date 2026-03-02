from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("", views.home, name="home"),
    path("news/", views.news_list, name="news_list"),
    path("news/<int:pk>/", views.news_detail, name="news_detail"),
    path("events/", views.events_list, name="events_list"),
    path("events/<int:pk>/", views.event_detail, name="event_detail"),
    path("council/", views.council_info, name="council"),
    path("community/", views.community_feed, name="community"),
    path("join/", views.join_request_create, name="join"),
    path("documents/", views.documents_list, name="documents"),
    path("projects/", views.projects_list, name="projects"),
    path("faq/", views.faq_list, name="faq"),
    path("feedback/", views.feedback_create, name="feedback"),
    path("register/", views.register, name="register"),
    path("cabinet/", views.cabinet, name="cabinet"),
    path("cabinet/profile/", views.profile_edit, name="profile_edit"),
    path("cabinet/feedbacks/", views.my_feedbacks, name="my_feedbacks"),
    path("cabinet/events/", views.my_events, name="my_events"),
]
