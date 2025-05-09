from rest_framework import serializers
from .models import CustomUser
from blog.models import ReadingTime, Like
from blog.serializers import PostSerializer
from rest_framework.validators import UniqueValidator
from django.contrib.auth.password_validation import validate_password as django_validate_password
from django.core.exceptions import ValidationError as DjangoValidationError

# Регистрация
class CustomUserRegisterSerializer(serializers.ModelSerializer):
    username = serializers.CharField(
        min_length=3,
        error_messages={'min_length': 'Логин должен быть не менее 3 символов'},
        validators=[UniqueValidator(queryset=CustomUser.objects.all(),
                                    message='Пользователь с таким именем уже существует')]
    )
    password = serializers.CharField(
        write_only=True,
        min_length=8,
        error_messages={'min_length': 'Пароль должен быть не менее 8 символов'}
    )
    password2 = serializers.CharField(write_only=True)

    class Meta:
        model = CustomUser
        fields = ('id', 'username', 'email', 'password', 'password2', 'avatar')

    def validate(self, attrs):
        # 1) Проверка совпадения паролей
        if attrs['password'] != attrs['password2']:
            raise serializers.ValidationError({'password2': 'Пароли не совпадают.'})

        # 2) Прогон через Django‑валидаторы (простые и сложные правила)
        try:
            django_validate_password(attrs['password'])
        except DjangoValidationError as e:
            # e.messages — список строк с причинами отказа
            raise serializers.ValidationError({'password': e.messages})

        return attrs

    def create(self, validated_data):
        # Убираем вспомогательное поле
        validated_data.pop('password2')
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
    username = serializers.CharField(
        min_length=3,
        error_messages={'min_length': 'Логин должен быть не менее 3 символов'},
        validators=[
            UniqueValidator(
                queryset=CustomUser.objects.all(),
                message='Пользователь с таким именем уже существует'
            )
        ]
    )
    email = serializers.EmailField(
        required=False,
        validators=[
            UniqueValidator(
                queryset=CustomUser.objects.all(),
                message='Пользователь с таким email уже зарегистрирован'
            )
        ]
    )
    avatar = serializers.ImageField(required=False)

    class Meta:
        model = CustomUser
        fields = ('username', 'email', 'avatar')

    def update(self, instance, validated_data):
        # Если аватар меняется, удаляем старый файл
        avatar = validated_data.get('avatar', None)
        if avatar and instance.avatar and instance.avatar != avatar:
            instance.avatar.delete(save=False)
        return super().update(instance, validated_data)

# Смена пароля
class ChangePasswordSerializer(serializers.Serializer):
    old_password  = serializers.CharField(write_only=True)
    new_password1 = serializers.CharField(
        write_only=True,
        min_length=8,
        error_messages={'min_length': 'Новый пароль должен быть не менее 8 символов'}
    )
    new_password2 = serializers.CharField(write_only=True)

    def validate_old_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError('Неверный старый пароль!')
        return value

    def validate_new_password1(self, value):
        try:
            django_validate_password(value, user=self.context['request'].user)
        except DjangoValidationError as e:
            raise serializers.ValidationError(e.messages)
        return value

    def validate(self, data):
        if data['new_password1'] != data['new_password2']:
            raise serializers.ValidationError({'new_password2': 'Пароли не совпадают!'})
        return data