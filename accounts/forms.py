from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import CustomUser
from blog.models import Post

class CustomUserCreationForm(UserCreationForm):
    class Meta:
        model = CustomUser
        fields = ['username', 'email', 'avatar', 'password1', 'password2']

class CustomUserEditForm(forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = ['username', 'email', 'avatar']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
        }

class PostCreateForm(forms.ModelForm):
    class Meta:
        model = Post
        fields = ['title', 'cover', 'content', 'tags']