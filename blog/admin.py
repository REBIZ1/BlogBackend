from django.contrib import admin
from .models import Post, Tag, Like, ReadingTime, Comment


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ('title', 'author', 'created_at', 'views', 'total_likes')
    list_filter = ('created_at', 'tags')
    search_fields = ('title', 'content', 'author__username')
    filter_horizontal = ('tags',)

@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)

@admin.register(Like)
class LikeAdmin(admin.ModelAdmin):
    list_display = ('user', 'post', 'liked_at')
    list_filter = ('liked_at',)
    search_fields = ('user__username', 'post__title')

@admin.register(ReadingTime)
class ReadingTimeAdmin(admin.ModelAdmin):
    list_display = ('user', 'post', 'seconds_spent', 'timestamp')
    list_filter = ('timestamp', 'post')
    search_fields = ('user__username', 'post__title')

@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display   = ('id', 'post', 'author', 'parent', 'created_at')
    list_filter    = ('created_at', 'post', 'author')
    search_fields  = ('author__username', 'post__title', 'content')
    readonly_fields = ('created_at',)
    raw_id_fields  = ('post', 'author', 'parent')
    ordering       = ('-created_at',)