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
    path("gallery/", views.gallery, name="gallery"),
    path("faq/", views.faq_list, name="faq"),
    path("feedback/", views.feedback_create, name="feedback"),
    path("register/", views.register, name="register"),
    path("cabinet/", views.cabinet, name="cabinet"),
    path("cabinet/profile/", views.profile_edit, name="profile_edit"),
    path("cabinet/feedbacks/", views.my_feedbacks, name="my_feedbacks"),
    path("cabinet/events/", views.my_events, name="my_events"),
    path("cabinet/join-requests/", views.my_join_requests, name="my_join_requests"),
    path("cabinet/moderator-replies/", views.moderator_replies, name="moderator_replies"),
    path("cabinet/posts/", views.my_posts, name="my_posts"),
    path("cabinet/files/", views.my_files, name="my_files"),
    path("cabinet/files/<int:pk>/download/", views.download_user_file, name="download_user_file"),
    path("staff/", views.staff_dashboard, name="staff_dashboard"),
    path("staff/feedbacks/", views.staff_feedbacks, name="staff_feedbacks"),
    path("staff/join-requests/", views.staff_join_requests, name="staff_join_requests"),
    path("staff/users/", views.staff_users, name="staff_users"),
    path("staff/files/", views.staff_files, name="staff_files"),
    path("staff/reports/", views.staff_reports, name="staff_reports"),
    path("staff/reports/events.docx", views.export_events_docx, name="export_events_docx"),
    path("staff/reports/feedback.xlsx", views.export_feedback_xlsx, name="export_feedback_xlsx"),
]

