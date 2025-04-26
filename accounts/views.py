from django.shortcuts import render, redirect
from  django.contrib.auth import login, logout, authenticate
from django.contrib import messages
from .forms import CustomUserCreationForm, CustomUserEditForm, PostCreateForm
from blog.models import Post, ReadingTime
from django.contrib.auth.decorators import login_required

def register_view(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST, request.FILES)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('post_list')
    else:
        form = CustomUserCreationForm
    return render(request, 'accounts/register.html', {'form': form})

def logout_view(request):
    logout(request)
    return redirect('post_list')

@login_required
def favorites_view(request):
    liked_posts = Post.objects.filter(likes__user=request.user).order_by('-created_at')
    return render(request, 'accounts/favorites.html', {
        'liked_posts': liked_posts,
        'active_tab': 'favorites'
    })

@login_required
def create_post_placeholder(request):
    return render(request, 'accounts/create.html', {'active_tab': 'create'})

@login_required
def history_view(request):
    history_posts = ReadingTime.objects.filter(user=request.user).order_by('-timestamp')

    return render(request, 'accounts/history.html', {
        'history_posts': history_posts,
        'active_tab': 'history'
    })

@login_required
def account_settings_view(request):
    if request.method == 'POST':
        form = CustomUserEditForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Профиль обновлен успешно.')
            return redirect('account_settings')
    else:
        form = CustomUserEditForm(instance=request.user)

    return render(request, 'accounts/settings.html', {
        'form': form,
        'active_tab': 'settings'
    })

@login_required
def create_post(request):
    if request.method == 'POST':
        form = PostCreateForm(request.POST, request.FILES)
        if form.is_valid():
            post = form.save(commit=False)
            post.author = request.user
            post.save()
            form.save_m2m()
            messages.success(request, 'Статья успешно создана!')
            return redirect('create_post')
    else:
        form = PostCreateForm()

    return render(request, 'accounts/create.html', {
        'form': form,
        'active_tab': 'create'
    })