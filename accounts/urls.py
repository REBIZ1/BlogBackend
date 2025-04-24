from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('favorites/', views.favorites_view, name='favorites'),
    path('create/', views.create_post_placeholder, name='create_post_placeholder'),
    path('history/', views.history_view, name='history'),
    path('settings/', views.account_settings_view, name='account_settings'),
    path('password_change/', auth_views.PasswordChangeView.as_view(
        template_name='accounts/password_change.html',
        success_url='/accounts/settings/'
    ), name='password_change'),
    path('register/', views.register_view, name='register'),
    path('login/', auth_views.LoginView.as_view(template_name='accounts/login.html'), name='login'),
    path('logout/', views.logout_view, name='logout'),
]