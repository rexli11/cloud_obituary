from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from . import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.home_view, name='home'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('obituary/', views.obituary_base, name='obituary_base'),
    path('obituary/create/', views.create_obituary, name='create_obituary'),
    path('obituary/search/', views.search_obituary, name='search_obituary'),
    path('preview_obituary/', views.preview_obituary, name='preview_obituary'),
    path('case_management/', views.case_management, name='case_management'),
    path('buy_car/', views.buy_car, name='buy_car'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT) 