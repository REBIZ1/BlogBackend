from rest_framework import serializers
from .models import CustomUser
from blog.models import ReadingTime, Like
from blog.serializers import PostSerializer

# Регистрация
class CustomUserRegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    password2 = serializers.CharField(write_only=True)

    class Meta:
        model = CustomUser
        fields = ('id', 'username', 'email', 'password', 'password2', 'avatar')

    def validate(self, data):
        if data['password'] != data['password2']:
            raise serializers.ValidationError("Пароли не совпадают.")
        return data

    def create(self, validated_data):
        validated_data.pop('password2')  # удаляем перед созданием пользователя
        user = CustomUser(
            username=validated_data['username'],
            email=validated_data.get('email', ''),
            avatar=validated_data.get('avatar', None)
        )
        user.set_password(validated_data['password'])
        user.save()
        return user

# Время чтения
class ReadingTimeSerializer(serializers.ModelSerializer):
    post = PostSerializer(read_only=True)

    class Meta:
        model = ReadingTime
        fields = ('id', 'post', 'seconds_spent', 'timestamp')

# Лайки
class LikePostSerializer(serializers.ModelSerializer):
    post = PostSerializer(read_only=True)

    class Meta:
        model = Like
        fields = ('id', 'post', 'liked_at')

# Настройки аккаунта
class ProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model  = CustomUser
        fields = ('username', 'email', 'avatar')

# Смена пароля
class ChangePasswordSerializer(serializers.Serializer):
    old_password  = serializers.CharField(write_only=True)
    new_password1 = serializers.CharField(write_only=True)
    new_password2 = serializers.CharField(write_only=True)

    def validate(self, data):
        if data['new_password1'] != data['new_password2']:
            raise serializers.ValidationError("Пароли не совпадают!")
        return data