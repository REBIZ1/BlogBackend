from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import PostViewSet, TrackPostView, TagViewSet, CommentViewSet

router = DefaultRouter()
router.register(r'posts', PostViewSet, basename='post')
router.register(r'tags', TagViewSet,  basename='tag')
router.register(r'comments', CommentViewSet, basename='comment')

urlpatterns = [
    path('', include(router.urls)),
]

# Маршрут для времени чтения статьи
urlpatterns += [
    path('track/', TrackPostView.as_view(), name='track_post'),
]

