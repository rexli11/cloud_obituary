from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout
import mysql.connector
from django.conf import settings
from google.oauth2 import service_account
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from datetime import datetime
import io
import os
from google.auth.transport.requests import Request
import json
from django.template.loader import render_to_string
from django.http import JsonResponse
from django.views.decorators.http import require_POST
import time
from .models import ObituaryClick
from django.views.decorators.csrf import ensure_csrf_cookie, csrf_exempt
from django.middleware.csrf import get_token

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

# def check_permissions(request, requested_page=None):
#     """
#     從 session 檢查用戶權限
#     requested_page: 'case_management' | 'obituary' | 'dashboard'
#     """
#     permission_level = request.session.get('permission_level')
    
#     if permission_level is None:
#         return None
        
#     # 如果沒有指定頁面，只返回權限等級
#     if not requested_page:
#         return permission_level
        
#     # 管理員可以訪問所有頁面
#     if permission_level == '0':
#         return True
        
#     # 檢查特定頁面的訪問權限
#     if requested_page == 'case_management':
#         return permission_level in ['1', '2']
#     elif requested_page == 'obituary':
#         return permission_level in ['1', '3']
#     elif requested_page == 'dashboard':
#         return permission_level in ['1', '2', '3', '4']
        
#     return False

def login_view(request):
    print(f"當前session狀態: {dict(request.session)}")  # 调试信息
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        next_url = request.POST.get('next', '')
        
        print(f"登入嘗 - 用戶名: {username}")  # 调试信
        
        db = connection_db()
        if db is None:
            messages.error(request, '系錯誤，請稍後再試')
            return render(request, 'login.html')
            
        cursor = db.cursor(dictionary=True)  # 使用 dictionary=True 來獲取列名
        try:
            # 修正 SQL 查询中的字段名
            cursor.execute("""
                SELECT 
                    u.user_id,
                    u.username,
                    u.password,
                    u.realname,
                    u.phone,
                    u.email,
                    u.department,
                    u.title,
                    u.company,
                    u.is_active,
                    u.is_superuser,
                    u.created_at,
                    u.updated_at,  # 修改 update_at 为 updated_at
                    p.permission_type
                FROM users u
                LEFT JOIN permissions p ON u.user_id = p.user_id
                WHERE u.username = %s AND u.password = %s
            """, [username, password])
            
            user_data = cursor.fetchone()
            
            if user_data:
                print(f"登入成功 - 用戶數據: {user_data}")  # 调试信息
                
                # 將所有資料存入 session
                request.session['user_id'] = user_data['user_id']
                request.session['username'] = user_data['username']
                request.session['realname'] = user_data['realname']
                request.session['phone'] = user_data['phone']
                request.session['email'] = user_data['email']
                request.session['department'] = user_data['department']
                request.session['title'] = user_data['title']
                request.session['company'] = user_data['company']
                request.session['is_active'] = user_data['is_active']
                request.session['is_superuser'] = user_data['is_superuser']
                request.session['created_at'] = user_data['created_at'].isoformat() if user_data['created_at'] else None
                request.session['updated_at'] = user_data['updated_at'].isoformat() if user_data['updated_at'] else None  # 修改字段名
                request.session['permission_level'] = user_data['permission_type']
                request.session['is_authenticated'] = True
                
                print(f"設置session後: {dict(request.session)}")  # 调试信息
                
                if next_url:
                    return redirect(next_url)
                return redirect('home')
            else:
                print("登失敗 - 用戶名或密碼錯誤")  # 调试信息
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
    if request.session.get('is_authenticated'):
        if next_url:
            return redirect(next_url)
        return redirect('home')
        
    return render(request, 'login.html', {'next': next_url})

def home_view(request):
    print(f"home_view session狀態: {dict(request.session)}")  # 调试信息
    
    if not request.session.get('is_authenticated'):
        return redirect('login')
    
    # 获取权限等级
    permission_level = request.session.get('permission_level')
    
    context = {
        'username': request.session.get('username'),
        'can_access_case': permission_level in ['0', '1', '2'],
        'can_access_obituary': permission_level in ['0', '1', '3'],
        'can_access_dashboard': True,
        'permission_level': permission_level  # 保传递权限等级到模板
    }
    return render(request, 'base.html', context)

def logout_view(request):
    """登出用戶"""
    request.session.flush()
    logout(request)
    return redirect('home')

