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
    path('register/', views.register, name='register'),
    path('preview_employee/', views.preview_employee, name='preview_employee'),
    path('toggle_active/<int:user_id>/', views.toggle_active, name='toggle_active'),
    path('delete_employee/<int:user_id>/', views.delete_employee, name='delete_employee'),
    path('make_obituary/', views.make_obituary, name='make_obituary'),
    path('obituary/view/<int:obituary_id>/', views.view_obituary, name='view_obituary'),
    path('obituary/delete/<int:obituary_id>/', views.delete_obituary, name='delete_obituary'),
    path('obituary/edit/<int:obituary_id>/', views.edit_obituary, name='edit_obituary'),
    path('obituary/count/<int:obituary_id>/', views.count_obituary_click, name='count_obituary_click'),
] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT) 