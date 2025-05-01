from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

# Стандартные маршруты
urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('blog.urls')),
    path('api/accounts/', include('accounts.urls')),
]

# полный путь к медиа файлам
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Маршруты для получения токена при входе и обновления токена
urlpatterns += [
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
]