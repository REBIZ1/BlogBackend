from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import PostViewSet, TrackPostView

router = DefaultRouter()
router.register(r'posts', PostViewSet, basename='post')

urlpatterns = [
    path('', include(router.urls)),
]

# Маршрут для времени чтения статьи
urlpatterns += [
    path('track/', TrackPostView.as_view(), name='track_post'),
]