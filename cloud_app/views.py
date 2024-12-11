from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout
import mysql.connector
from django.conf import settings
from django.template.loader import render_to_string
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import ensure_csrf_cookie, csrf_exempt
from django.middleware.csrf import get_token
from django.urls import reverse
from .models import ObituaryClick
import json
from datetime import datetime
import os
import base64
from PIL import Image
import io

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
            # 先刪除相關的照片
            cursor.execute("DELETE FROM photos WHERE obituary_id = %s", [obituary_id])
            
            # 刪除訃聞記錄
            cursor.execute("DELETE FROM obituary WHERE id = %s", [obituary_id])
            
            db.commit()
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
        # 獲取訃聞基本資料
        cursor.execute("""
            SELECT * FROM obituary WHERE id = %s
        """, [obituary_id])
        obituary_data = cursor.fetchone()
        
        if not obituary_data:
            messages.error(request, '找不到該訃聞')
            return redirect('obituary_base')
            
        # 處理日期格式
        if obituary_data['birth_date']:
            obituary_data['birth_date'] = obituary_data['birth_date'].strftime('%Y-%m-%d')
        if obituary_data['death_date']:
            obituary_data['death_date'] = obituary_data['death_date'].strftime('%Y-%m-%d')
            
        # 獲取各種類型的照片
        photo_queries = {
            'deceased_photo': "SELECT * FROM photos WHERE obituary_id = %s AND photo_type = 'personal' LIMIT 1",
            'obituary_front': "SELECT * FROM photos WHERE obituary_id = %s AND photo_type = 'obituary_front' LIMIT 1",
            'obituary_back': "SELECT * FROM photos WHERE obituary_id = %s AND photo_type = 'obituary_back' LIMIT 1",
            'life_photos': "SELECT * FROM photos WHERE obituary_id = %s AND photo_type = 'life'",
            'flower_gifts': "SELECT * FROM photos WHERE obituary_id = %s AND photo_type = 'flower_gift'"
        }
        
        photos = {}
        for key, query in photo_queries.items():
            cursor.execute(query, [obituary_id])
            if key in ['life_photos', 'flower_gifts']:
                photos[key] = cursor.fetchall()
                print(f"獲取到 {len(photos[key])} 張 {key}")
            else:
                photo = cursor.fetchone()
                if photo and photo.get('photo_link'):
                    print(f"獲取到 {key} 照片")
                    photos[key] = {
                        'id': photo['id'],
                        'data': base64.b64encode(photo['photo_link']).decode('utf-8')
                    }
        
        # 處理儀式流程
        ceremony_process = []
        if obituary_data.get('ceremony_process_list'):
            try:
                ceremony_process = json.loads(obituary_data['ceremony_process_list'])
                print(f"解析儀式流程: {len(ceremony_process)} 項")
            except json.JSONDecodeError:
                print(f"解析儀式流程錯誤")
        
        # 準備編輯用的資料
        context = {
            'edit_mode': True,
            'obituary': {
                'id': obituary_data['id'],
                'service_area': obituary_data['service_area'],
                'deceased_name': obituary_data['deceased_name'],
                'birth_date': obituary_data['birth_date'],
                'death_date': obituary_data['death_date'],
                'hide_birth_date': bool(obituary_data['hide_birth_date']),
                'hide_death_date': bool(obituary_data['hide_death_date']),
                'ceremony_details': obituary_data['ceremony_details'] or '',
                'farewell_location_name': obituary_data.get('location_name', ''),
                'farewell_location_address': obituary_data.get('location_address', ''),
                'farewell_location_area': obituary_data.get('location_area', ''),
                'farewell_traffic_info': obituary_data.get('traffic_info', ''),
                'tomb_location_name': obituary_data.get('tomb_location_name', ''),
                'tomb_location_address': obituary_data.get('tomb_location_address', ''),
                'tomb_location_area': obituary_data.get('tomb_location_area', ''),
                'tomb_traffic_info': obituary_data.get('tomb_traffic_info', ''),
                'flower_gift_description': obituary_data.get('flower_gift_description', ''),
                'agent_name': obituary_data.get('agent_name', ''),
                'agent_phone': obituary_data.get('agent_phone', ''),
                'memorial_video': obituary_data.get('memorial_video', ''),
                'is_draft': bool(obituary_data.get('is_draft', False))
            },
            'photos': photos,
            'ceremony_process': ceremony_process
        }
        
        # 輸出結構化的調試信息
        print("\n編輯資料摘要:")
        print(f"訃聞 ID: {context['obituary']['id']}")
        print(f"往生者: {context['obituary']['deceased_name']}")
        print(f"服務區域: {context['obituary']['service_area']}")
        print(f"照片數量: {len(photos)}")
        print(f"儀式流程: {len(ceremony_process)} 項")
        print("="*50)
        
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
    """記錄訃聞點擊次數並處理物車"""
    try:
        print("\n" + "="*50)
        print(f"收到點擊計數請求")
        print(f"時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"訃聞 ID: {obituary_id}")
        
        # 使用修改後的計數方法
        new_count = ObituaryClick.increment_click(obituary_id)
        
        if new_count > 0:
            print(f"計數更新成功！")
            print(f"- 訃聞 ID: {obituary_id}")
            print(f"- 新計數: {new_count}")
            print(f"- 更新時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print("="*50 + "\n")
            
            # 在 response 中添加清除購物車的標
            return JsonResponse({
                'success': True,
                'new_count': new_count,
                'clear_cart': True,  # 添加清除購物車標記
                'obituary_id': obituary_id  # 添加訃聞 ID
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

@require_POST
def update_obituary(request):
    """上傳訃聞資料到資料庫"""
    try:
        if not request.session.get('is_authenticated'):
            raise Exception("請先登入")
            
        db = connection_db()
        if not db:
            raise Exception("資料庫連接失敗")
            
        cursor = db.cursor(dictionary=True)
        
        try:
            # 設置較長的超時時間和較大的packet大小
            cursor.execute("SET SESSION wait_timeout=300")  # 設置5分鐘超時
            cursor.execute("SET GLOBAL max_allowed_packet=67108864")  # 設置64MB
            
            # 獲取基本資料
            service_area = request.POST.get('area_selection')
            deceased_name = request.POST.get('deceased_name')
            is_draft = request.POST.get('is_draft') == 'true'
            
            # 處理儀式流程列表
            ceremony_times = request.POST.getlist('ceremony_time[]', [])
            ceremony_contents = request.POST.getlist('ceremony_content[]', [])
            ceremony_process = []
            
            for time, content in zip(ceremony_times, ceremony_contents):
                if time and content:
                    ceremony_process.append({
                        'time': time,
                        'content': content
                    })
            
            # 將儀式流程轉換為JSON字串
            ceremony_process_json = json.dumps(ceremony_process, ensure_ascii=False)
            
            print("\n儀式流程資料:")
            print(f"- 數量: {len(ceremony_process)}")
            print(f"- JSON: {ceremony_process_json}")

            # 檢查是否為更新現有訃聞
            obituary_id = request.POST.get('obituary_id')
            
            # 修改照片上傳函數
            def save_photo(file, photo_type, name=None, price=None, orderable=False):
                if file:
                    try:
                        # 重新建立連接以防止超時
                        if not db.is_connected():
                            db.ping(reconnect=True)
                            
                        # 讀取圖片
                        img = Image.open(file)
                        
                        # 轉換為RGB模式（如果是RGBA）
                        if img.mode == 'RGBA':
                            img = img.convert('RGB')
                        
                        # 計算新的尺寸，保持比例
                        max_size = (800, 800)  # 最大尺寸
                        img.thumbnail(max_size, Image.Resampling.LANCZOS)
                        
                        # 保存為JPEG格式，使用BytesIO
                        output = io.BytesIO()
                        img.save(output, format='JPEG', quality=85)  # 降低品質以減少文件大小
                        photo_data = output.getvalue()
                        
                        # 檢查壓縮後的大小
                        if len(photo_data) > 16777215:  # MySQL MEDIUMBLOB的最大大小
                            raise Exception("圖片太大，即使壓縮後仍超過限制")
                        
                        # 插入資料庫
                        cursor.execute("""
                            INSERT INTO photos (
                                obituary_id, photo_type, photo_link, 
                                name, price, orderable, created_at
                            ) VALUES (%s, %s, %s, %s, %s, %s, NOW())
                        """, [
                            obituary_id, photo_type, photo_data,
                            name, price, orderable
                        ])
                        db.commit()  # 每次照片上傳後立即提交
                        
                        print(f"成功上傳照片 ({photo_type}) - 大小: {len(photo_data)} bytes")
                        
                    except Exception as e:
                        print(f"照片上傳錯誤 ({photo_type}): {e}")
                        if "max_allowed_packet" in str(e):
                            raise Exception("圖片大小超過系統限制，請使用較小的圖片")
                        raise

            if obituary_id:
                # 更新現有訃聞的代碼保持不變...
                cursor.execute("""
                    UPDATE obituary SET
                        service_area = %s,
                        deceased_name = %s,
                        birth_date = NULLIF(%s, ''),
                        death_date = NULLIF(%s, ''),
                        ceremony_details = %s,
                        hide_birth_date = %s,
                        hide_death_date = %s,
                        location_name = NULLIF(%s, ''),
                        location_address = NULLIF(%s, ''),
                        location_area = NULLIF(%s, ''),
                        traffic_info = NULLIF(%s, ''),
                        tomb_location_name = NULLIF(%s, ''),
                        tomb_location_address = NULLIF(%s, ''),
                        tomb_location_area = NULLIF(%s, ''),
                        tomb_traffic_info = NULLIF(%s, ''),
                        flower_gift_description = NULLIF(%s, ''),
                        agent_name = NULLIF(%s, ''),
                        agent_phone = NULLIF(%s, ''),
                        memorial_video = NULLIF(%s, ''),
                        background_music = NULLIF(%s, ''),
                        desktop_background = NULLIF(%s, ''),
                        font_style = NULLIF(%s, ''),
                        ceremony_process_list = %s,
                        is_draft = %s,
                        updated_at = NOW()
                    WHERE id = %s
                """, [
                    service_area, deceased_name,
                    request.POST.get('birth_date', ''),
                    request.POST.get('death_date', ''),
                    request.POST.get('ceremony_details', ''),
                    request.POST.get('hide_birth_date') == 'on',
                    request.POST.get('hide_death_date') == 'on',
                    request.POST.get('farewell_location_name', ''),
                    request.POST.get('farewell_location_address', ''),
                    request.POST.get('farewell_location_area', ''),
                    request.POST.get('farewell_traffic_info', ''),
                    request.POST.get('tomb_location_name', ''),
                    request.POST.get('tomb_location_address', ''),
                    request.POST.get('tomb_location_area', ''),
                    request.POST.get('tomb_traffic_info', ''),
                    request.POST.get('flower_gift_description', ''),
                    request.POST.get('agent_name', ''),
                    request.POST.get('agent_phone', ''),
                    request.POST.get('memorial_video', ''),
                    request.POST.get('background_music', ''),
                    request.POST.get('desktop_background', ''),
                    request.POST.get('font_style', ''),
                    ceremony_process_json,
                    is_draft,
                    obituary_id
                ])
                db.commit()  # 提交訃聞更新
            else:
                # 創建新訃聞的代碼保持不變...
                cursor.execute("""
                    INSERT INTO obituary (
                        service_area, deceased_name, created_at,
                        birth_date, death_date, ceremony_details,
                        hide_birth_date, hide_death_date,
                        location_name, location_address, location_area, traffic_info,
                        tomb_location_name, tomb_location_address, tomb_location_area,
                        tomb_traffic_info, flower_gift_description,
                        agent_name, agent_phone, memorial_video,
                        background_music, desktop_background, font_style,
                        ceremony_process_list,
                        is_draft
                    ) VALUES (
                        %s, %s, NOW(),
                        NULLIF(%s, ''), NULLIF(%s, ''), %s,
                        %s, %s,
                        NULLIF(%s, ''), NULLIF(%s, ''), NULLIF(%s, ''), NULLIF(%s, ''),
                        NULLIF(%s, ''), NULLIF(%s, ''), NULLIF(%s, ''),
                        NULLIF(%s, ''), NULLIF(%s, ''),
                        NULLIF(%s, ''), NULLIF(%s, ''), NULLIF(%s, ''),
                        NULLIF(%s, ''), NULLIF(%s, ''), NULLIF(%s, ''),
                        %s,
                        %s
                    )
                """, [
                    service_area, deceased_name,
                    request.POST.get('birth_date', ''),
                    request.POST.get('death_date', ''),
                    request.POST.get('ceremony_details', ''),
                    request.POST.get('hide_birth_date') == 'on',
                    request.POST.get('hide_death_date') == 'on',
                    request.POST.get('farewell_location_name', ''),
                    request.POST.get('farewell_location_address', ''),
                    request.POST.get('farewell_location_area', ''),
                    request.POST.get('farewell_traffic_info', ''),
                    request.POST.get('tomb_location_name', ''),
                    request.POST.get('tomb_location_address', ''),
                    request.POST.get('tomb_location_area', ''),
                    request.POST.get('tomb_traffic_info', ''),
                    request.POST.get('flower_gift_description', ''),
                    request.POST.get('agent_name', ''),
                    request.POST.get('agent_phone', ''),
                    request.POST.get('memorial_video', ''),
                    request.POST.get('background_music', ''),
                    request.POST.get('desktop_background', ''),
                    request.POST.get('font_style', ''),
                    ceremony_process_json,
                    is_draft
                ])
                obituary_id = cursor.lastrowid
                db.commit()  # 提交新訃聞創建

            # 分別處理每種類型的照片上傳
            try:
                # 處理個人照片
                if 'deceased_photo' in request.FILES:
                    print("開始上傳個人照片...")
                    save_photo(request.FILES['deceased_photo'], 'personal')

                # 處理訃聞正反面照片
                if 'obituary_front_image' in request.FILES:
                    print("開始上傳訃聞正面...")
                    save_photo(request.FILES['obituary_front_image'], 'obituary_front')
                if 'obituary_back_image' in request.FILES:
                    print("開始上傳訃聞背面...")
                    save_photo(request.FILES['obituary_back_image'], 'obituary_back')

                # 處理生活照
                for key in request.FILES:
                    if key.startswith('life_photos['):
                        print(f"開始上傳生活照: {key}")
                        save_photo(request.FILES[key], 'life')

                # 處理花禮照片
                for key in request.FILES:
                    if key.startswith('flower_gift_list['):
                        print(f"開始上傳花禮照片: {key}")
                        index = key[key.find('[')+1:key.find(']')]
                        name = request.POST.get(f'flower_gift_list[{index}][name]', '')
                        price = request.POST.get(f'flower_gift_list[{index}][price]', '')
                        orderable = request.POST.get(f'flower_gift_list[{index}][orderable]') == 'on'
                        save_photo(
                            request.FILES[key], 
                            'flower_gift',
                            name=name,
                            price=price,
                            orderable=orderable
                        )
            except Exception as photo_error:
                print(f"照片處理過程中發生錯誤: {photo_error}")
                raise Exception(str(photo_error))
            
            print("\n資料儲存成功!")
            print(f"訃聞 ID: {obituary_id}")
            print("="*50 + "\n")
            
            return JsonResponse({
                'success': True,
                'obituary_id': obituary_id,
                'is_draft': is_draft,
                'redirect_url': reverse('draft_obituaries' if is_draft else 'obituary_base')
            })
            
        except Exception as e:
            db.rollback()
            print(f"\n資料庫操作錯誤: {e}")
            raise
            
        finally:
            cursor.close()
            db.close()
            
    except Exception as e:
        print(f"儲存失敗: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

def home_view(request):
    """首頁視圖"""
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

def login_view(request):
    """登入視圖"""
    print(f"當前session狀態: {dict(request.session)}")

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        next_url = request.POST.get('next', '')
        
        print(f"登入嘗試 - 用戶名: {username}")
        
        db = connection_db()
        if db is None:
            messages.error(request, '系統錯誤，請稍後再試')
            return render(request, 'login.html')
            
        cursor = db.cursor(dictionary=True)
        try:
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
                    u.updated_at,
                    p.permission_type
                FROM users u
                LEFT JOIN permissions p ON u.user_id = p.user_id
                WHERE u.username = %s AND u.password = %s
            """, [username, password])
            
            user_data = cursor.fetchone()
            
            if user_data:
                # 設置 session
                request.session['is_authenticated'] = True
                request.session['user_id'] = user_data['user_id']
                request.session['username'] = user_data['username']
                request.session['realname'] = user_data['realname']
                request.session['permission_level'] = user_data['permission_type']
                
                print(f"登入成功 - 用戶: {username}")
                print(f"權限等級: {user_data['permission_type']}")
                
                if next_url:
                    return redirect(next_url)
                return redirect('home')
            else:
                messages.error(request, '帳號或密碼錯誤')
                return render(request, 'login.html', {'next': next_url})
                
        except mysql.connector.Error as err:
            print(f"數據庫錯誤: {err}")
            messages.error(request, '系統錯誤，請稍後再試')
            return render(request, 'login.html', {'next': next_url})
            
        finally:
            cursor.close()
            db.close()
    
    return render(request, 'login.html')

def logout_view(request):
    """登出視圖"""
    logout_type = request.GET.get('type', 'manual')
    
    request.session.flush()
    logout(request)
    
    if request.method == 'POST' and logout_type == 'auto':
        return JsonResponse({'success': True, 'message': '自動登出成功'})
    else:
        return redirect('home')

def obituary_base(request):
    """訃聞列表頁面"""
    if not request.session.get('is_authenticated'):
        messages.error(request, '請先登入')
        return redirect('login')
        
    db = connection_db()
    if db is None:
        messages.error(request, '系統錯誤，請稍後再試')
        return redirect('home')
        
    cursor = db.cursor(dictionary=True)
    try:
        # 只獲取非草稿的訃聞
        cursor.execute("""
            SELECT * FROM obituary 
            WHERE is_draft = 0 
            ORDER BY created_at DESC
        """)
        obituaries = cursor.fetchall()
        
        return render(request, 'obituary_base.html', {'obituaries': obituaries})
        
    except Exception as e:
        print(f"獲取訃聞列表錯誤: {e}")
        messages.error(request, '系統錯誤，請稍後再試')
        return redirect('home')
        
    finally:
        cursor.close()
        db.close()

def create_obituary(request):
    """創建訃聞"""
    return render(request, 'obituary_maker.html')

def search_obituary(request):
    """搜尋訃聞"""
    return render(request, 'search_obituary.html')

def buy_car(request):
    """購物車頁面"""
    return render(request, 'buy_car.html')

def case_management(request):
    """案件管理頁面"""
    if not request.session.get('is_authenticated'):
        return redirect('login')
    return render(request, 'case_management.html')

def preview_obituary(request):
    """預覽訃聞"""
    if request.method == 'POST':
        try:
            # 检查是否登入
            if not request.session.get('is_authenticated'):
                messages.error(request, '請先登入')
                return redirect('login')
            
            # 獲取服務處選擇
            area_selection = request.POST.get('area_selection')
            
            # 獲取表單輸入
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
                'company_name': '楊子北服務處' if area_selection == '1' else '楊子南區務處' if area_selection == '3' else '楊子佛教禮儀(股)公司'
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

            # 修改音樂路徑處理
            background_music = request.POST.get('background_music', '')
            if background_music:
                # 移除重複的 static/audio 路徑
                background_music = background_music.replace('/static/audio/', '')
                preview_data['background_music'] = background_music
            
            return render(request, 'preview_obituary.html', {'data': preview_data})
            
        except Exception as e:
            print(f"預覽錯誤: {e}")
            messages.error(request, '預覽失敗，請稍後再試')
            return redirect('create_obituary')
    
    return redirect('create_obituary')

def register(request):
    """職員註冊頁面"""
    print(f"訪問註冊頁")  # 调试信息
    print(f"當前用戶權限: {request.session.get('permission_level')}")  # 调试信息
    print(f"Session 數據: {dict(request.session)}")  # 调试信息
    
    # 檢查是否登入
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
            
            # 入權限資料到 permissions 表
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
                姓名: {realname}
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
            
            # 直接返回當前頁面，保留消息
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
    """切換用戶啟用狀態"""
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
        
        # 切換狀態
        new_status = 0 if current_status else 1
        cursor.execute("""
            UPDATE users 
            SET is_active = %s, updated_at = NOW()
            WHERE user_id = %s
        """, [new_status, user_id])
        
        db.commit()
        messages.success(request, '用戶狀態已更新')
        
    except Exception as e:
        db.rollback()
        print(f"切換用戶狀態誤: {e}")
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
        # 先刪除權限記錄
        cursor.execute("DELETE FROM permissions WHERE user_id = %s", [user_id])
        # 再刪除用戶記錄
        cursor.execute("DELETE FROM users WHERE user_id = %s", [user_id])
        
        db.commit()
        messages.success(request, '用戶已刪除')
        
    except Exception as e:
        db.rollback()
        print(f"刪除用戶錯誤: {e}")
        messages.error(request, '刪除失敗，請稍後再試')
        
    finally:
        cursor.close()
        db.close()
        
    return redirect('preview_employee')

def make_obituary(request, obituary_id=None):
    """製作訃聞上傳片"""
    if request.method == 'POST':
        try:
            # 確保目錄存在
            obituaries_dir = os.path.join(settings.STATICFILES_DIRS[0], 'obituaries')
            if not os.path.exists(obituaries_dir):
                try:
                    os.makedirs(obituaries_dir)
                    print(f"創建目錄: {obituaries_dir}")
                except Exception as e:
                    print(f"創建目錄失敗: {e}")
                    raise Exception(f"無法創建必要的目錄: {str(e)}")
            
            # 檢查目錄寫入權限
            if not os.access(obituaries_dir, os.W_OK):
                raise Exception(f"沒有寫入權限: {obituaries_dir}")
                
            print("\n" + "="*50)
            print("開始處理訃聞製作請求...")
            current_time = datetime.now()
            print(f"時間: {current_time.strftime('%Y-%m-%d %H:%M:%S')}")
            
            # 生成時間戳
            import time as time_module  # 重命名避免衝突
            timestamp = int(time_module.time())
            
            db = connection_db()
            if not db:
                raise Exception("料庫連接失敗")
                
            cursor = db.cursor(dictionary=True)
            
            try:
                # 獲基本資料
                service_area = request.POST.get('area_selection')
                deceased_name = request.POST.get('deceased_name')
                
                print("\n基本資料:")
                print(f"- 服務區域: {service_area}")
                print(f"- 往生者姓名: {deceased_name}")
                
                # 生成 HTML 檔案名稱
                file_name = f"obituary_{timestamp}.html"
                
                # 準備模板資料
                template_data = {
                    'deceased_name': deceased_name,
                    'service_area': service_area,
                    # ... 其他資料 ...
                }
                
                # 生成 HTML 內容
                html_content = render_to_string('obituary_template.html', template_data)
                
                # 保存 HTML 檔案
                file_path = os.path.join(obituaries_dir, file_name)
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(html_content)
                
                # 更新資料庫
                cursor.execute("""
                    UPDATE obituary 
                    SET file_path = %s 
                    WHERE id = %s
                """, [file_name, obituary_id])
                
                db.commit()
                print(f"訃聞製作完成: {file_path}")
                
            except Exception as e:
                db.rollback()
                print(f"\n資料庫操作錯誤: {e}")
                raise
                
            finally:
                cursor.close()
                db.close()
                
        except Exception as e:
            print(f"\n製作失敗: {e}")
            print("="*50 + "\n")
            messages.error(request, f'訃聞製作失敗：{str(e)}')
            return redirect('create_obituary')
            
    return redirect('create_obituary')

def view_obituary(request, obituary_id):
    """查看訃聞"""
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
        
        # 準備模板資料
        context = {
            'obituary': obituary_data,
            'photos': photos
        }
        
        return render(request, 'obituary_page.html', context)
        
    except Exception as e:
        print(f"查看訃聞錯誤: {e}")
        messages.error(request, '無法載入訃聞')
        return redirect('obituary_base')
        
    finally:
        cursor.close()
        db.close()

def extract_youtube_id(url):
    """從 YouTube URL 提取影片 ID"""
    if not url:
        return None
        
    import re
    
    # 處理 YouTube URL 格式
    patterns = [
        r'(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/)([^&\?\/]+)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    
    return None

# 添加新的視圖函數處理草稿訃聞
def draft_obituaries(request):
    """顯示草稿訃聞列表"""
    if not request.session.get('is_authenticated'):
        messages.error(request, '請先登入')
        return redirect('login')
        
    db = connection_db()
    if db is None:
        messages.error(request, '系統錯誤，請稍後再試')
        return redirect('obituary_base')
        
    cursor = db.cursor(dictionary=True)
    try:
        # 獲取所有草稿訃聞
        cursor.execute("""
            SELECT * FROM obituary 
            WHERE is_draft = 1 
            ORDER BY created_at DESC
        """)
        drafts = cursor.fetchall()
        
        return render(request, 'draft_obituaries.html', {'drafts': drafts})
        
    except Exception as e:
        print(f"獲取草稿訃聞錯誤: {e}")
        messages.error(request, '無法載入草稿訃聞')
        return redirect('obituary_base')
        
    finally:
        cursor.close()
        db.close()

def edit_draft(request, obituary_id):
    """編輯草稿訃聞"""
    if not request.session.get('is_authenticated'):
        messages.error(request, '請先登入')
        return redirect('login')
        
    try:
        db = connection_db()
        if not db:
            raise Exception("資料庫連接失敗")
            
        cursor = db.cursor(dictionary=True)
        
        # 獲取草稿訃聞資料
        cursor.execute("""
            SELECT * FROM obituary 
            WHERE id = %s AND is_draft = 1
        """, [obituary_id])
        
        draft_data = cursor.fetchone()
        if not draft_data:
            messages.error(request, '找不到該草稿訃聞')
            return redirect('draft_obituaries')
            
        # 處理日期格式
        if draft_data['birth_date']:
            draft_data['birth_date'] = draft_data['birth_date'].strftime('%Y-%m-%d')
        if draft_data['death_date']:
            draft_data['death_date'] = draft_data['death_date'].strftime('%Y-%m-%d')
            
        # 獲取相關照片
        photo_queries = {
            'deceased_photo': "SELECT * FROM photos WHERE obituary_id = %s AND photo_type = 'personal' LIMIT 1",
            'obituary_front': "SELECT * FROM photos WHERE obituary_id = %s AND photo_type = 'obituary_front' LIMIT 1",
            'obituary_back': "SELECT * FROM photos WHERE obituary_id = %s AND photo_type = 'obituary_back' LIMIT 1",
            'life_photos': "SELECT * FROM photos WHERE obituary_id = %s AND photo_type = 'life'",
            'flower_gifts': "SELECT * FROM photos WHERE obituary_id = %s AND photo_type = 'flower_gift'"
        }
        
        photos = {}
        for key, query in photo_queries.items():
            cursor.execute(query, [obituary_id])
            if key in ['life_photos', 'flower_gifts']:
                photos[key] = cursor.fetchall()
            else:
                photo = cursor.fetchone()
                if photo and photo.get('photo_link'):
                    photos[key] = {
                        'id': photo['id'],
                        'data': base64.b64encode(photo['photo_link']).decode('utf-8')
                    }
        
        # 處理儀式流程
        ceremony_process = []
        if draft_data.get('ceremony_process_list'):
            try:
                ceremony_process = json.loads(draft_data['ceremony_process_list'])
            except json.JSONDecodeError:
                print(f"解析儀式流程錯誤")
        
        # 準備模板資料
        context = {
            'edit_mode': True,
            'draft': draft_data,
            'photos': photos,
            'ceremony_process': ceremony_process
        }
        
        print(f"載入草稿 ID: {draft_data['id']}")
        return render(request, 'draft_maker.html', context)
        
    except Exception as e:
        print(f"編輯草稿錯誤: {e}")
        messages.error(request, '無法載入草稿')
        return redirect('draft_obituaries')
        
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'db' in locals():
            db.close()

# ... 其他視圖函數 ...