def obituary_base(request):
    """訃聞列表頁面"""
    if not request.session.get('is_authenticated'):
        return redirect('login')
        
    db = connection_db()
    if db is None:
        messages.error(request, '系統錯誤，請稍後再試')
        return redirect('home')
        
    cursor = db.cursor(dictionary=True)
    try:
        # 直接從 obituary 表獲取 view_count
        cursor.execute("""
            SELECT id, service_area, deceased_name, created_at, file_path,
                   COALESCE(view_count, 0) as view_count
            FROM obituary 
            ORDER BY created_at DESC
        """)
        
        obituaries = cursor.fetchall()
        
        # 添加日誌輸出
        print("\n當前所有訃聞的點擊統計:")
        for obituary in obituaries:
            print(f"訃聞 ID: {obituary['id']}")
            print(f"- 往生者: {obituary['deceased_name']}")
            print(f"- 點擊次數: {obituary['view_count']}")
            print("-" * 30)
        
        # 修改連結格式
        for obituary in obituaries:
            if obituary['file_path']:
                obituary['file_path'] = f"/static/obituaries/{obituary['file_path']}"
                
        return render(request, 'obituary_base.html', {'obituaries': obituaries})
        
    except Exception as e:
        print(f"獲取訃聞列表錯誤: {e}")
        messages.error(request, '系統錯誤，請稍後再試')
        return redirect('home')
        
    finally:
        cursor.close()
        db.close()

def create_obituary(request):
    """創新訃聞"""
    # if not request.session.get('is_authenticated'):
    #     return redirect('login')
    return render(request, 'obituary_maker.html')

def search_obituary(request):
    """搜尋訃聞"""
    # if not request.session.get('is_authenticated'):
    #     return redirect('login')
    return render(request, 'search_obituary.html')

# Google Drive API 設置
SCOPES = ['https://www.googleapis.com/auth/drive']
FOLDER_ID = '1vl5PUbbIKwBeBW5Q_DtvzqH8MCsm9jEs'
SERVICE_ACCOUNT_FILE = 'D:\\yz_cloud_obituary\\cloud_obituary\\key\\test-cloud-443501-2b5eb85fe489.json'

def get_google_drive_service():
    """初始化 Google Drive API 服務"""
    try:
        # 使用服務帳號憑證
        credentials = service_account.Credentials.from_service_account_file(
            SERVICE_ACCOUNT_FILE, 
            scopes=SCOPES
        )
        
        # 建立服務
        service = build('drive', 'v3', credentials=credentials)
        return service
        
    except Exception as e:
        print(f"Google Drive API 初始化錯誤: {e}")
        return None

def upload_to_drive(file_bytes, filename, folder_id):
    """上傳檔案到指定的 Google Drive 資料夾並返回檔案連結"""
    service = get_google_drive_service()
    if not service:
        return None
    
    try:
        # 準備檔案數據
        file_metadata = {
            'name': filename,
            'parents': [folder_id]
        }
        
        # 創建媒體檔案
        fh = io.BytesIO(file_bytes)
        media = MediaIoBaseUpload(fh, mimetype='image/jpeg', resumable=True)
        
        # 上傳檔案
        file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id, webViewLink'
        ).execute()
        
        # 修改檔案權限為所有人可讀
        permission = {
            'type': 'anyone',
            'role': 'reader'
        }
        service.permissions().create(
            fileId=file.get('id'),
            body=permission
        ).execute()
        
        return file.get('webViewLink')
        
    except Exception as e:
        print(f"檔案上傳錯誤: {e}")
        return None

