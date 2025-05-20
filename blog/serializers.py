from rest_framework import serializers
from .models import Post, Like, Tag, Comment, Follow
from accounts.models import CustomUser

class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ('id', 'name', 'slug')

class PostSerializer(serializers.ModelSerializer):
    # — Поля для валидации
    title = serializers.CharField(
        min_length=10, max_length=200,
        error_messages={
            'min_length': 'Заголовок статьи должен быть не менее 10 символов',
            'max_length': 'Заголовок статьи не должен превышать 200 символов'
        }
    )
    content = serializers.CharField(
        min_length=50, max_length=5000,
        error_messages={
            'min_length': 'Содержимое должно быть не менее 50 символов',
            'max_length': 'Содержимое не должно превышать 5000 символов'
        }
    )
    cover = serializers.ImageField(
        required=True,
        allow_null=False,
        error_messages={
            'required': 'Пожалуйста, загрузите обложку для статьи',
            'invalid': 'Неверный формат файла обложки'
        }
    )

    author_username = serializers.CharField(source='author.username', read_only=True)
    author_avatar   = serializers.ImageField(source='author.avatar', read_only=True)

    # — Вложенный вывод тегов
    tags = TagSerializer(many=True, read_only=True)
    # — Поле приёма тегов по slug'ам
    tag_slugs = serializers.SlugRelatedField(
        many=True,
        slug_field='slug',
        queryset=Tag.objects.all(),
        write_only=True,
        required=True,
        error_messages={'required': 'Укажите хотя бы один тег'}
    )

    # — Поля лайков
    likes_count = serializers.IntegerField(source='likes.count', read_only=True)
    is_liked    = serializers.SerializerMethodField()

    class Meta:
        model = Post
        fields = [
            'id', 'title', 'content', 'cover', 'views',
            'created_at', 'updated_at',
            'likes_count', 'is_liked',
            'tags', 'tag_slugs',
            'author_username', 'author_avatar',
        ]

    def validate_tag_slugs(self, value):
        if not value:
            raise serializers.ValidationError('Выберите хотя бы один тег')
        return value

    def get_is_liked(self, obj):
        user = self.context['request'].user
        if user.is_authenticated:
            return Like.objects.filter(user=user, post=obj).exists()
        return False

    def create(self, validated_data):
        slugs = validated_data.pop('tag_slugs', [])  # список Tag-объектов
        post = Post(
            title = validated_data['title'],
        content = validated_data['content'],
        cover = validated_data.get('cover', None),
        author = self.context['request'].user
        )
        post.save()
        # Вместо повторного фильтра по slug, просто передаём сами объекты
        post.tags.set(slugs)
        return post

    def update(self, instance, validated_data):
        slugs = validated_data.pop('tag_slugs', None)
        for attr, val in validated_data.items():
            setattr(instance, attr, val)
        instance.save()
        if slugs is not None:
            instance.tags.set(slugs)
        return instance

class RecursiveField(serializers.Serializer):
    """
    Позволяет сериализовать вложенные replies рекурсивно.
    """
    def to_representation(self, value):
        serializer = self.parent.parent.__class__(value, context=self.context)
        return serializer.data

class CommentSerializer(serializers.ModelSerializer):
    author_username = serializers.CharField(source='author.username', read_only=True)
    author_avatar   = serializers.ImageField(source='author.avatar', read_only=True)
    replies         = RecursiveField(many=True, read_only=True)

    content = serializers.CharField(
        max_length=1000,
        allow_blank=False,
        error_messages={
            'blank': 'Комментарий не может быть пустым.',
            'max_length': 'Комментарий слишком длинный (не более 1000 символов).'
        }
    )

    class Meta:
        model = Comment
        fields = (
            'id',
            'post',
            'parent',
            'author_username',
            'author_avatar',
            'content',
            'created_at',
            'replies',
        )
        read_only_fields = ('author_username', 'author_avatar', 'created_at', 'replies')

    def validate(self, data):
        """
        Дополнительная валидация:
        — Проверим, что parent (если указан) относится к тому же посту.
        """
        parent = data.get('parent')
        post   = data.get('post')
        if parent and parent.post_id != post.id:
            raise serializers.ValidationError("Нельзя отвечать на комментарий к другому посту.")
        return data

    def create(self, validated_data):
        """
        Привязываем автора автоматически из request.user.
        """
        user = self.context['request'].user
        return Comment.objects.create(author=user, **validated_data)

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ('username', 'avatar')

# Подписки
class FollowSerializer(serializers.ModelSerializer):
    author_username = serializers.CharField(source='author.username', read_only=True)
    author_avatar   = serializers.ImageField(source='author.avatar', read_only=True)

    class Meta:
        model = Follow
        fields = ('id', 'author', 'author_username', 'author_avatar', 'created_at')
        read_only_fields = ('id', 'created_at')
