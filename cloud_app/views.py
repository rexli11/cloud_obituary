from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.template import Library

register = Library()

@register.filter
def split(value, arg):
    return value.split(arg)

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
            'hide_birth_date': request.POST.get('hide_birth_date') == 'on',
            'hide_death_date': request.POST.get('hide_death_date') == 'on',
            'ceremony_details': request.POST.get('ceremony_details', ''),
            'desktop_background': request.POST.get('desktop_background', ''),
            'mobile_background': request.POST.get('mobile_background', ''),
            'font_style': request.POST.get('font_style', 'fangsong'),
            'ceremony_times': [],
            'deceased_photo': None,
            'obituary_front_image': None,
            'obituary_back_image': None,
            'location_name': request.POST.get('farewell_location_name', ''),
            'location_address': request.POST.get('farewell_location_address', ''),
            'location_area': request.POST.get('farewell_location_area', ''),
            'traffic_info': request.POST.get('farewell_traffic_info', ''),
            'tomb_location_name': request.POST.get('tomb_location_name', ''),
            'tomb_location_address': request.POST.get('tomb_location_address', ''),
            'tomb_location_area': request.POST.get('tomb_location_area', ''),
            'tomb_traffic_info': request.POST.get('tomb_traffic_info', ''),
        }
        
        # 處理個人照片
        if 'deceased_photo' in request.FILES:
            try:
                photo = request.FILES['deceased_photo']
                import base64
                photo_data = base64.b64encode(photo.read()).decode()
                preview_data['deceased_photo'] = f'data:image/jpeg;base64,{photo_data}'
                print("個人照片處理成功")
            except Exception as e:
                print(f"個人照片處理錯誤：{str(e)}")
        
        # 處理儀式流程數據
        times = request.POST.getlist('ceremony_time[]')
        contents = request.POST.getlist('ceremony_content[]')
        if times and contents:
            preview_data['ceremony_times'] = list(zip(times, contents))
            print("儀式流程數據：", preview_data['ceremony_times'])
        
        # 處理訃聞照片
        for photo_type in ['obituary_front_image', 'obituary_back_image']:
            try:
                if photo_type in request.FILES:
                    photo = request.FILES[photo_type]
                    import base64
                    photo_data = base64.b64encode(photo.read()).decode()
                    preview_data[photo_type] = f'data:image/jpeg;base64,{photo_data}'
                    print(f"{photo_type} 處理成功")
                else:
                    print(f"沒有收到 {photo_type}")
            except Exception as e:
                print(f"{photo_type} 處理錯誤：{str(e)}")

        print("準備渲染預覽頁面")
        return render(request, 'preview_obituary.html', {'data': preview_data})
    
    print("非POST請求，重定向到create_obituary")
    return redirect('create_obituary')
