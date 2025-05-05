from django.urls import path
from .views import CustomUserRegisterView, ProfileView, HistoryView, FavoritesView, ChangePasswordView

urlpatterns = [
    path('register/', CustomUserRegisterView.as_view(), name='register'),
    path('profile/', ProfileView.as_view(), name='profile'),
    path('change_password/', ChangePasswordView.as_view(), name='change-password'),
    path('history/', HistoryView.as_view(), name='account-history'),
    path('favorites/', FavoritesView.as_view(), name='account-favorites'),
]