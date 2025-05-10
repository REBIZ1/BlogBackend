from rest_framework import viewsets, status
from .models import Post, ReadingTime, Like, Tag
from .serializers import PostSerializer, TagSerializer
from rest_framework.views import APIView
from rest_framework.response import Response
from django.db.models import F
from rest_framework.permissions import AllowAny, IsAuthenticatedOrReadOnly
from datetime import timedelta
from django.utils import timezone
from rest_framework.decorators import action

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
        """
        Взять все посты, отсортировать по дате,
        и, если в GET-параметрах пришёл ?tag=slug,
        отфильтровать те, у которых есть этот тег.
        """
        qs = Post.objects.all().order_by('-created_at')
        tag_slug = self.request.query_params.get('tag')
        if tag_slug:
            qs = qs.filter(tags__slug=tag_slug)
        return qs

    def perform_create(self, serializer):
        # При создании поста явно передаём author=current user
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

