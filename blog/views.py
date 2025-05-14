from rest_framework import viewsets, status,permissions
from .models import Post, ReadingTime, Like, Tag, Comment
from accounts.models import CustomUser
from .serializers import PostSerializer, TagSerializer, CommentSerializer, UserSerializer
from rest_framework.views import APIView
from rest_framework.response import Response
from django.db.models import F, Count
from rest_framework.permissions import AllowAny, IsAuthenticatedOrReadOnly
from datetime import timedelta
from django.utils import timezone
from rest_framework.decorators import action
from rest_framework.generics import RetrieveAPIView

class TagViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Только для чтения: GET /api/tags/ и GET /api/tags/{pk}/
    """
    queryset = Tag.objects.all().order_by('name')
    serializer_class = TagSerializer

# Вывод списка постов на главной странице
class PostViewSet(viewsets.ModelViewSet):
    serializer_class = PostSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        # 1) Базовый qs с аннотацией для подсчёта лайков
        qs = Post.objects.annotate(likes_count=Count('likes'))

        # 2) Фильтрация по тегам (OR-режим)
        slugs = self.request.query_params.getlist('tag')
        if slugs:
            qs = qs.filter(tags__slug__in=slugs).distinct()

        # 3) даты
        date_from = self.request.query_params.get('date_from')
        date_to = self.request.query_params.get('date_to')
        if date_from:
            qs = qs.filter(created_at__date__gte=date_from)
        if date_to:
            qs = qs.filter(created_at__date__lte=date_to)

        # 4) Читаем оба параметра сортировки
        likes_order = self.request.query_params.get('likes_order')
        views_order = self.request.query_params.get('views_order')

        # 5) Применяем сортировку по просмотрам, если есть
        if views_order == 'asc':
            qs = qs.order_by('views', '-created_at')
        elif views_order == 'desc':
            qs = qs.order_by('-views', '-created_at')

        # 6) Если сортировки по просмотрам нет, смотрим сортировку по лайкам
        elif likes_order == 'asc':
            qs = qs.order_by('likes_count', '-created_at')
        elif likes_order == 'desc':
            qs = qs.order_by('-likes_count', '-created_at')

        # 7) Фильтрация по автору
        author = self.request.query_params.get('author')
        if author:
            qs = qs.filter(author__username=author)

        # 8) Если ни views_order, ни likes_order не заданы, сортируем по дате создания
        else:
            qs = qs.order_by('-created_at')

        return qs

    @action(detail=False, methods=['get'], url_path='popular')
    def popular(self, request):
        """
        GET /api/posts/popular/?period=<all|week|month|year>
        Отдаёт посты, отфильтрованные по дате создания и отсортированные по просмотрам.
        """
        period = request.query_params.get('period', 'all')
        now = timezone.now()

        qs = Post.objects.all()
        if period == 'week':
            qs = qs.filter(created_at__gte=now - timedelta(days=7))
        elif period == 'month':
            qs = qs.filter(created_at__gte=now - timedelta(days=30))
        elif period == 'year':
            qs = qs.filter(created_at__gte=now - timedelta(days=365))
        # иначе 'all' — без доп. фильтрации по дате

        qs = qs.order_by('-views')

        # пагинация (если настроена)
        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticatedOrReadOnly])
    def like(self, request, pk=None):
        post = self.get_object()
        user = request.user

        liked, created = Like.objects.get_or_create(user=user, post=post)
        if not created:
            liked.delete()
            return Response({
                'status': 'unliked',
                'likes_count': post.likes.count()
            }, status=status.HTTP_200_OK)

        return Response({
            'status': 'liked',
            'likes_count': post.likes.count()
        }, status=status.HTTP_201_CREATED)

class TrackPostView(APIView):
    permission_classes = [AllowAny]  # и гости, и юзеры

    def post(self, request):
        post_id = request.data.get('post_id')
        seconds = request.data.get('seconds')

        if not post_id or seconds is None:
            return Response({'error': 'post_id и seconds обязательны'}, status=400)

        try:
            post = Post.objects.get(id=post_id)
        except Post.DoesNotExist:
            return Response({'error': 'Статья не найдена'}, status=404)

        # Фильтрация "мусора" по времени чтения
        seconds = int(seconds)
        if seconds < 8:
            return Response({'status': 'too_short'})

        now = timezone.now()
        THRESHOLD_HOURS = 4
        cutoff = now - timedelta(hours=THRESHOLD_HOURS)

        user = request.user if request.user.is_authenticated else None


        if user:
            # авторизованный: смотрим ReadingTime
            last = ReadingTime.objects.filter(user=user, post=post).order_by('-timestamp').first()
            if not last or last.timestamp < cutoff:
                Post.objects.filter(pk=post.pk).update(views=F('views') + 1)
        else:
            # гость: храним в сессии метку последнего просмотра
            session_key = f'viewed_post_{post.pk}'
            last_ts = request.session.get(session_key)
            if not last_ts or timezone.datetime.fromisoformat(last_ts) < cutoff:
                Post.objects.filter(pk=post.pk).update(views=F('views') + 1)
                # сохраняем новую отметку
                request.session[session_key] = now.isoformat()

        if user:
            ReadingTime.objects.create(user=user, post=post, seconds_spent=seconds)

        return Response({'status': 'ok'})

class CommentViewSet(viewsets.ModelViewSet):
    """
    CRUD для комментариев.
    GET  /api/comments/?post=<post_id> — корневые комментарии для поста
    POST /api/comments/           — создать новый комментарий или ответ
    """
    serializer_class = CommentSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        qs = Comment.objects.all()
        post_id = self.request.query_params.get('post')
        if post_id:
            # возвращаем только корневые комментарии для данного поста
            qs = qs.filter(post_id=post_id, parent__isnull=True)
        return qs

class UserDetailView(RetrieveAPIView):
    queryset = CustomUser.objects.all()
    lookup_field = 'username'
    serializer_class = UserSerializer

class UserViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = CustomUser.objects.all().order_by('username')
    serializer_class = UserSerializer
    lookup_field = 'username'