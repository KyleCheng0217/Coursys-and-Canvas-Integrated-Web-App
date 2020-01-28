from django.urls import path

from . import views

app_name = 'authentication'
urlpatterns = [
    path('register/', views.registration_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('logout/success/', views.logout_success_view, name='logout_success'),
    path('oauth/coursys', views.coursys_authentication_view, name='oauth_coursys'),
]
