from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout
import mysql.connector
from django.conf import settings

def connection_db():
    """建立資料庫連線"""
    try:
        db = mysql.connector.connect(
            host=settings.DATABASES['default']['HOST'],
            user=settings.DATABASES['default']['USER'],
            password=settings.DATABASES['default']['PASSWORD'],
            database=settings.DATABASES['default']['NAME'],
            port=settings.DATABASES['default']['PORT']
        )
        return db
    except mysql.connector.Error as err:
        print(f"資料庫連線錯誤: {err}")
        return None

def check_permissions(request, requested_page=None):
    """
    從 session 檢查用戶權限
    requested_page: 'case_management' | 'obituary' | 'dashboard'
    """
    permission_level = request.session.get('permission_level')
    
    if permission_level is None:
        return None
        
    # 如果沒有指定頁面，只返回權限等級
    if not requested_page:
        return permission_level
        
    # 管理員可以訪問所有頁面
    if permission_level == '0':
        return True
        
    # 檢查特定頁面的訪問權限
    if requested_page == 'case_management':
        return permission_level in ['1', '2']
    elif requested_page == 'obituary':
        return permission_level in ['1', '3']
    elif requested_page == 'dashboard':
        return permission_level in ['1', '2', '3', '4']
        
    return False

def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        next_url = request.POST.get('next', '')
        
        print(f"登入嘗試 - 用戶名: {username}")  # 调试信息
        
        db = connection_db()
        if db is None:
            messages.error(request, '系統錯誤，請稍後再試')
            return render(request, 'login.html')
        
        cursor = db.cursor()
        try:
            cursor.execute("""
                SELECT u.user_id, u.username, u.password, p.permission_type
                FROM users u
                LEFT JOIN permissions p ON u.user_id = p.user_id
                WHERE u.username = %s AND u.password = %s
            """, [username, password])
            user_data = cursor.fetchone()
            
            if user_data:
                print(f"登入成功 - 用戶數據: {user_data}")  # 调试信息
                
                request.session['user_id'] = user_data[0]
                request.session['username'] = user_data[1] 
                request.session['permission_level'] = user_data[3]
                request.session['is_authenticated'] = True
                
                # 登入成功後直接重定向到首頁
                return redirect('home')
            else:
                print("登入失敗 - 用戶名或密碼錯誤")  # 调试信息
                messages.error(request, '帳號或密碼錯誤')
                return render(request, 'login.html', {'next': next_url})
        
        except mysql.connector.Error as err:
            print(f"數據庫錯誤: {err}")  # 调试信息
            messages.error(request, '系統錯誤，請稍後再試')
            return render(request, 'login.html', {'next': next_url})
        
        finally:
            cursor.close()
            db.close()
    
    # GET 請求
    next_url = request.GET.get('next', '')
    return render(request, 'login.html', {'next': next_url})

def home_view(request):
    if not request.session.get('user_id'):
        return redirect('login')
    
    permission_level = request.session.get('permission_level')
    print(f"首頁訪問 - 權限等級: {permission_level}")  # 调试信息
    
    context = {
        'username': request.session.get('username'),
        'can_access_case': permission_level in ['0', '1', '2'],
        'can_access_obituary': permission_level in ['0', '1', '3'],
        'can_access_dashboard': permission_level in ['0', '1', '2', '3', '4']
    }
    return render(request, 'base.html', context)

def logout_view(request):
    """登出用戶"""
    # 清除 session
    request.session.flush()
    # 執行登出
    logout(request)
    # 重定向到首頁
    return redirect('home')

@login_required(login_url='login')
def obituary_base(request):
    """訃聞製作基礎頁面"""
    # 添加调试信息
    print(f"訪問訃聞頁面")
    print(f"Session 數據: {dict(request.session)}")
    print(f"權限等級: {request.session.get('permission_level')}")
    
    permission_level = request.session.get('permission_level')
    
    if permission_level in ['0', '1', '3']:
        return render(request, 'obituary_base.html')
    else:
        messages.error(request, '您沒有權限訪問此頁面')
        return redirect('home')

@login_required(login_url='login')
def create_obituary(request):
    """創建新訃聞"""
    # 檢查用戶是否已登入
    if not request.session.get('user_id'):
        messages.error(request, '請先登入')
        return redirect('login')
    
    # 檢查用戶權限
    permission_level = request.session.get('permission_level')
    if permission_level not in [0, 1, 3]:  # 只有管理員、第一級和第三級權限可以訪問
        messages.error(request, '您沒有權限訪問此頁面')
        return redirect('home')
    
    return render(request, 'obituary_maker.html')

@login_required(login_url='login')
def search_obituary(request):
    """搜尋訃聞"""
    # 檢查用戶是否已登入
    if not request.session.get('user_id'):
        messages.error(request, '請先登入')
        return redirect('login')
    
    # 檢查用戶權限
    permission_level = request.session.get('permission_level')
    if permission_level not in [0, 1, 3]:
        messages.error(request, '您沒有權限訪問此頁面')
        return redirect('home')
    
    return render(request, 'search_obituary.html')

@login_required(login_url='login')
def preview_obituary(request):
    """覽訃聞"""
    if request.method == 'POST':
        preview_data = {
            'deceased_name': request.POST.get('deceased_name', ''),
            'birth_date': request.POST.get('birth_date', ''),
            'death_date': request.POST.get('death_date', ''),
            'hide_birth_date': request.POST.get('hide_birth_date') == 'on',
            'hide_death_date': request.POST.get('hide_death_date') == 'on',
            'ceremony_details': request.POST.get('ceremony_details', ''),
            'desktop_background': request.POST.get('desktop_background', ''),
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
            'life_photos': [],
            'agent_name': request.POST.get('agent_name', ''),
            'agent_phone': request.POST.get('agent_phone', ''),
            'background_music': request.POST.get('background_music', ''),
        }
        return render(request, 'preview_obituary.html', {'data': preview_data})
    return redirect('create_obituary')

@login_required(login_url='login')
def buy_car(request):
    """購物車頁面"""
    if not request.session.get('user_id'):
        messages.error(request, '請先登入')
        return redirect('login')
    
    # 檢查用戶權限
    permission_level = request.session.get('permission_level')
    if permission_level not in [0, 1, 3]:
        messages.error(request, '您沒有權限訪問此頁面')
        return redirect('home')
    
    return render(request, 'buy_car.html')

@login_required(login_url='login')
def case_management(request):
    """案件管理頁面"""
    # 檢查用戶是否已登入
    if not request.session.get('is_authenticated'):
        messages.error(request, '請先登入')
        return redirect('login')
    
    # 檢查用戶權限
    permission_level = request.session.get('permission_level')
    print(f"Current permission level for case management: {permission_level}")  # 調試用
    
    # 轉換權限值為字符串進行比較
    if str(permission_level) in ['0', '1', '2']:  # 管理員、第一級和第二級權限可以訪問
        return render(request, 'case_management.html')
    
    messages.error(request, '您沒有權限訪問此頁面')
    return redirect('home')

# ... 其他視圖函數保持不變 ...