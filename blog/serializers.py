from rest_framework import serializers
from .models import Post, Like, Tag

class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ('id', 'name', 'slug')

class PostSerializer(serializers.ModelSerializer):
    # — Поля для валидации
    title = serializers.CharField(
        min_length=4,
        error_messages={'min_length': 'Заголовок должен быть не менее 4 символов'}
    )
    content = serializers.CharField(
        min_length=20,
        error_messages={'min_length': 'Содержимое должно быть не менее 20 символов'}
    )
    cover = serializers.ImageField(
        required=False,
        allow_null=True
    )

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
            'tags', 'tag_slugs'
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
        slugs = validated_data.pop('tag_slugs', [])
        # Явно берём только те поля, которые нужны модели
        post = Post(
            title=validated_data['title'],
            content=validated_data['content'],
            cover=validated_data.get('cover', None),
            author=self.context['request'].user
        )
        post.save()
        post.tags.set(Tag.objects.filter(slug__in=slugs))
        return post

    def update(self, instance, validated_data):
        slugs = validated_data.pop('tag_slugs', None)
        for attr, val in validated_data.items():
            setattr(instance, attr, val)
        instance.save()
        if slugs is not None:
            instance.tags.set(Tag.objects.filter(slug__in=slugs))
        return instance