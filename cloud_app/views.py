from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required

def home_view(request):
    return render(request, 'base.html')

def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            next_url = request.POST.get('next', '')
            if next_url:
                return redirect(next_url)
            return redirect('home')
        else:
            messages.error(request, '帳號或密碼錯誤')
    
    next_url = request.GET.get('next', '')
    return render(request, 'login.html', {'next': next_url})

def logout_view(request):
    logout(request)
    return redirect('home')

@login_required(login_url='login')
def obituary_base(request):
    return render(request, 'obituary_base.html')

@login_required(login_url='login')
def create_obituary(request):
    if request.method == 'POST':
        # 處理表單提交的邏輯
        pass
    return render(request, 'obituary_maker.html')

@login_required(login_url='login')
def search_obituary(request):
    return render(request, 'search_obituary.html')

@login_required(login_url='login')
def preview_obituary(request):
    if request.method == 'POST':
        preview_data = {
            'deceased_name': request.POST.get('deceased_name', ''),
            'birth_date': request.POST.get('birth_date', ''),
            'death_date': request.POST.get('death_date', ''),
            'ceremony_details': request.POST.get('ceremony_details', ''),
            'location_name': request.POST.get('location_name', ''),
            'location_address': request.POST.get('location_address', ''),
            'location_area': request.POST.get('location_area', ''),
            'traffic_info': request.POST.get('traffic_info', ''),
            'flower_gift_description': request.POST.get('flower_gift_description', ''),
            'memorial_video': request.POST.get('memorial_video', ''),
            'agent_name': request.POST.get('agent_name', ''),
            'agent_phone': request.POST.get('agent_phone', ''),
            'desktop_background': request.POST.get('desktop_background', ''),
            'mobile_background': request.POST.get('mobile_background', '')
        }
        
        # 處理照片文件
        if 'deceased_photo' in request.FILES:
            preview_data['deceased_photo'] = request.FILES['deceased_photo']
            
        return render(request, 'preview_obituary.html', {'data': preview_data})
    return redirect('create_obituary')
