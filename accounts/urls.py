from django.urls import path

from . import views

app_name='accounts'
urlpatterns = [
    path('weekly_schedule/', views.weekly_schedule, name='weekly_schedule'),
    path('weekly_schedule/ajax/<str:slug>/', views.ajax, name='ajax'),
    path('weekly_schedule/refresh/', views.refresh, name='refresh'),
    path('courses/<int:course_id>/',views.course_info_view, name = "course_info"),
    path('courses/',views.courses_view, name = "courses"),
    path('announcements/',views.announcements_view, name = 'announcements'),
	path('assignments/',views.assignments_view, name = 'assignments'),
    path('profile/', views.profile, name='profile'),
]
