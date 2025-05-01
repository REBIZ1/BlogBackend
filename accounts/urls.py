from django.urls import path
from .views import CustomUserRegisterView, ProfileView

urlpatterns = [
    path('register/', CustomUserRegisterView.as_view(), name='register'),
    path('profile/', ProfileView.as_view(), name='profile'),
]