from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (PostViewSet, TrackPostView, TagViewSet,
                    CommentViewSet, UserDetailView,
                    UserViewSet, FollowViewSet, SubscriptionsListView,
                    SubscriptionsCountView, RecommendationsContentView,
                    RecommendationsCFView, RecommendationsHybridView)

router = DefaultRouter()
router.register(r'posts', PostViewSet, basename='post')
router.register(r'tags', TagViewSet,  basename='tag')
router.register(r'comments', CommentViewSet, basename='comment')
router.register(r'users', UserViewSet, basename='user')
router.register(r'follow', FollowViewSet, basename='follow')

urlpatterns = [
    path('', include(router.urls)),
]

# Маршрут для времени чтения статьи
urlpatterns += [
    path('track/', TrackPostView.as_view(), name='track_post'),
]

# Профили
urlpatterns += [
    path('users/<str:username>/', UserDetailView.as_view(), name='user-detail'),
]

# новые эндпойнты для подписок
urlpatterns += [
    path('subscriptions/count/', SubscriptionsCountView.as_view(), name='subs-count'),
    path('subscriptions/', SubscriptionsListView.as_view(), name='subs-list'),
]


urlpatterns += [
    path('recommendations/content/', RecommendationsContentView.as_view(), name='rec-content'),
    path('recommendations/cf/', RecommendationsCFView.as_view(), name='rec-cf'),
    path('recommendations/hybrid/', RecommendationsHybridView.as_view(), name='rec-hybrid'),
]
