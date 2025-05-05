from django.core.serializers import serialize
from django.template.context_processors import request
from rest_framework import generics, status
from .models import CustomUser
from blog.models import ReadingTime, Like
from .serializers import CustomUserRegisterSerializer, ReadingTimeSerializer, LikePostSerializer, ProfileSerializer, ChangePasswordSerializer
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework.response import Response

# Регистрация
class CustomUserRegisterView(generics.CreateAPIView):
    queryset = CustomUser.objects.all()
    serializer_class = CustomUserRegisterSerializer

# Возваращает имя и аватар пользователя
class ProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        return Response({
            "username": user.username,
            "avatar": user.avatar.url if user.avatar else None
        })

# История просмотра
class HistoryView(generics.ListAPIView):
    serializer_class = ReadingTimeSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Берём только для текущего пользователя, сортируем по дате (свежие вверху)
        return ReadingTime.objects.filter(user=self.request.user) \
                                  .order_by('-timestamp')

# Избранное
class FavoritesView(generics.ListAPIView):
    serializer_class = LikePostSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Like.objects.filter(user=self.request.user).order_by('-liked_at')

# Настройки аккаунта
class ProfileView(generics.RetrieveUpdateAPIView):
    serializer_class   = ProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        # всегда возвращаем текущего пользователя
        return self.request.user

# смена пароля
class ChangePasswordView(generics.GenericAPIView):
    serializer_class   = ChangePasswordSerializer
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = request.user
        # проверяем старый пароль
        if not user.check_password(serializer.validated_data['old_password']):
            return Response({'old_password': 'Неверный старый пароль!'}, status=status.HTTP_400_BAD_REQUEST)
        # устанавливаем новый
        user.set_password(serializer.validated_data['new_password1'])
        user.save()
        return Response({'detail': 'Пароль успешно изменён!'}, status=status.HTTP_200_OK)
