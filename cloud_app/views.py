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
        
        print(f"登入嘗試 - 用戶名: {username}")  # 调试信息
        
        db = connection_db()
        if db is None:
            messages.error(request, '系統錯誤，請稍後再試')
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
        'permission_level': permission_level  # 确保传递权限等级到模板
    }
    return render(request, 'base.html', context)

def logout_view(request):
    """登出用戶"""
    request.session.flush()
    logout(request)
    return redirect('home')

def obituary_base(request):
    """訃聞製作基礎頁面"""
    print(f"訪問訃聞頁面")  # 调试信息
    print(f"obituary_base session狀態: {dict(request.session)}")  # 调试信息
    
    # 检查是否已登录
    if not request.session.get('is_authenticated'):
        return redirect('login')
    
    return render(request, 'obituary_base.html')

def create_obituary(request):
    """創建新訃聞"""
    # if not request.session.get('is_authenticated'):
    #     return redirect('login')
    return render(request, 'obituary_maker.html')

def search_obituary(request):
    """搜尋訃聞"""
    # if not request.session.get('is_authenticated'):
    #     return redirect('login')
    return render(request, 'search_obituary.html')

def preview_obituary(request):
    """預覽訃聞"""
    if request.method == 'POST':
        # 获取 YouTube URL 并处理
        memorial_video = request.POST.get('memorial_video', '')
        video_id = None
        
        if memorial_video:
            if 'youtu.be/' in memorial_video:
                video_id = memorial_video.split('youtu.be/')[-1]
            elif 'youtube.com/watch?v=' in memorial_video:
                video_id = memorial_video.split('watch?v=')[-1]
            elif 'youtube.com/embed/' in memorial_video:
                video_id = memorial_video.split('embed/')[-1]
            else:
                video_id = memorial_video  # 假设直接输入的是视频 ID
                
            # 移除任何额外的参数
            if '&' in video_id:
                video_id = video_id.split('&')[0]
                
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
            'ceremony_times': [],
            'flower_gifts': [],
            'life_photos': [],
            'memorial_video': video_id,  # 使用处理后的视频 ID
        }
        
        # 打印调试信息
        print(f"Original URL: {memorial_video}")
        print(f"Video ID: {video_id}")
        
        # 处理仪式时间
        ceremony_times = request.POST.getlist('ceremony_time[]', [])
        ceremony_contents = request.POST.getlist('ceremony_content[]', [])
        preview_data['ceremony_times'] = list(zip(ceremony_times, ceremony_contents))

        # 处理上传的图片
        if 'deceased_photo' in request.FILES:
            file = request.FILES['deceased_photo']
            import base64
            preview_data['deceased_photo'] = f"data:image/{file.content_type.split('/')[-1]};base64,{base64.b64encode(file.read()).decode()}"
            
        if 'obituary_front_image' in request.FILES:
            file = request.FILES['obituary_front_image']
            import base64
            preview_data['obituary_front_image'] = f"data:image/{file.content_type.split('/')[-1]};base64,{base64.b64encode(file.read()).decode()}"
            
        if 'obituary_back_image' in request.FILES:
            file = request.FILES['obituary_back_image']
            import base64
            preview_data['obituary_back_image'] = f"data:image/{file.content_type.split('/')[-1]};base64,{base64.b64encode(file.read()).decode()}"

        # 处理生活照片
        for key in request.FILES:
            if key.startswith('life_photos['):
                file = request.FILES[key]
                import base64
                preview_data['life_photos'].append(
                    f"data:image/{file.content_type.split('/')[-1]};base64,{base64.b64encode(file.read()).decode()}"
                )

        # 修改处理花礼的部分
        flower_gifts = []
        for key in request.FILES:
            if key.startswith('flower_gift_list['):
                index = key[key.find('[')+1:key.find(']')]
                name = request.POST.get(f'flower_gift_list[{index}][name]', '')
                price = request.POST.get(f'flower_gift_list[{index}][price]', '')
                orderable = request.POST.get(f'flower_gift_list[{index}][orderable]') == 'on'  # 获取可订购状态
                file = request.FILES[key]
                import base64
                image = f"data:image/{file.content_type.split('/')[-1]};base64,{base64.b64encode(file.read()).decode()}"
                flower_gifts.append({
                    'name': name,
                    'price': price,
                    'image': image,
                    'orderable': orderable  # 添加可订购状态到数据中
                })
        preview_data['flower_gifts'] = flower_gifts

        return render(request, 'preview_obituary.html', {'data': preview_data})
    
    return redirect('create_obituary')

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
    print(f"當前用戶權限: {request.session.get('permission_level')}")  # 调试信息
    print(f"Session 數據: {dict(request.session)}")  # 调试信息
    
    # 檢查是否已登入
    if not request.session.get('is_authenticated'):
        messages.error(request, '請先登入')
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
            messages.error(request, '系統錯誤，請稍後再試')
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
                電子郵件：{email}
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
            # 關閉資料庫連接
            cursor.close()
            db.close()
    
    # GET 請求
    return render(request, 'register.html', {'session': request.session})

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
        messages.error(request, '系統錯誤，請稍後再試')
        return redirect('home')
        
    finally:
        cursor.close()
        db.close()

def toggle_active(request, user_id):
    """變更用戶啟用狀態"""
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
        print(f"數據庫錯誤: {err}")
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
        messages.error(request, '刪除失敗，請稍後再試')
        
    finally:
        cursor.close()
        db.close()
    
    return redirect('preview_employee')

# ... 其他視圖函數保持不變 ...