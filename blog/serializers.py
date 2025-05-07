from rest_framework import serializers
from .models import Post, Like, Tag

class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ('id', 'name', 'slug')

class PostSerializer(serializers.ModelSerializer):
    likes_count = serializers.IntegerField(source="likes.count", read_only=True)
    is_liked = serializers.SerializerMethodField()

    # Поле для чтения тегов
    tags = TagSerializer(many=True, read_only=True)

    # Поле для записи тегов: список slug'ов
    tag_slugs = serializers.SlugRelatedField(
        many = True,
        slug_field = 'slug',
        queryset = Tag.objects.all(),
        write_only = True
    )

    class Meta:
        model = Post
        fields = [
            'id', 'title', 'content', 'cover', 'views',
            'created_at', 'updated_at',
            'likes_count', 'is_liked', 'tags', 'tag_slugs'
        ]

    def get_is_liked(self, obj):
        user = self.context['request'].user
        if user.is_authenticated:
            return Like.objects.filter(user=user, post=obj).exists()
        return False

    def create(self, validated_data):
        # извлекаем список slug'ов, чтобы не передавать его в супер
        slugs = validated_data.pop('tag_slugs', [])
        post = super().create(validated_data)
        post.tags.set(Tag.objects.filter(slug__in=slugs))
        return post

    def update(self, instance, validated_data):
        slugs = validated_data.pop('tag_slugs', None)
        post = super().update(instance, validated_data)
        if slugs is not None:
            post.tags.set(Tag.objects.filter(slug__in=slugs))
        return post