@ensure_csrf_cookie
def preview_obituary(request):
    """預覽訃聞"""
    if request.method == 'POST':
        try:
            # 检查登录状态
            if not request.session.get('is_authenticated'):
                messages.error(request, '請先登入')
                return redirect('login')
            
            # 獲取服務處選擇
            area_selection = request.POST.get('area_selection')
            
            # 获取表单数据
            preview_data = {
                'deceased_name': request.POST.get('deceased_name', ''),
                'birth_date': request.POST.get('birth_date', ''),
                'death_date': request.POST.get('death_date', ''),
                'hide_birth_date': request.POST.get('hide_birth_date') == 'on',
                'hide_death_date': request.POST.get('hide_death_date') == 'on',
                'ceremony_details': request.POST.get('ceremony_details', ''),
                'desktop_background': request.POST.get('desktop_background', ''),
                'font_style': request.POST.get('font_style', 'fangsong'),
                'location_name': request.POST.get('farewell_location_name', ''),
                'location_address': request.POST.get('farewell_location_address', ''),
                'location_area': request.POST.get('farewell_location_area', ''),
                'traffic_info': request.POST.get('farewell_traffic_info', ''),
                'tomb_location_name': request.POST.get('tomb_location_name', ''),
                'tomb_location_address': request.POST.get('tomb_location_address', ''),
                'tomb_location_area': request.POST.get('tomb_location_area', ''),
                'tomb_traffic_info': request.POST.get('tomb_traffic_info', ''),
                'flower_gift_description': request.POST.get('flower_gift_description', ''),
                'agent_name': request.POST.get('agent_name', ''),
                'agent_phone': request.POST.get('agent_phone', ''),
                'background_music': request.POST.get('background_music', ''),
                'ceremony_items': [],
                'flower_gifts': [],
                'life_photos': [],
                'deceased_photo': None,
                'obituary_front': None,
                'obituary_back': None,
                
                # 添加服務處相關資訊
                'area_selection': area_selection,
                'title_icon': 'images/title-icon-2.png' if area_selection in ['1', '3'] else 'images/title-icon.png',
                'logo_img': 'images/title-icon-2.png' if area_selection in ['1', '3'] else 'images/logo.jpg',
                'google_map_link': 'https://maps.app.goo.gl/TQpZFGBWYPHZGNYt9' if area_selection == '1' else 'https://maps.app.goo.gl/cQEdZ9SVdXe9d4zm7',
                'company_name': '楊子北服務處' if area_selection == '1' else '楊子南區服務處' if area_selection == '3' else '楊子佛教禮儀(股)公司'
            }

            # youtube連結
            video_url = request.POST.get('memorial_video', '')
            if video_url:
                video_id = extract_youtube_id(video_url)
                if video_id:
                    preview_data['memorial_video'] = video_id

            # 處理儀式時間和內容
            ceremony_times = request.POST.getlist('ceremony_time[]', [])
            ceremony_contents = request.POST.getlist('ceremony_content[]', [])
            
            # 組合儀式流程數據
            for time, content in zip(ceremony_times, ceremony_contents):
                preview_data['ceremony_items'].append({
                    'time': time,
                    'content': content
                })

            # 處理上傳圖片
            if 'deceased_photo' in request.FILES:
                file = request.FILES['deceased_photo']
                import base64
                preview_data['deceased_photo'] = f"data:image/{file.content_type.split('/')[-1]};base64,{base64.b64encode(file.read()).decode()}"
                
            if 'obituary_front_image' in request.FILES:
                file = request.FILES['obituary_front_image']
                import base64
                preview_data['obituary_front'] = f"data:image/{file.content_type.split('/')[-1]};base64,{base64.b64encode(file.read()).decode()}"
                
            if 'obituary_back_image' in request.FILES:
                file = request.FILES['obituary_back_image']
                import base64
                preview_data['obituary_back'] = f"data:image/{file.content_type.split('/')[-1]};base64,{base64.b64encode(file.read()).decode()}"

            # 處理生活照片
            for key in request.FILES:
                if key.startswith('life_photos['):
                    file = request.FILES[key]
                    import base64
                    preview_data['life_photos'].append(
                        f"data:image/{file.content_type.split('/')[-1]};base64,{base64.b64encode(file.read()).decode()}"
                    )

            # 處理花禮照片
            for key in request.FILES:
                if key.startswith('flower_gift_list['):
                    index = key[key.find('[')+1:key.find(']')]
                    name = request.POST.get(f'flower_gift_list[{index}][name]', '')
                    price = request.POST.get(f'flower_gift_list[{index}][price]', '')
                    orderable = request.POST.get(f'flower_gift_list[{index}][orderable]') == 'on'
                    file = request.FILES[key]
                    import base64
                    image = f"data:image/{file.content_type.split('/')[-1]};base64,{base64.b64encode(file.read()).decode()}"
                    preview_data['flower_gifts'].append({
                        'name': name,
                        'price': price,
                        'image': image,
                        'orderable': orderable
                    })

            return render(request, 'preview_obituary.html', {'data': preview_data})
            
        except Exception as e:
            print(f"預覽錯誤: {e}")
            messages.error(request, '預覽失敗，請稍後再試')
            return redirect('create_obituary')
    
    return redirect('create_obituary')

