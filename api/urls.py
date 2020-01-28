from django.urls import path
from rest_framework.authtoken.views import obtain_auth_token
from api import views

app_name='api'
urlpatterns = [
    path('all-courses/', views.AllCoursesView.as_view(), name='all-courses'),
    path('assignments/<str:course_id>/', views.AssignmentsView.as_view(), name='assignments'),
    path('obtain-token/', obtain_auth_token, name='obtain-token'),
]