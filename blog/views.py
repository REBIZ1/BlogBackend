from django.shortcuts import render, get_object_or_404, redirect
from .models import Post, ReadingTime, Like, Tag
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.shortcuts import redirect
from django.db.models import Count
from django.core.paginator import Paginator
import json

def post_detail(request, pk):
    post = get_object_or_404(Post, pk=pk)
    session_key = f'viewed_post_{pk}'

    # Учет просмотра
    if not request.session.get(session_key, False):
        post.views += 1
        post.save()
        request.session[session_key] = True

    # Обработка лайка
    if request.method == 'POST' and request.user.is_authenticated:
        existing_like = Like.objects.filter(user=request.user, post=post)
        if existing_like.exists():
            existing_like.delete()
        else:
            Like.objects.create(user=request.user, post=post)
        return redirect('post_detail', pk=pk)  # Обновим страницу

    context = {
        'post': post,
        'is_liked': Like.objects.filter(user=request.user, post=post).exists() if request.user.is_authenticated else False
    }
    return render(request, 'blog/post_detail.html', context)

@csrf_exempt
def track_time(request): # Время просмотра
    if request.method == 'POST':
        data = json.loads(request.body)
        user = request.user if request.user.is_authenticated else None
        post_id = data.get('post_id')
        seconds = data.get('seconds')

        if user and post_id and seconds:
            ReadingTime.objects.create(
                user=user,
                post_id=post_id,
                seconds_spent=seconds
            )
            return JsonResponse({'status': 'success'})
        return JsonResponse({'status': 'error', 'message': 'Invalid data'}, status=400)

def post_list(request):
    # Работа с постами и тэгами для сортировки по ним
    tag_slug = request.GET.get('tag')
    posts = Post.objects.all().order_by('-created_at')

    if tag_slug:
        posts = posts.filter(tags__slug=tag_slug)

    tags = Tag.objects.annotate(post_count=Count('posts'))

    paginator = Paginator(posts, 3)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'blog/post_list.html', {
        'page_obj': page_obj,
        'posts': posts,
        'tags': tags,
        'selected_tag': tag_slug
    })

