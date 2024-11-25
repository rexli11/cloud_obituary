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
        # 處理 YouTube URL
        memorial_video = request.POST.get('memorial_video', '')
        if memorial_video and 'youtube.com' in memorial_video:
            # 從 URL 中提取影片 ID
            if 'watch?v=' in memorial_video:
                video_id = memorial_video.split('watch?v=')[1].split('&')[0]
            elif 'youtu.be/' in memorial_video:
                video_id = memorial_video.split('youtu.be/')[1].split('?')[0]
            else:
                video_id = ''
            
            # 生成嵌入式 URL
            if video_id:
                memorial_video = f'https://www.youtube.com/embed/{video_id}'

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
            'flower_gift_description': request.POST.get('flower_gift_description', ''),
            'flower_gifts': [],
            'memorial_video': memorial_video,
            'life_photos': [],
            'agent_name': request.POST.get('agent_name', ''),
            'agent_phone': request.POST.get('agent_phone', ''),
        }

        # 處理花禮
        try:
            flower_gifts = []
            indices = set()
            # 測試接收
            # print("所有 POST 鍵值:", request.POST.keys())
            # print("所有 FILES 鍵值:", request.FILES.keys())
            
            # 修改索引提取方式
            for key in request.POST:
                if 'flower_gift_list[' in key and '][name]' in key:
                    index = key.split('[')[1].split(']')[0]
                    indices.add(index)
            
            # print(f"找到的花禮索引: {indices}")

            for index in sorted(indices):
                name = request.POST.get(f'flower_gift_list[{index}][name]', '').strip()
                price = request.POST.get(f'flower_gift_list[{index}][price]', '').strip()
                image_key = f'flower_gift_list[{index}][image]'
                # 測試接收值
                # print(f"處理花禮 {index}:")
                # print(f"- 名稱: {name}")
                # print(f"- 價格: {price}")
                # print(f"- 圖片鍵值: {image_key}")
                
                # 創建花禮對象
                gift = {
                    'name': name or '無名稱',
                    'price': price or '無價格',
                    'image': None
                }
                
                # 檢查是否有圖片文件
                image_file = request.FILES.get(image_key)
                if image_file:
                    # print(f"- 找到圖片文件: {image_file.name}")
                    try:
                        import base64
                        photo_data = base64.b64encode(image_file.read()).decode()
                        gift['image'] = f'data:{image_file.content_type};base64,{photo_data}'
                        # print("- 成功處理圖片")
                    except Exception as e:
                        pass
                        # print(f"- 圖片處理錯誤: {str(e)}")
                else:
                    pass
                    # print(f"- 未找到圖片文件: {image_key}")
                
                flower_gifts.append(gift)
                # print(f"- 成功添加花禮: {gift}")
            
            preview_data['flower_gifts'] = flower_gifts
            # print(f"最終處理的花禮數量: {len(flower_gifts)}")
            
        except Exception as e:
            pass
            # print(f"花禮處理錯誤：{str(e)}")
            # import traceback
            # print(traceback.format_exc())

        # 處理生活照
        try:
            life_photos = []
            
            # 從 FILES 中獲取生活照
            life_photo_keys = sorted([k for k in request.FILES.keys() if k.startswith('life_photos[')])
            # print(f"找到的生活照文件鍵值: {life_photo_keys}")
            
            for key in life_photo_keys:
                photo = request.FILES[key]
                if photo and photo.content_type.startswith('image/'):
                    try:
                        # print(f"處理生活照: {key}")
                        import base64
                        photo_data = base64.b64encode(photo.read()).decode()
                        life_photos.append(f'data:{photo.content_type};base64,{photo_data}')
                        # print(f"成功處理生活照: {key}")
                    except Exception as e:
                        pass
                        # print(f"生活照 {key} 處理錯誤: {str(e)}")
            
            preview_data['life_photos'] = life_photos
            # print(f"最終處理的生活照數量: {len(life_photos)}")

        except Exception as e:
            pass
            # print(f"生活照處理錯誤：{str(e)}")
            # import traceback
            # print(traceback.format_exc())

        # 處理其他照片和數據
        try:
            if 'deceased_photo' in request.FILES:
                photo = request.FILES['deceased_photo']
                import base64
                photo_data = base64.b64encode(photo.read()).decode()
                preview_data['deceased_photo'] = f'data:image/jpeg;base64,{photo_data}'
        except Exception as e:
            pass
            # print(f"個人照片處理錯誤：{str(e)}")

        # 處理儀式流程
        try:
            times = request.POST.getlist('ceremony_time[]')
            contents = request.POST.getlist('ceremony_content[]')
            if times and contents:
                preview_data['ceremony_times'] = list(zip(times, contents))
        except Exception as e:
            pass
            # print(f"儀式流程處理錯誤：{str(e)}")

        # 處理訃聞照片
        try:
            for photo_type in ['obituary_front_image', 'obituary_back_image']:
                if photo_type in request.FILES:
                    photo = request.FILES[photo_type]
                    import base64
                    photo_data = base64.b64encode(photo.read()).decode()
                    preview_data[photo_type] = f'data:image/jpeg;base64,{photo_data}'
        except Exception as e:
            pass
            # print(f"訃聞照片處理錯誤：{str(e)}")

        return render(request, 'preview_obituary.html', {'data': preview_data})

    return redirect('create_obituary')
