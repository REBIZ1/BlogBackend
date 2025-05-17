from django.db import models
from django.contrib.auth import get_user_model
from django.utils.text import slugify
from unidecode import unidecode
from django.conf import settings
import os

User = get_user_model()

class Tag(models.Model):
    name = models.CharField(max_length=50, unique=True)
    slug = models.SlugField(unique=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            # сперва транслитерируем, потом делаем латинский slug
            raw = unidecode(self.name)
            self.slug = slugify(raw)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

class Post(models.Model):
    title = models.CharField(max_length=200)
    cover = models.ImageField(upload_to='cover/', null=True, blank=True)
    content = models.TextField()
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='posts')
    tags = models.ManyToManyField(Tag, related_name='posts')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    views = models.PositiveIntegerField(default=0)

    def tag_vector(self, tag_index_map):
        """
        tag_index_map: dict { slug: position_in_vector }
        возвращает list[int] длины N_tags, где 1 если у поста есть этот тег
        """
        vec = [0] * len(tag_index_map)
        for t in self.tags.all():
            idx = tag_index_map.get(t.slug)
            if idx is not None:
                vec[idx] = 1
        return vec
    
    def save(self, *args, **kwargs):
        # Проверяем: это обновление, а не создание нового объекта
        if self.pk:  # pk — это primary key, то есть id
            try:
                old_post = Post.objects.get(pk=self.pk)
                # Проверяем: обложка поменялась и старая обложка существует
                if old_post.cover and old_post.cover != self.cover:
                    old_path = os.path.join(settings.MEDIA_ROOT, old_post.cover.name)
                    if os.path.exists(old_path):
                        os.remove(old_path)
            except Post.DoesNotExist:
                pass  # Поста ещё нет в базе

        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.cover:
            try:
                old_path = os.path.join(settings.MEDIA_ROOT, self.cover.name)
                if os.path.exists(old_path):
                    os.remove(old_path)
            except Exception as e:
                print(f"Ошибка удаления обложки: {e}")
        super().delete(*args, **kwargs)

    def __str__(self):
        return self.title

    def total_likes(self):
        return self.likes.count()


class Like(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='likes')
    liked_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'post')  # Один пользователь = один лайк на пост

    def __str__(self):
        return f"{self.user.username} liked {self.post.title}"


class ReadingTime(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    post = models.ForeignKey(Post, on_delete=models.CASCADE)
    seconds_spent = models.PositiveIntegerField()
    timestamp = models.DateTimeField(auto_now_add=True)

class Comment(models.Model):
    post       = models.ForeignKey('blog.Post', on_delete=models.CASCADE, related_name='comments')
    author     = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    parent     = models.ForeignKey('self', null=True, blank=True, on_delete=models.CASCADE, related_name='replies')
    content    = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('created_at',)
        verbose_name = 'Комментарий'
        verbose_name_plural = 'Комментарии'

    def __str__(self):
        return f'Комментарий #{self.id} к посту "{self.post.title}"'

class Follow(models.Model):
    """
    Модель подписок: user подписан на author.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='follows'
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='followers'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'author')
        ordering = ('-created_at',)

    def __str__(self):
        return f"{self.user.username} → {self.author.username}"