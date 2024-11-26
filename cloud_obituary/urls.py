from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from cloud_app import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('cloud_app.urls')),
    path('buy_car/', views.buy_car, name='buy_car'),
    # path('favicon.ico', RedirectView.as_view(url='/static/favicon.ico')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