def extract_youtube_id(url):
    """从 YouTube URL 提取视频 ID"""
    if not url:
        return None
        
    import re
    
    # 处理多种 YouTube URL 格式
    patterns = [
        r'(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/)([^&\?\/]+)',
        r'youtube\.com\/watch\?.*v=([^&]+)',
        r'youtube\.com\/shorts\/([^&\?\/]+)'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    
    return None

def buy_car(request):
    """購物車頁面"""
    # if not request.session.get('is_authenticated'):
    #     return redirect('login')
    return render(request, 'buy_car.html')

def case_management(request):
    """案件管理頁面"""
    if not request.session.get('is_authenticated'):
        return redirect('login')
    return render(request, 'case_management.html')

def register(request):
    """職員註冊頁面"""
    print(f"訪問註冊頁面")  # 调试信息
    print(f"當前用戶權: {request.session.get('permission_level')}")  # 调试信息
    print(f"Session 數據: {dict(request.session)}")  # 调试信息
    
    # 檢查是否已登入
    if not request.session.get('is_authenticated'):
        messages.error(request, '先登')
        return redirect('login')
    
    # 檢查是否為超級用戶
    if not request.session.get('permission_level') == '0':
        messages.error(request, '您沒有權限訪問此頁面')
        return redirect('home')
    
    if request.method == 'POST':
        # 獲取表單數據
        username = request.POST.get('username')
        password = request.POST.get('password')
        realname = request.POST.get('realname')
        phone = request.POST.get('phone')
        email = request.POST.get('email')
        department = request.POST.get('department')
        title = request.POST.get('title')
        company = request.POST.get('company')
        is_active = 1 if request.POST.get('is_active') else 0
        is_superuser = 1 if request.POST.get('is_superuser') else 0
        permission_type = request.POST.get('permission_type')
        
        # 連接資料庫
        db = connection_db()
        if db is None:
            messages.error(request, '系錯誤請稍後再試')
            return render(request, 'register.html')
        
        cursor = db.cursor()
        try:
            # 插入用戶資料到 users 表
            cursor.execute("""
                INSERT INTO users 
                (username, password, realname, phone, email, department, title, 
                company, is_active, is_superuser, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
            """, [username, password, realname, phone, email, department, 
                 title, company, is_active, is_superuser])
            
            # 獲取新插入的用戶ID
            user_id = cursor.lastrowid
            
            # 插入權限資料到 permissions 表
            cursor.execute("""
                INSERT INTO permissions (user_id, permission_type)
                VALUES (%s, %s)
            """, [user_id, permission_type])
            
            # 提交事務
            db.commit()
            
            # 準備成功訊息
            success_message = f"""
                註冊成功！
                用戶名：{username}
                姓名：{realname}
                密碼：{password}
                電話：{phone}
                電子郵：{email}
                部門：{department}
                職稱：{title}
                公司：{company}
                權限等級：{permission_type}
                是否啟動：{'是' if is_active else '否'}
                是否為管理員：{'是' if is_superuser else '否'}
            """
            messages.success(request, success_message)
            
            # 直接返回当前页面，保留消息
            return render(request, 'register.html', {'session': request.session})
            
        except mysql.connector.Error as err:
            # 發生錯誤時回滾
            db.rollback()
            print(f"數據庫錯誤: {err}")
            messages.error(request, f'註冊失敗：{err}')
            return render(request, 'register.html', {'session': request.session})
            
        finally:
            # 關資料庫連接
            cursor.close()
            db.close()
    
    # GET 請求
    return render(request, 'register.html', {'session': request.session})

# 在文件末尾添加新函数
def view_obituary(request, obituary_id):
    """查看訃聞頁面"""
    try:
        # 連接資料庫
        db = connection_db()
        if not db:
            raise Exception("資料庫連接失敗")
            
        cursor = db.cursor(dictionary=True)
        
        try:
            # 獲取訃聞資料
            cursor.execute("""
                SELECT * FROM obituary WHERE id = %s
            """, [obituary_id])
            obituary_data = cursor.fetchone()
            
            if not obituary_data:
                messages.error(request, '找不到該訃聞')
                return redirect('obituary_base')
            
            # 獲取照片資料
            cursor.execute("""
                SELECT * FROM photos WHERE obituary_id = %s
            """, [obituary_id])
            photos = cursor.fetchall()
            
            # 準備模板數據
            context = {
                'obituary': obituary_data,
                'photos': photos,
                'data': {
                    'deceased_name': obituary_data['deceased_name'],
                    'birth_date': obituary_data['birth_date'],
                    'death_date': obituary_data['death_date'],
                    'ceremony_details': obituary_data['ceremony_details'],
                    'ceremony_process_list': json.loads(obituary_data['ceremony_process_list']) if obituary_data['ceremony_process_list'] else {},
                    'farewell_form': json.loads(obituary_data['farewell_form']) if obituary_data['farewell_form'] else {},
                    'tomb_form': json.loads(obituary_data['tomb_form']) if obituary_data['tomb_form'] else None,
                    'flower_gift_description': obituary_data['flower_gift_description'],
                    'memorial_video': obituary_data['memorial_video'],
                    'agent_name': obituary_data['agent_name'],
                    'agent_phone': obituary_data['agent_phone'],
                    'service_area': obituary_data['service_area']
                }
            }
            
            return render(request, 'preview_obituary.html', context)
            
        except Exception as e:
            print(f"查看訃聞錯誤: {e}")
            messages.error(request, '無法顯示訃')
            return redirect('obituary_base')
            
        finally:
            cursor.close()
            db.close()
            
    except Exception as e:
        print(f"查看訃聞錯誤: {e}")
        messages.error(request, '系統錯誤')
        return redirect('obituary_base')

def preview_employee(request):
    """查看職員列表"""
    print(f"訪問職員列表頁面")  # 调试信息
    print(f"當前用戶權限: {request.session.get('permission_level')}")  # 调试信息
    
    # 檢查是否已登入
    if not request.session.get('is_authenticated'):
        messages.error(request, '請先登入')
        return redirect('login')
    
    # 檢查權限
    if request.session.get('permission_level') not in ['0', '1']:
        messages.error(request, '您沒有權限訪問此頁面')
        return redirect('home')
    
    # 連接資料庫
    db = connection_db()
    if db is None:
        messages.error(request, '系統錯誤，請稍後再試')
        return redirect('home')
    
    cursor = db.cursor(dictionary=True)
    try:
        # 查詢所有用戶資料
        cursor.execute("""
            SELECT 
                u.user_id,
                u.username,
                u.realname,
                u.phone,
                u.email,
                u.department,
                u.title,
                u.company,
                u.is_active,
                u.is_superuser,
                u.created_at,
                u.updated_at,
                p.permission_type
            FROM users u
            LEFT JOIN permissions p ON u.user_id = p.user_id
            ORDER BY u.user_id
        """)
        
        employees = cursor.fetchall()
        
        # 處理日期時間格式
        for emp in employees:
            emp['created_at'] = emp['created_at'].strftime('%Y-%m-%d %H:%M:%S') if emp['created_at'] else ''
            emp['updated_at'] = emp['updated_at'].strftime('%Y-%m-%d %H:%M:%S') if emp['updated_at'] else ''
        
        return render(request, 'preview_employee.html', {'employees': employees})
        
    except mysql.connector.Error as err:
        print(f"數據庫錯誤: {err}")
        messages.error(request, '系誤，請稍後再試')
        return redirect('home')
        
    finally:
        cursor.close()
        db.close()

def toggle_active(request, user_id):
    """變更用戶啟用狀"""
    if not request.session.get('is_authenticated') or request.session.get('permission_level') not in ['0', '1']:
        messages.error(request, '您沒有權限執行此操作')
        return redirect('home')
    
    db = connection_db()
    if db is None:
        messages.error(request, '系統錯誤，請稍後再試')
        return redirect('preview_employee')
    
    cursor = db.cursor()
    try:
        # 先獲取當前狀態
        cursor.execute("SELECT is_active FROM users WHERE user_id = %s", [user_id])
        current_status = cursor.fetchone()[0]
        
        # 更新狀態
        new_status = 0 if current_status else 1
        cursor.execute("UPDATE users SET is_active = %s WHERE user_id = %s", [new_status, user_id])
        db.commit()
        
        messages.success(request, f'用戶狀態已更新為{"啟用" if new_status else "停用"}')
        
    except mysql.connector.Error as err:
        db.rollback()
        print(f"數據錯誤: {err}")
        messages.error(request, '操作失敗，請稍後再試')
        
    finally:
        cursor.close()
        db.close()
    
    return redirect('preview_employee')

def delete_employee(request, user_id):
    """刪除用戶"""
    if not request.session.get('is_authenticated') or request.session.get('permission_level') not in ['0', '1']:
        messages.error(request, '您沒有權限執行此操作')
        return redirect('home')
    
    db = connection_db()
    if db is None:
        messages.error(request, '系統錯誤，請稍後再試')
        return redirect('preview_employee')
    
    cursor = db.cursor()
    try:
        # 檢查是否為管理員
        cursor.execute("SELECT permission_type FROM permissions WHERE user_id = %s", [user_id])
        permission = cursor.fetchone()
        if permission and permission[0] == '0':
            messages.error(request, '無法刪除管理員帳號')
            return redirect('preview_employee')
        
        # 先刪除權限記錄
        cursor.execute("DELETE FROM permissions WHERE user_id = %s", [user_id])
        # 再刪除用戶記錄
        cursor.execute("DELETE FROM users WHERE user_id = %s", [user_id])
        
        db.commit()
        messages.success(request, '用戶已成功刪除')
        
    except mysql.connector.Error as err:
        db.rollback()
        print(f"數據庫錯誤: {err}")
        messages.error(request, '刪除失敗，稍後再試')
        
    finally:
        cursor.close()
        db.close()
    
    return redirect('preview_employee')

def make_obituary(request):
    """製作訃聞並上傳照片"""
    if request.method == 'POST':
        print("開始處理訃聞製作請求...")
        
        if not request.session.get('is_authenticated'):
            print("用戶未登入")
            messages.error(request, '請先登入')
            return redirect('login')
            
        try:
            print("開始資料庫接...")
            db = connection_db()
            if db is None:
                raise Exception("資料庫連接失敗")
            
            cursor = db.cursor(dictionary=True)
            
            print("開始插入訃聞基本資料...")
            
            # 獲取服務處選擇
            area_selection = request.POST.get('area_selection')
            
            # 獲取往生者姓名
            deceased_name = request.POST.get('deceased_name', '')
            
            # 生成檔案名稱
            file_name = f"obituary_{int(time.time())}.html"
            
            # ��保靜態目錄存在
            static_dir = os.path.join(settings.BASE_DIR, 'static')
            obituaries_dir = os.path.join(static_dir, 'obituaries')
            os.makedirs(obituaries_dir, exist_ok=True)
            
            # 生成完整的檔案路徑
            file_path = os.path.join(obituaries_dir, file_name)
            
            # 插入訃聞基本資料到資料庫
            cursor.execute("""
                INSERT INTO obituary (
                    service_area,
                    deceased_name,
                    birth_date,
                    death_date,
                    ceremony_details,
                    file_path,
                    created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, NOW())
            """, [
                area_selection,
                deceased_name,
                request.POST.get('birth_date') or None,
                request.POST.get('death_date') or None,
                request.POST.get('ceremony_details'),
                file_name  # 只保存檔案名稱，不包含路徑
            ])
            
            # 獲取新插入的訃聞ID
            obituary_id = cursor.lastrowid
            
            # 準備 context 數據
            context = {
                'obituary': {
                    'id': obituary_id  # 添加訃聞 ID
                },
                'data': {
                    'deceased_name': deceased_name,
                    'birth_date': request.POST.get('birth_date', ''),
                    'death_date': request.POST.get('death_date', ''),
                    'hide_birth_date': request.POST.get('hide_birth_date') == 'on',
                    'hide_death_date': request.POST.get('hide_death_date') == 'on',
                    'ceremony_details': request.POST.get('ceremony_details', ''),
                    'desktop_background': request.POST.get('desktop_background', ''),
                    'font_style': request.POST.get('font_style', 'fangsong'),
                    'location_name': request.POST.get('farewell_location_name', ''),
                    'location_address': request.POST.get('farewell_location_address', ''),
                    'location_area': request.POST.get('farewell_location_area', ''),
                    'traffic_info': request.POST.get('farewell_traffic_info', ''),
                    'tomb_location_name': request.POST.get('tomb_location_name', ''),
                    'tomb_location_address': request.POST.get('tomb_location_address', ''),
                    'tomb_location_area': request.POST.get('tomb_location_area', ''),
                    'tomb_traffic_info': request.POST.get('tomb_traffic_info', ''),
                    'flower_gift_description': request.POST.get('flower_gift_description', ''),
                    'agent_name': request.POST.get('agent_name', ''),
                    'agent_phone': request.POST.get('agent_phone', ''),
                    'background_music': request.POST.get('background_music', ''),
                    'ceremony_items': [],  # 這裡需要添加儀式流程數據
                    'flower_gifts': [],    # 這裡需要添加花禮數據
                    'life_photos': [],     # 這裡需要添加生活照片數據
                    
                    # 添加服務處相關資訊
                    'area_selection': area_selection,
                    'title_icon': 'images/title-icon-2.png' if area_selection in ['1', '3'] else 'images/title-icon.png',
                    'logo_img': 'images/title-icon-2.png' if area_selection in ['1', '3'] else 'images/logo.jpg',
                    'google_map_link': 'https://maps.app.goo.gl/apuxVC9fTTyGRWQL8' if area_selection == '1' else 'https://maps.app.goo.gl/cQEdZ9SVdXe9d4zm7',
                    'company_name': '楊子北區服務處' if area_selection == '1' else '楊子南區服務處' if area_selection == '3' else '楊子佛教禮儀(股)公司'
                },
                'csrf_token': request.META.get('CSRF_COOKIE', '')
            }
            
            # 修改 HTML 內容
            html_content = render_to_string('preview_obituary.html', context)
            
            # 確保 CSRF token 被正確插入
            csrf_token = get_token(request)
            html_content = html_content.replace(
                '</head>',
                f'<meta name="csrf-token" content="{csrf_token}"></head>'
            )
            
            # 添加標題
            title_tag = f'<title>{deceased_name} - 楊子佛教禮儀雲端訃聞系統</title>'
            html_content = html_content.replace('<title>訃聞預覽</title>', title_tag)
            
            # 保存 HTML 文件
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(html_content)

            db.commit()
            print(f"訃聞製作完成，檔案保存在: {file_path}")
            return redirect('obituary_base')
            
        except Exception as e:
            if db:
                db.rollback()
            print(f"訃聞製作過程錯誤: {e}")
            print(f"錯誤詳情: {str(e)}")
            messages.error(request, '訃聞製作失敗，請稍後再試')
            return redirect('create_obituary')
            
        finally:
            if cursor:
                cursor.close()
            if db:
                db.close()
    
    return redirect('create_obituary')

@require_POST
def delete_obituary(request, obituary_id):
    """刪除訃聞"""
    if not request.session.get('is_authenticated'):
        return JsonResponse({'success': False, 'error': '請先登入'})
        
    try:
        db = connection_db()
        if not db:
            return JsonResponse({'success': False, 'error': '資料庫連接失敗'})
            
        cursor = db.cursor(dictionary=True)
        
        try:
            # 獲取訃聞資料和檔案路徑
            cursor.execute("""
                SELECT deceased_name, created_at, file_path 
                FROM obituary 
                WHERE id = %s
            """, [obituary_id])
            obituary_data = cursor.fetchone()
            
            if not obituary_data:
                return JsonResponse({'success': False, 'error': '找不到該訃聞'})
            
            # 刪除靜態目錄中的 HTML 文件
            if obituary_data['file_path']:
                html_path = os.path.join(settings.OBITUARY_FILES_DIR, obituary_data['file_path'])
                try:
                    if os.path.exists(html_path):
                        os.remove(html_path)
                        print(f"已刪除HTML文件: {html_path}")
                except Exception as e:
                    print(f"刪除HTML文件錯誤: {e}")
            
            # 獲取所有相關照片連結
            cursor.execute("""
                SELECT photo_link FROM photos WHERE obituary_id = %s
            """, [obituary_id])
            photos = cursor.fetchall()
            
            # 刪除 Google Drive 中的檔案和資料夾
            service = get_google_drive_service()
            if service:
                try:
                    # 構建資料夾名稱
                    folder_name = f"{obituary_data['deceased_name']}_{obituary_data['created_at'].strftime('%Y%m%d_%H%M%S')}"
                    print(f"尋找資料夾: {folder_name}")
                    
                    # 搜尋資料夾
                    results = service.files().list(
                        q=f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and '{FOLDER_ID}' in parents",
                        fields="files(id, name)"
                    ).execute()
                    
                    folders = results.get('files', [])
                    if folders:
                        folder_id = folders[0]['id']
                        print(f"找到資料夾 ID: {folder_id}")
                        
                        # 刪除資料夾（這會同時刪除資料夾內的所有檔案）
                        service.files().delete(fileId=folder_id).execute()
                        print(f"已刪除資料夾: {folder_name}")
                    else:
                        print("找不到對應的資料夾，嘗試逐個刪除檔案")
                        # 如果找不到資料夾，就逐個刪除檔案
                        for photo in photos:
                            try:
                                file_id = photo['photo_link'].split('/')[-2]
                                service.files().delete(fileId=file_id).execute()
                                print(f"已刪除檔案 ID: {file_id}")
                            except Exception as e:
                                print(f"刪除檔案錯誤: {e}")
                                
                except Exception as e:
                    print(f"Google Drive 操作錯誤: {e}")
            
            # 刪除資料庫中的記錄
            cursor.execute("DELETE FROM photos WHERE obituary_id = %s", [obituary_id])
            cursor.execute("DELETE FROM obituary WHERE id = %s", [obituary_id])
            
            db.commit()
            print("資料庫記錄已刪除")
            return JsonResponse({'success': True})
            
        except Exception as e:
            db.rollback()
            print(f"刪除訃聞錯誤: {e}")
            return JsonResponse({'success': False, 'error': str(e)})
            
        finally:
            cursor.close()
            db.close()
            
    except Exception as e:
        print(f"刪除訃聞錯誤: {e}")
        return JsonResponse({'success': False, 'error': str(e)})

def edit_obituary(request, obituary_id):
    """編輯訃聞"""
    if not request.session.get('is_authenticated'):
        messages.error(request, '請先登入')
        return redirect('login')
        
    db = connection_db()
    if db is None:
        messages.error(request, '系統錯誤，請稍後再試')
        return redirect('obituary_base')
        
    cursor = db.cursor(dictionary=True)
    
    try:
        # 獲取訃聞資料
        cursor.execute("""
            SELECT * FROM obituary WHERE id = %s
        """, [obituary_id])
        obituary_data = cursor.fetchone()
        
        if not obituary_data:
            messages.error(request, '找不到該訃聞')
            return redirect('obituary_base')
            
        # 獲取照片資料
        cursor.execute("""
            SELECT * FROM photos WHERE obituary_id = %s
        """, [obituary_id])
        photos = cursor.fetchall()
        
        # 準備編輯用的資料
        context = {
            'obituary': obituary_data,
            'photos': photos,
            'edit_mode': True  # 標記為輯模式
        }
        
        return render(request, 'obituary_maker.html', context)
        
    except Exception as e:
        print(f"編輯訃聞錯誤: {e}")
        messages.error(request, '無法載入訃聞資料')
        return redirect('obituary_base')
        
    finally:
        cursor.close()
        db.close()

@require_POST
@csrf_exempt
def count_obituary_click(request, obituary_id):
    """記錄訃���點擊次數"""
    try:
        print("\n" + "="*50)
        print(f"收到點擊計數請求")
        print(f"時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"訃聞 ID: {obituary_id}")
        
        # 使用修改後的計數方法
        new_count = ObituaryClick.increment_click(obituary_id)
        
        if new_count is not None:  # 修改判斷條件
            print(f"計數更新成功！")
            print(f"- 訃聞 ID: {obituary_id}")
            print(f"- 新計數: {new_count}")
            print(f"- 更新時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print("="*50 + "\n")
            
            return JsonResponse({
                'success': True,
                'new_count': new_count
            })
        else:
            print(f"計數更新失敗")
            print("="*50 + "\n")
            return JsonResponse({
                'success': False,
                'error': '更新失敗'
            })
    
    except Exception as e:
        print(f"計數更新錯誤！")
        print(f"- 錯誤類型: {type(e).__name__}")
        print(f"- 錯誤訊息: {str(e)}")
        print(f"- 訃聞 ID: {obituary_id}")
        print(f"- 時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*50 + "\n")
        
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

# ... 其他視圖函數保持不變 ...