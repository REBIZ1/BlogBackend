from django.db import models
from django.contrib.auth.models import AbstractUser
import os
from django.conf import settings

class CustomUser(AbstractUser):
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)
    subscriptions_last_checked = models.DateTimeField(null=True, blank=True)

    def save(self, *args, **kwargs):
        try:
            # Получаем старую версию объекта из базы
            this = CustomUser.objects.get(id=self.id)
            if this.avatar != self.avatar and this.avatar:
                old_path = os.path.join(settings.MEDIA_ROOT, this.avatar.name)
                if os.path.exists(old_path):
                    os.remove(old_path)
        except CustomUser.DoesNotExist:
            pass  # Новый пользователь — нечего удалять

        super().save(*args, **kwargs)

    def __str__(self):
        return self.username
