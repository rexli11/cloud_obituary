from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout
import mysql.connector
from django.conf import settings
from django.template.loader import render_to_string
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_http_methods
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
    try:
        print("\n" + "="*50)
        print("開始載入草稿編輯資料...")
        print(f"時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"訃聞 ID: {obituary_id}")
        
        if not request.session.get('is_authenticated'):
            print("錯誤: 使用者未登入")
            messages.error(request, '請先登入')
            return redirect('login')
            
        db = connection_db()
        if not db:
            print("錯誤: 資料庫連接失敗")
            raise Exception("資料庫連接失敗")
            
        cursor = db.cursor(dictionary=True)
        
        try:
            # 獲取訃聞基本資料
            cursor.execute("""
                SELECT * FROM obituary WHERE id = %s
            """, [obituary_id])
            obituary_data = cursor.fetchone()
            
            if not obituary_data:
                print("錯誤: 找不到訃聞")
                messages.error(request, '找不到該訃聞')
                return redirect('obituary_base')
                
            print(f"\n基本資料:")
            print(f"- 往生者: {obituary_data['deceased_name']}")
            print(f"- 建立時間: {obituary_data['created_at']}")
            
            # 獲取各種類型的照片
            photo_queries = {
                'deceased_photo': "SELECT * FROM photos WHERE obituary_id = %s AND photo_type = 'personal' LIMIT 1",
                'obituary_front': "SELECT * FROM photos WHERE obituary_id = %s AND photo_type = 'obituary_front' LIMIT 1",
                'obituary_back': "SELECT * FROM photos WHERE obituary_id = %s AND photo_type = 'obituary_back' LIMIT 1",
                'life_photos': "SELECT * FROM photos WHERE obituary_id = %s AND photo_type = 'life'",
                'flower_gifts': "SELECT * FROM photos WHERE obituary_id = %s AND photo_type = 'flower_gift'"
            }
            
            print("\n照片資料:")
            photos = {}
            for key, query in photo_queries.items():
                cursor.execute(query, [obituary_id])
                if key in ['life_photos', 'flower_gifts']:
                    photos[key] = []
                    results = cursor.fetchall()
                    print(f"- {key}:")
                    for idx, photo in enumerate(results, 1):
                        if photo.get('photo_link'):
                            photo_data = {
                                'id': photo['id'],
                                'photo_link': base64.b64encode(photo['photo_link']).decode('utf-8'),
                                'name': photo.get('name', ''),
                                'price': photo.get('price', ''),
                                'orderable': photo.get('orderable', False),
                                'file_name': photo.get('file_name', '未命名檔案'),
                                'created_at': photo.get('created_at').strftime('%Y-%m-%d %H:%M:%S')
                            }
                            photos[key].append(photo_data)
                            print(f"  {idx}. ID: {photo['id']}")
                            print(f"     檔案名稱: {photo.get('file_name', '未命名檔案')}")
                            print(f"     建立時間: {photo.get('created_at').strftime('%Y-%m-%d %H:%M:%S')}")
                            if key == 'flower_gifts':
                                print(f"     名稱: {photo.get('name', '')}")
                                print(f"     價格: {photo.get('price', '')}")
                                print(f"     可訂購: {'是' if photo.get('orderable') else '否'}")
                else:
                    photo = cursor.fetchone()
                    print(f"- {key}:")
                    if photo and photo.get('photo_link'):
                        photos[key] = {
                            'id': photo['id'],
                            'data': base64.b64encode(photo['photo_link']).decode('utf-8'),
                            'name': photo.get('file_name', '未命名檔案'),
                            'created_at': photo.get('created_at').strftime('%Y-%m-%d %H:%M:%S')
                        }
                        print(f"  ID: {photo['id']}")
                        print(f"  檔案名稱: {photo.get('file_name', '未命名檔案')}")
                        print(f"  建立時間: {photo.get('created_at').strftime('%Y-%m-%d %H:%M:%S')}")
                    else:
                        print("  未上傳")

            # 處理日期格式
            if obituary_data['birth_date']:
                obituary_data['birth_date'] = obituary_data['birth_date'].strftime('%Y-%m-%d')
            if obituary_data['death_date']:
                obituary_data['death_date'] = obituary_data['death_date'].strftime('%Y-%m-%d')
            
            # 處理儀式流程
            ceremony_process = []
            if obituary_data.get('ceremony_process_list'):
                try:
                    ceremony_process = json.loads(obituary_data['ceremony_process_list'])
                    print(f"\n儀式流程: {len(ceremony_process)} 項")
                except json.JSONDecodeError:
                    print(f"\n解析儀式流程錯誤")
            
            # 準備模板資料
            context = {
                'edit_mode': True,
                'obituary': obituary_data,
                'photos': photos,
                'ceremony_process': ceremony_process
            }
            
            print("\n編輯資料摘要:")
            print(f"訃聞 ID: {obituary_data['id']}")
            print(f"往生者姓名: {obituary_data['deceased_name']}")
            print(f"服務區域: {obituary_data['service_area']}")
            print(f"照片數量: {len(photos)}")
            print(f"儀式流程: {len(ceremony_process)} 項")
            print("="*50 + "\n")
            
            return render(request, 'draft_maker.html', context)
            
        except Exception as e:
            print(f"編輯訃聞錯誤: {e}")
            raise
            
        finally:
            cursor.close()
            db.close()
            
    except Exception as e:
        print(f"載入訃聞失敗: {e}")
        messages.error(request, '無法載入訃聞資料')
        return redirect('obituary_base')

def preview_draft(request, obituary_id):
    """預覽草稿訃聞"""
    try:
        print("\n" + "="*50)
        print("開始載入草稿預覽...")
        print(f"時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"訃聞 ID: {obituary_id}")
        
        db = connection_db()
        if not db:
            raise Exception("資料庫連接失敗")
            
        cursor = db.cursor(dictionary=True)
        
        try:
            # 獲取草稿訃聞資料
            cursor.execute("""
                SELECT * FROM obituary 
                WHERE id = %s AND is_draft = 1
            """, [obituary_id])
            
            obituary_data = cursor.fetchone()
            if not obituary_data:
                raise Exception("找不到草稿訃聞")
            
            # 處理儀式流程
            ceremony_process = []
            if obituary_data.get('ceremony_process_list'):
                try:
                    ceremony_process = json.loads(obituary_data['ceremony_process_list'])
                    print(f"\n儀式流程解析成功:")
                    for idx, process in enumerate(ceremony_process, 1):
                        print(f"  {idx}. 時間: {process.get('time', '')}")
                        print(f"     內容: {process.get('content', '')}")
                except json.JSONDecodeError as e:
                    print(f"解析儀式流程錯誤: {e}")
                    ceremony_process = []
            
            # 獲取照片資料
            photo_queries = {
                'deceased_photo': "SELECT * FROM photos WHERE obituary_id = %s AND photo_type = 'personal' LIMIT 1",
                'obituary_front': "SELECT * FROM photos WHERE obituary_id = %s AND photo_type = 'obituary_front' LIMIT 1",
                'obituary_back': "SELECT * FROM photos WHERE obituary_id = %s AND photo_type = 'obituary_back' LIMIT 1",
                'life_photos': "SELECT * FROM photos WHERE obituary_id = %s AND photo_type = 'life'",
                'flower_gifts': "SELECT * FROM photos WHERE obituary_id = %s AND photo_type = 'flower_gift'"
            }
            
            preview_data = {
                'deceased_name': obituary_data['deceased_name'],
                'birth_date': obituary_data['birth_date'],
                'death_date': obituary_data['death_date'],
                'hide_birth_date': obituary_data['hide_birth_date'],
                'hide_death_date': obituary_data['hide_death_date'],
                'ceremony_details': obituary_data['ceremony_details'],
                'location_name': obituary_data.get('location_name', ''),
                'location_address': obituary_data.get('location_address', ''),
                'location_area': obituary_data.get('location_area', ''),
                'traffic_info': obituary_data.get('traffic_info', ''),
                'tomb_location_name': obituary_data.get('tomb_location_name', ''),
                'tomb_location_address': obituary_data.get('tomb_location_address', ''),
                'tomb_location_area': obituary_data.get('tomb_location_area', ''),
                'tomb_traffic_info': obituary_data.get('tomb_traffic_info', ''),
                'agent_name': obituary_data.get('agent_name', ''),
                'agent_phone': obituary_data.get('agent_phone', ''),
                'desktop_background': obituary_data.get('desktop_background', ''),
                'font_style': obituary_data.get('font_style', ''),
                'life_photos': [],
                'flower_gifts': [],
                'ceremony_process': ceremony_process  # 添加儀式流程
            }
            
            # 處理照片
            for key, query in photo_queries.items():
                cursor.execute(query, [obituary_id])
                if key in ['life_photos', 'flower_gifts']:
                    photos = []
                    for photo in cursor.fetchall():
                        if photo.get('photo_link'):
                            photo_data = {
                                'image': f"data:image/jpeg;base64,{base64.b64encode(photo['photo_link']).decode()}",
                                'name': photo.get('name', ''),
                                'price': photo.get('price', ''),
                                'orderable': photo.get('orderable', False)
                            }
                            photos.append(photo_data)
                    preview_data[key] = photos
                else:
                    photo = cursor.fetchone()
                    if photo and photo.get('photo_link'):
                        preview_data[key] = f"data:image/jpeg;base64,{base64.b64encode(photo['photo_link']).decode()}"
            
            print("\n預覽資料準備成!")
            print(f"- 往生者: {preview_data['deceased_name']}")
            print(f"- 照片數量: {len(preview_data.get('life_photos', []))}")
            print(f"- 花禮數量: {len(preview_data.get('flower_gifts', []))}")
            print(f"- 儀式流程: {len(preview_data.get('ceremony_process', []))}")
            print("="*50 + "\n")
            
            return render(request, 'draft_preview.html', {'data': preview_data})
            
        except Exception as e:
            print(f"預覽資料處理錯誤: {e}")
            raise
            
        finally:
            cursor.close()
            db.close()
            
    except Exception as e:
        print(f"預覽載入失敗: {e}")
        messages.error(request, '無法載入預覽')
        return redirect('draft_obituaries')

@require_POST
@csrf_exempt
def count_obituary_click(request, obituary_id):
    """記錄訃聞點擊次數"""
    try:
        # 檢查請求來源
        referer = request.META.get('HTTP_REFERER', '')
        # 只有從 obituary_base.html 或 obituary_list.html 點擊訪問時才計數
        if not ('obituary/' in referer or 'obituary/list/' in referer):
            return JsonResponse({
                'success': False,
                'error': 'Invalid request source'
            })

        # 檢查是否是實際點擊
        click_type = request.headers.get('X-Click-Type')
        if click_type != 'actual_click':
            return JsonResponse({
                'success': False,
                'error': 'Not an actual click'
            })

        print("\n" + "="*50)
        print(f"開始處理點擊計��請求")
        print(f"時��: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"訃聞 ID: {obituary_id}")
        print(f"請求來源: {referer}")
        print(f"點擊類型: {click_type}")
        
        db = connection_db()
        if not db:
            raise Exception("資料庫連接失敗")
            
        cursor = db.cursor(dictionary=True)
        
        try:
            # 更新點擊次數
            cursor.execute("""
                UPDATE obituary 
                SET view_count = COALESCE(view_count, 0) + 1 
                WHERE id = %s
            """, [obituary_id])
            
            # 獲取更新後的點擊次數
            cursor.execute("""
                SELECT view_count 
                FROM obituary 
                WHERE id = %s
            """, [obituary_id])
            
            result = cursor.fetchone()
            new_count = result['view_count'] if result else 0
            
            db.commit()
            
            print(f"點擊計數更新成功！")
            print(f"- 訃聞 ID: {obituary_id}")
            print(f"- 新點擊次數: {new_count}")
            print(f"- 更新時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print("="*50 + "\n")
            
            return JsonResponse({
                'success': True,
                'new_count': new_count
            })
            
        except Exception as e:
            db.rollback()
            print(f"點擊計數更新錯誤: {e}")
            raise
            
        finally:
            cursor.close()
            db.close()
            
    except Exception as e:
        print(f"點擊計數處理失敗: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@require_http_methods(["GET", "POST"])
def update_obituary(request):
    """更新訃聞資料"""
    try:
        print("\n" + "="*50)
        print("開始更新訃聞資料...")
        print(f"時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        db = connection_db()
        if not db:
            return JsonResponse({'success': False, 'error': '資料庫連接失敗'})
            
        cursor = db.cursor(dictionary=True)
        
        def compress_image(image_file, max_size=1024*1024):  # 預設最大1MB
            """壓縮圖片"""
            try:
                # 讀取圖片
                img = Image.open(image_file)
                
                # 保持原始圖片格式
                format = img.format
                
                # 計算目標尺寸
                width, height = img.size
                while (width * height * 3) > max_size:  # 3 bytes per pixel (RGB)
                    width = int(width * 0.9)  # 每次縮小10%
                    height = int(height * 0.9)
                
                # 調整圖片大小
                img = img.resize((width, height), Image.Resampling.LANCZOS)
                
                # 轉換為 bytes
                output = io.BytesIO()
                img.save(output, format=format, quality=85, optimize=True)
                compressed_image = output.getvalue()
                
                return compressed_image
            except Exception as e:
                print(f"圖片壓縮錯誤: {e}")
                return image_file.read()

        try:
            # 定義照片類型對應
            photo_types = {
                'deceased_photo': 'personal',
                'obituary_front_image': 'obituary_front',
                'obituary_back_image': 'obituary_back'
            }
            
            obituary_id = request.POST.get('obituary_id')
            is_draft = request.POST.get('is_draft', 'false').lower() == 'true'
            
            # 處理儀式流程列表
            ceremony_times = request.POST.getlist('ceremony_time[]')
            ceremony_contents = request.POST.getlist('ceremony_content[]')
            ceremony_process_list = []
            
            print("\n處理儀式流程...")
            for time, content in zip(ceremony_times, ceremony_contents):
                if content:  # 只添加非空的項目
                    ceremony_process_list.append({
                        'time': time,
                        'content': content
                    })
                    print(f"- 流程: {time} - {content}")

            # 修改獲取 is_public 的方式
            is_public = request.POST.get('is_public_hidden')  # 從隱藏欄位獲取值
            if is_public is None:  # 如果隱藏欄位沒有值，則從選擇框獲取
                is_public = request.POST.get('is_public', '0')
            
            # 準備更新的數據
            update_data = {
                'service_area': request.POST.get('area_selection'),
                'deceased_name': request.POST.get('deceased_name'),
                'birth_date': request.POST.get('birth_date'),
                'death_date': request.POST.get('death_date'),
                'hide_birth_date': request.POST.get('hide_birth_date') == 'on',
                'hide_death_date': request.POST.get('hide_death_date') == 'on',
                'ceremony_details': request.POST.get('ceremony_details'),
                'background_music': request.POST.get('background_music', '').replace('static/audio/', ''),
                'desktop_background': request.POST.get('desktop_background'),
                'font_style': request.POST.get('font_style'),
                'is_draft': is_draft,
                'agent_name': request.POST.get('agent_name'),
                'agent_phone': request.POST.get('agent_phone'),
                'memorial_video': request.POST.get('memorial_video'),
                'flower_gift_description': request.POST.get('flower_gift_description'),
                'location_name': request.POST.get('farewell_location_name'),
                'location_address': request.POST.get('farewell_location_address'),
                'location_area': request.POST.get('farewell_location_area'),
                'traffic_info': request.POST.get('farewell_traffic_info'),
                'tomb_location_name': request.POST.get('tomb_location_name'),
                'tomb_location_address': request.POST.get('tomb_location_address'),
                'tomb_location_area': request.POST.get('tomb_location_area'),
                'tomb_traffic_info': request.POST.get('tomb_traffic_info'),
                'ceremony_process_list': json.dumps(ceremony_process_list),
                'is_public': int(is_public) if is_public else 0  # 確保轉換為整數
            }

            # 打印基本資料
            print("\n基本資料:")
            print(f"- 服務區域: {update_data['service_area']}")
            print(f"- 是否公開: {update_data['is_public']}")
            print(f"- 往生者: {update_data['deceased_name']}")
            print(f"- 出生日期: {update_data['birth_date']}")
            print(f"- 死亡日期: {update_data['death_date']}")
            print(f"- 隱藏出生日期: {update_data['hide_birth_date']}")
            print(f"- 隱藏死亡日期: {update_data['hide_death_date']}")

            print("\n聯絡資訊:")
            print(f"- 承辦人: {update_data['agent_name']}")
            print(f"- 聯絡電話: {update_data['agent_phone']}")

            print("\n告別式資訊:")
            print(f"- 地點名稱: {update_data['location_name']}")
            print(f"- 地址: {update_data['location_address']}")
            print(f"- 區域: {update_data['location_area']}")
            print(f"- 交通資訊: {update_data['traffic_info']}")

            print("\n靈堂資訊:")
            print(f"- 地點名稱: {update_data['tomb_location_name']}")
            print(f"- 地址: {update_data['tomb_location_address']}")
            print(f"- 區域: {update_data['tomb_location_area']}")
            print(f"- 交通資訊: {update_data['tomb_traffic_info']}")

            print("\n其他資訊:")
            print(f"- 儀式細節: {update_data['ceremony_details']}")
            print(f"- 背景音樂: {update_data['background_music']}")
            print(f"- 桌面背景: {update_data['desktop_background']}")
            print(f"- 字體樣式: {update_data['font_style']}")
            print(f"- 追思影片: {update_data['memorial_video']}")
            print(f"- 花禮說明: {update_data['flower_gift_description']}")

            # 構建 SQL 更新語句
            if obituary_id:
                sql = """
                    UPDATE obituary SET 
                        service_area = %(service_area)s,
                        deceased_name = %(deceased_name)s,
                        birth_date = %(birth_date)s,
                        death_date = %(death_date)s,
                        hide_birth_date = %(hide_birth_date)s,
                        hide_death_date = %(hide_death_date)s,
                        ceremony_details = %(ceremony_details)s,
                        background_music = %(background_music)s,
                        desktop_background = %(desktop_background)s,
                        font_style = %(font_style)s,
                        is_draft = %(is_draft)s,
                        agent_name = %(agent_name)s,
                        agent_phone = %(agent_phone)s,
                        memorial_video = %(memorial_video)s,
                        flower_gift_description = %(flower_gift_description)s,
                        location_name = %(location_name)s,
                        location_address = %(location_address)s,
                        location_area = %(location_area)s,
                        traffic_info = %(traffic_info)s,
                        tomb_location_name = %(tomb_location_name)s,
                        tomb_location_address = %(tomb_location_address)s,
                        tomb_location_area = %(tomb_location_area)s,
                        tomb_traffic_info = %(tomb_traffic_info)s,
                        ceremony_process_list = %(ceremony_process_list)s,
                        is_public = %(is_public)s
                    WHERE id = %(obituary_id)s
                """
                update_data['obituary_id'] = obituary_id
            else:
                sql = """
                    INSERT INTO obituary (
                        service_area, deceased_name, birth_date, death_date,
                        hide_birth_date, hide_death_date, ceremony_details,
                        background_music, desktop_background, font_style,
                        is_draft, agent_name, agent_phone, memorial_video,
                        flower_gift_description, location_name, location_address,
                        location_area, traffic_info, tomb_location_name,
                        tomb_location_address, tomb_location_area, tomb_traffic_info,
                        ceremony_process_list, is_public
                    ) VALUES (
                        %(service_area)s, %(deceased_name)s, %(birth_date)s, %(death_date)s,
                        %(hide_birth_date)s, %(hide_death_date)s, %(ceremony_details)s,
                        %(background_music)s, %(desktop_background)s, %(font_style)s,
                        %(is_draft)s, %(agent_name)s, %(agent_phone)s, %(memorial_video)s,
                        %(flower_gift_description)s, %(location_name)s, %(location_address)s,
                        %(location_area)s, %(traffic_info)s, %(tomb_location_name)s,
                        %(tomb_location_address)s, %(tomb_location_area)s, %(tomb_traffic_info)s,
                        %(ceremony_process_list)s, %(is_public)s
                    )
                """
            
            # 執行 SQL
            cursor.execute(sql, update_data)
            
            if not obituary_id:
                obituary_id = cursor.lastrowid
                print(f"\n創建新訃聞:")
                print(f"- 新訃聞 ID: {obituary_id}")
            else:
                print(f"\n更新現有訃聞:")
                print(f"- 訃聞 ID: {obituary_id}")

            print(f"- 往生者: {update_data['deceased_name']}")
            print(f"- 是否為草稿: {is_draft}")
            print(f"- 儀式流程數量: {len(ceremony_process_list)}")

            # 處理照片上傳時分批處理
            print("\n開始處理照片上傳...")
            total_photos = 0

            # 處理基本照片（往生者照片、訃聞正反面）
            for field_name, photo_type in photo_types.items():
                if field_name in request.FILES:
                    file = request.FILES[field_name]
                    if file.size > 0:
                        try:
                            # 壓縮圖片
                            compressed_image = compress_image(file)
                            
                            photo_data = {
                                'obituary_id': obituary_id,
                                'photo_type': photo_type,
                                'photo_link': compressed_image,
                                'file_name': file.name,
                                'created_at': datetime.now()
                            }
                            
                            cursor.execute("""
                                INSERT INTO photos (
                                    obituary_id, photo_type, photo_link, file_name, created_at
                                ) VALUES (%s, %s, %s, %s, %s)
                            """, [
                                photo_data['obituary_id'],
                                photo_data['photo_type'],
                                photo_data['photo_link'],
                                photo_data['file_name'],
                                photo_data['created_at']
                            ])
                            
                            db.commit()
                            total_photos += 1
                            print(f"- {field_name}: 已上傳 {file.name}")
                            
                        except Exception as e:
                            print(f"上傳照片失敗: {e}")
                            continue
                else:
                    print(f"- {field_name}: 未上傳")

            # 處理生活照片
            for key in request.FILES:
                if key.startswith('life_photos['):
                    file = request.FILES[key]
                    if file.size > 0:
                        try:
                            # 壓縮圖片
                            compressed_image = compress_image(file)
                            
                            cursor.execute("""
                                INSERT INTO photos (
                                    obituary_id, photo_type, photo_link, file_name, created_at
                                ) VALUES (%s, 'life', %s, %s, NOW())
                            """, [obituary_id, compressed_image, file.name])
                            
                            db.commit()
                            total_photos += 1
                            print(f"- 已上傳生活照: {file.name}")
                            
                        except Exception as e:
                            print(f"上傳生活照片失敗: {e}")
                            continue

            # 處理花禮照片
            for key in request.FILES:
                if key.startswith('flower_gift_list['):
                    try:
                        index = key[key.find('[')+1:key.find(']')]
                        file = request.FILES[key]
                        if file.size > 0:
                            # 壓縮圖片
                            compressed_image = compress_image(file)
                            
                            name = request.POST.get(f'flower_gift_list[{index}][name]', '')
                            price = request.POST.get(f'flower_gift_list[{index}][price]', '')
                            orderable = request.POST.get(f'flower_gift_list[{index}][orderable]') == 'on'
                            
                            cursor.execute("""
                                INSERT INTO photos (
                                    obituary_id, photo_type, photo_link, file_name,
                                    name, price, orderable, created_at
                                ) VALUES (%s, 'flower_gift', %s, %s, %s, %s, %s, NOW())
                            """, [obituary_id, compressed_image, file.name, name, price, orderable])
                            
                            db.commit()
                            total_photos += 1
                            print(f"  - 已上傳花禮: {file.name}")
                            print(f"    名稱: {name}, 價格: {price}, 可訂購: {orderable}")
                            
                    except Exception as e:
                        print(f"上傳花禮照片失敗: {e}")
                        continue

            print(f"\n照片上傳總結:")
            print(f"- 總計上傳: {total_photos} 張照片")

            db.commit()
            
            print(f"\n訃聞資料更新成功！")
            print(f"- ID: {obituary_id}")
            print(f"- 是否為草稿: {is_draft}")
            print(f"- 更新時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print("="*50 + "\n")
            
            return JsonResponse({
                'success': True,
                'obituary_id': obituary_id
            })
            
        except Exception as e:
            db.rollback()
            print(f"更新訃聞資料錯誤: {e}")
            raise
            
        finally:
            cursor.close()
            db.close()
            
    except Exception as e:
        print(f"處理訃聞更新失敗: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

def home_view(request):
    """首頁視圖"""
    print(f"home_view session狀態: {dict(request.session)}")  # 调试信息
    
    if not request.session.get('is_authenticated'):
        return redirect('login')
    
    # 获取限等级
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
                request.session['phone'] = user_data['phone']
                request.session['email'] = user_data['email']
                request.session['department'] = user_data['department']
                request.session['title'] = user_data['title']
                request.session['company'] = user_data['company']
                request.session['permission_level'] = user_data['permission_type']
                
                print(f"登入成功 - 用戶: {username}")
                print(f"權限等級: {user_data['permission_type']}")
                
                if next_url:
                    return redirect(next_url)
                return redirect('home')
            else:
                messages.error(request, '帳號或密錯誤')
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
    """訃聞列表面"""
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
                background_music = background_music.replace('static/audio/', '')
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
                用戶：{username}
                姓名: {realname}
                密碼：{password}
                電話：{phone}
                電子郵件：{email}
                部門：{department}
                職稱：{title}
                公司：{company}
                權限等級：{permission_type}
                是否啟用：{'是' if is_active else '否'}
                是否為管理：{'是' if is_superuser else '否'}
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
    print(f"當前用戶限: {request.session.get('permission_level')}")  # 调试信息
    
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
        print(f"切換用戶狀態錯誤: {e}")
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
        messages.success(request, '用戶已刪除資料庫內容')
        
    except Exception as e:
        db.rollback()
        print(f"刪除用戶錯誤: {e}")
        messages.error(request, '刪除失敗，請稍後再試')
        
    finally:
        cursor.close()
        db.close()
        
    return redirect('preview_employee')

@require_http_methods(["GET", "POST"])
def retrieve_obituary(request, obituary_id):
    """取得資料庫中的訃聞資料"""
    try:
        print("\n" + "="*50)
        print("開始擷取訃聞資料...")
        print(f"時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"訃聞 ID: {obituary_id}")
        
        if not request.session.get('is_authenticated'):
            print("錯誤: 使用者未登入")
            return JsonResponse({'success': False, 'error': '請先登入'})
            
        db = connection_db()
        if not db:
            print("錯誤: 資料庫連接失敗")
            return JsonResponse({'success': False, 'error': '資料庫連接失敗'})
            
        cursor = db.cursor(dictionary=True)
        
        try:
            # 獲取訃聞基本資料
            print("\n正在獲取基本資料...")
            cursor.execute("""
                SELECT *, COALESCE(is_public, 0) as is_public 
                FROM obituary WHERE id = %s
            """, [obituary_id])
            
            obituary_data = cursor.fetchone()
            if not obituary_data:
                print("錯誤: 找不到訃聞資料")
                return JsonResponse({'success': False, 'error': '找不到訃聞資料'})
            
            print("\n基本資料摘要:")
            print(f"- 往生者: {obituary_data.get('deceased_name', '未設定')}")
            print(f"- 建立時間: {obituary_data.get('created_at', '未設定')}")
            print(f"- 服務區域: {obituary_data.get('service_area', '未設定')}")
            print(f"- 背景音樂: {obituary_data.get('background_music', '未設定')}")
            print(f"- 背景樣式: {obituary_data.get('desktop_background', '未設定')}")
            print(f"- 字體樣式: {obituary_data.get('font_style', '未設定')}")
            print(f"- 是否公開: {'是' if obituary_data.get('is_public') else '否'}")

            # 獲取各種類型的照片
            print("\n正在獲取照片資料...")
            photo_queries = {
                'deceased_photo': "SELECT * FROM photos WHERE obituary_id = %s AND photo_type = 'personal' LIMIT 1",
                'obituary_front': "SELECT * FROM photos WHERE obituary_id = %s AND photo_type = 'obituary_front' LIMIT 1",
                'obituary_back': "SELECT * FROM photos WHERE obituary_id = %s AND photo_type = 'obituary_back' LIMIT 1",
                'life_photos': "SELECT * FROM photos WHERE obituary_id = %s AND photo_type = 'life'",
                'flower_gifts': "SELECT * FROM photos WHERE obituary_id = %s AND photo_type = 'flower_gift'"
            }
            
            photos = {}
            for key, query in photo_queries.items():
                print(f"\n處理 {key} 照片:")
                cursor.execute(query, [obituary_id])
                if key in ['life_photos', 'flower_gifts']:
                    photos[key] = []
                    results = cursor.fetchall()
                    print(f"- 找到 {len(results)} 張照片")
                    for idx, photo in enumerate(results, 1):
                        if photo.get('photo_link'):
                            photo_data = {
                                'id': photo['id'],
                                'photo_link': base64.b64encode(photo['photo_link']).decode('utf-8'),
                                'name': photo.get('name', ''),
                                'price': photo.get('price', ''),
                                'orderable': photo.get('orderable', False),
                                'file_name': photo.get('file_name', '未命名檔案'),
                                'created_at': photo.get('created_at').strftime('%Y-%m-%d %H:%M:%S')
                            }
                            photos[key].append(photo_data)
                            print(f"  {idx}. ID: {photo['id']}")
                            print(f"     檔案名稱: {photo.get('file_name', '未命名檔案')}")
                            print(f"     建立時間: {photo.get('created_at').strftime('%Y-%m-%d %H:%M:%S')}")
                else:
                    photo = cursor.fetchone()
                    if photo and photo.get('photo_link'):
                        photos[key] = {
                            'id': photo['id'],
                            'data': base64.b64encode(photo['photo_link']).decode('utf-8'),
                            'name': photo.get('file_name', '未命名檔案'),
                            'created_at': photo.get('created_at').strftime('%Y-%m-%d %H:%M:%S')
                        }
                        print(f"- 成功獲取照片")
                        print(f"  ID: {photo['id']}")
                        print(f"  檔案名稱: {photo.get('file_name', '未命名檔案')}")
                        print(f"  建立時間: {photo.get('created_at').strftime('%Y-%m-%d %H:%M:%S')}")
                    else:
                        print("- 未上傳照片")

            # 處理日期格式
            print("\n處理日期格式...")
            if obituary_data.get('birth_date'):
                obituary_data['birth_date'] = obituary_data['birth_date'].strftime('%Y-%m-%d')
                print(f"- 生日: {obituary_data['birth_date']}")
            if obituary_data.get('death_date'):
                obituary_data['death_date'] = obituary_data['death_date'].strftime('%Y-%m-%d')
                print(f"- 死亡日期: {obituary_data['death_date']}")
            
            # 處理儀式流程
            print("\n處理儀式流程...")
            ceremony_process = []
            if obituary_data.get('ceremony_process_list'):
                try:
                    ceremony_process = json.loads(obituary_data['ceremony_process_list'])
                    print(f"- 找到 {len(ceremony_process)} 個流程項目:")
                    for idx, process in enumerate(ceremony_process, 1):
                        print(f"  {idx}. 時間: {process.get('time', '未設定')}")
                        print(f"     內容: {process.get('content', '未設定')}")
                except json.JSONDecodeError as e:
                    print(f"錯誤: 解析儀式流程失敗 - {e}")
                    ceremony_process = []
            else:
                print("- 無儀式流程資料")
            
            print("\n資料擷取完成!")
            print("="*50 + "\n")
            
            # 返回完整資料
            return JsonResponse({
                'success': True,
                'data': {
                    'obituary': obituary_data,
                    'photos': photos,
                    'ceremony_process': ceremony_process
                }
            }, safe=False)
            
        finally:
            cursor.close()
            db.close()
            
    except Exception as e:
        print(f"\n錯誤: 資料擷取失敗 - {e}")
        print("="*50 + "\n")
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@require_http_methods(["GET", "POST"])
def make_obituary(request, obituary_id):
    """製作正式訃聞"""
    try:
        print("\n" + "="*50)
        print("開始製作正式訃聞...")
        print(f"時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"訃聞 ID: {obituary_id}")
        
        db = connection_db()
        if not db:
            return JsonResponse({'success': False, 'error': '資料庫連接失敗'})
            
        cursor = db.cursor(dictionary=True)
        
        try:
            # 更新點擊次數
            cursor.execute("""
                UPDATE obituary 
                SET view_count = COALESCE(view_count, 0) + 1 
                WHERE id = %s
            """, [obituary_id])
            
            # 獲取訃聞資料
            cursor.execute("""
                SELECT * FROM obituary WHERE id = %s
            """, [obituary_id])
            
            obituary_data = cursor.fetchone()
            if not obituary_data:
                return JsonResponse({'success': False, 'error': '找不到訃聞資料'})

            # 準備渲染資料
            preview_data = {
                'deceased_name': obituary_data.get('deceased_name'),
                'birth_date': obituary_data.get('birth_date').strftime('%Y-%m-%d') if obituary_data.get('birth_date') else None,
                'death_date': obituary_data.get('death_date').strftime('%Y-%m-%d') if obituary_data.get('death_date') else None,
                'hide_birth_date': obituary_data.get('hide_birth_date'),
                'hide_death_date': obituary_data.get('hide_death_date'),
                'ceremony_details': obituary_data.get('ceremony_details'),
                'background_music': obituary_data.get('background_music'),
                'desktop_background': obituary_data.get('desktop_background'),
                'font_style': obituary_data.get('font_style'),
                'area_selection': obituary_data.get('service_area'),
                'agent_name': obituary_data.get('agent_name'),
                'agent_phone': obituary_data.get('agent_phone'),
                'memorial_video': extract_youtube_id(obituary_data.get('memorial_video')),
                'flower_gift_description': obituary_data.get('flower_gift_description'),
                'location_name': obituary_data.get('location_name'),
                'location_address': obituary_data.get('location_address'),
                'location_area': obituary_data.get('location_area'),
                'traffic_info': obituary_data.get('traffic_info'),
                'tomb_location_name': obituary_data.get('tomb_location_name'),
                'tomb_location_address': obituary_data.get('tomb_location_address'),
                'tomb_location_area': obituary_data.get('tomb_location_area'),
                'tomb_traffic_info': obituary_data.get('tomb_traffic_info'),
            }

            # 獲取照片資料
            cursor.execute("""
                SELECT * FROM photos WHERE obituary_id = %s
            """, [obituary_id])
            photos = cursor.fetchall()

            # 處理照片資料
            for photo in photos:
                if photo.get('photo_link'):
                    photo_type = photo.get('photo_type')
                    if photo_type == 'personal':
                        preview_data['deceased_photo'] = f"data:image/jpeg;base64,{base64.b64encode(photo['photo_link']).decode('utf-8')}"
                    elif photo_type == 'obituary_front':
                        preview_data['obituary_front'] = f"data:image/jpeg;base64,{base64.b64encode(photo['photo_link']).decode('utf-8')}"
                    elif photo_type == 'obituary_back':
                        preview_data['obituary_back'] = f"data:image/jpeg;base64,{base64.b64encode(photo['photo_link']).decode('utf-8')}"
                    elif photo_type == 'life':
                        if 'life_photos' not in preview_data:
                            preview_data['life_photos'] = []
                        preview_data['life_photos'].append(f"data:image/jpeg;base64,{base64.b64encode(photo['photo_link']).decode('utf-8')}")
                    elif photo_type == 'flower_gift':
                        if 'flower_gifts' not in preview_data:
                            preview_data['flower_gifts'] = []
                        preview_data['flower_gifts'].append({
                            'name': photo.get('name'),
                            'price': photo.get('price'),
                            'image': f"data:image/jpeg;base64,{base64.b64encode(photo['photo_link']).decode('utf-8')}",
                            'orderable': bool(photo.get('orderable', False))
                        })

            # 處理儀式流程
            if obituary_data.get('ceremony_process_list'):
                try:
                    preview_data['ceremony_items'] = json.loads(obituary_data['ceremony_process_list'])
                except json.JSONDecodeError:
                    preview_data['ceremony_items'] = []

            # 更新訃聞狀態為非草稿
            cursor.execute("""
                UPDATE obituary 
                SET is_draft = 0
                WHERE id = %s
            """, [obituary_id])
            
            db.commit()
            
            print(f"點擊計數更新成功！")
            print(f"- 訃聞 ID: {obituary_id}")
            print(f"- 新點擊次數: {obituary_data['view_count']}")
            print(f"- 更新時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            
            return render(request, 'obituary_page.html', {'data': preview_data})
            
        except Exception as e:
            db.rollback()
            print(f"錯誤: 製作訃聞失敗 - {e}")
            raise
            
        finally:
            cursor.close()
            db.close()
            
    except Exception as e:
        print(f"\n嚴重錯誤: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

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
    try:
        print("\n" + "="*50)
        print("開始載入草稿編輯資料...")
        print(f"時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"訃聞 ID: {obituary_id}")
        
        if not request.session.get('is_authenticated'):
            print("錯誤: 使用者未登入")
            messages.error(request, '請先登入')
            return redirect('login')
            
        db = connection_db()
        if not db:
            print("錯誤: 資庫連接失敗")
            raise Exception("資料庫連接失敗")
            
        cursor = db.cursor(dictionary=True)
        
        try:
            # 獲取草稿訃聞基本資料
            print("\n正在獲取草稿資料...")
            cursor.execute("""
                SELECT * FROM obituary 
                WHERE id = %s AND is_draft = 1
            """, [obituary_id])
            
            draft_data = cursor.fetchone()
            if not draft_data:
                print("錯誤: 找不到草稿訃聞")
                messages.error(request, '找不到該草稿訃聞')
                return redirect('draft_obituaries')
                
            print(f"成功獲取草稿資料:")
            print(f"- 往生者: {draft_data['deceased_name']}")
            print(f"- 建立時間: {draft_data['created_at']}")
            
            # 處理儀式流程
            ceremony_process = []
            if draft_data.get('ceremony_process_list'):
                try:
                    ceremony_process = json.loads(draft_data['ceremony_process_list'])
                    print(f"\n儀式流程解析成功:")
                    for idx, process in enumerate(ceremony_process, 1):
                        print(f"  {idx}. 時間: {process.get('time', '')}")
                        print(f"     內容: {process.get('content', '')}")
                except json.JSONDecodeError as e:
                    print(f"解析儀式流程錯誤: {e}")
                    ceremony_process = []
            
            # 獲取各種類型的照片
            photo_queries = {
                'deceased_photo': "SELECT * FROM photos WHERE obituary_id = %s AND photo_type = 'personal' LIMIT 1",
                'obituary_front': "SELECT * FROM photos WHERE obituary_id = %s AND photo_type = 'obituary_front' LIMIT 1",
                'obituary_back': "SELECT * FROM photos WHERE obituary_id = %s AND photo_type = 'obituary_back' LIMIT 1",
                'life_photos': "SELECT * FROM photos WHERE obituary_id = %s AND photo_type = 'life'",
                'flower_gifts': "SELECT * FROM photos WHERE obituary_id = %s AND photo_type = 'flower_gift'"
            }
            
            print("\n照片資料:")
            photos = {}
            for key, query in photo_queries.items():
                cursor.execute(query, [obituary_id])
                if key in ['life_photos', 'flower_gifts']:
                    photos[key] = []
                    results = cursor.fetchall()
                    print(f"- {key}:")
                    for idx, photo in enumerate(results):
                        if photo.get('photo_link'):
                            photo_data = {
                                'id': photo['id'],
                                'photo_link': base64.b64encode(photo['photo_link']).decode('utf-8'),
                                'name': photo.get('name', ''),
                                'price': photo.get('price', ''),
                                'orderable': photo.get('orderable', False),
                                'file_name': photo.get('file_name', '未命名檔案'),
                                'created_at': photo.get('created_at').strftime('%Y-%m-%d %H:%M:%S')
                            }
                            photos[key].append(photo_data)
                            print(f"  {idx}. ID: {photo['id']}")
                            print(f"     檔案名稱: {photo.get('file_name', '未命名檔案')}")
                            print(f"     建立時間: {photo.get('created_at').strftime('%Y-%m-%d %H:%M:%S')}")
                else:
                    photo = cursor.fetchone()
                    print(f"- {key}:")
                    if photo and photo.get('photo_link'):
                        photos[key] = {
                            'id': photo['id'],
                            'data': base64.b64encode(photo['photo_link']).decode('utf-8'),
                            'name': photo.get('file_name', '未命名檔案'),
                            'created_at': photo.get('created_at').strftime('%Y-%m-%d %H:%M:%S')
                        }
                        print(f"  ID: {photo['id']}")
                        print(f"  檔案名稱: {photo.get('file_name', '未命名檔案')}")
                        print(f"  建立時間: {photo.get('created_at').strftime('%Y-%m-%d %H:%M:%S')}")
                    else:
                        print("  未上傳")
            
            # 準備模板資料
            context = {
                'edit_mode': True,
                'obituary': {
                    'id': draft_data['id'],
                    'service_area': draft_data['service_area'],
                    'deceased_name': draft_data['deceased_name'],
                    'birth_date': draft_data['birth_date'],
                    'death_date': draft_data['death_date'],
                    'hide_birth_date': bool(draft_data['hide_birth_date']),
                    'hide_death_date': bool(draft_data['hide_death_date']),
                    'ceremony_details': draft_data['ceremony_details'] or '',
                    'farewell_location_name': draft_data.get('location_name', ''),
                    'farewell_location_address': draft_data.get('location_address', ''),
                    'farewell_location_area': draft_data.get('location_area', ''),
                    'farewell_traffic_info': draft_data.get('traffic_info', ''),
                    'tomb_location_name': draft_data.get('tomb_location_name', ''),
                    'tomb_location_address': draft_data.get('tomb_location_address', ''),
                    'tomb_location_area': draft_data.get('tomb_location_area', ''),
                    'tomb_traffic_info': draft_data.get('tomb_traffic_info', ''),
                    'flower_gift_description': draft_data.get('flower_gift_description', ''),
                    'agent_name': draft_data.get('agent_name', ''),
                    'agent_phone': draft_data.get('agent_phone', ''),
                    'memorial_video': draft_data.get('memorial_video', ''),
                    'background_music': draft_data.get('background_music', ''),
                    'desktop_background': draft_data.get('desktop_background', ''),
                    'font_style': draft_data.get('font_style', ''),
                    'is_draft': True
                },
                'photos': photos,
                'ceremony_process': ceremony_process
            }
            
            print("\n編輯草稿資料摘要:")
            print(f"訃聞 ID: {context['obituary']['id']}")
            print(f"往生者姓名: {context['obituary']['deceased_name']}")
            print(f"服務區域: {context['obituary']['service_area']}")
            print(f"照片數量: {len(photos)}")
            print(f"儀式流程: {len(ceremony_process)} 項")
            print("="*50 + "\n")
            
            return render(request, 'draft_maker.html', context)
            
        except Exception as e:
            print(f"編輯草稿錯誤: {e}")
            raise
            
        finally:
            cursor.close()
            db.close()
            
    except Exception as e:
        print(f"載入草稿失敗: {e}")
        messages.error(request, '無法載入草稿資料')
        return redirect('draft_obituaries')

def obituary_list(request):
    """訃聞列表頁面"""
    try:
        db = connection_db()
        if not db:
            messages.error(request, '系統錯誤，請稍後再試')
            return redirect('home')
            
        cursor = db.cursor(dictionary=True)
        
        try:
            # 獲取搜尋參數
            service_area = request.GET.get('service_area', '')
            deceased_name = request.GET.get('deceased_name', '')
            
            # 基本條件：非草稿的訃聞
            conditions = ["is_draft = 0"]
            params = []
            
            # 添加搜尋條件
            if service_area:
                conditions.append("service_area = %s")
                params.append(service_area)
                print(f"搜尋條件 - 服務區域: {service_area}")
            
            if deceased_name:
                conditions.append("deceased_name LIKE %s")
                params.append(f"%{deceased_name}%")
                print(f"搜尋條件 - 往生者姓名: {deceased_name}")
            
            # 組合 SQL 查詢
            sql = f"""
                SELECT id, deceased_name, service_area, created_at, 
                       COALESCE(view_count, 0) as view_count,
                       is_public
                FROM obituary 
                WHERE {' AND '.join(conditions)}
                ORDER BY created_at DESC
            """
            
            print(f"\n執行查詢:")
            print(f"SQL: {sql}")
            print(f"參數: {params}")
            
            cursor.execute(sql, params)
            obituaries = cursor.fetchall()
            
            # 處理日期格式
            for obituary in obituaries:
                if obituary.get('created_at'):
                    obituary['created_at'] = obituary['created_at'].strftime('%Y-%m-%d %H:%M:%S')
            
            print(f"\n搜尋結果:")
            print(f"- 找到 {len(obituaries)} 筆訃聞")
            
            # 如果是 AJAX 請求，返回 JSON
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'obituaries': obituaries
                })
            
            # 否則返回完整頁面
            context = {
                'title': '訃聞列表',
                'obituaries': obituaries
            }
            
            return render(request, 'obituary_list.html', context)
            
        except Exception as e:
            print(f"獲取訃聞列表錯誤: {e}")
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'error': str(e)
                })
            messages.error(request, '無法載入訃聞列表')
            return redirect('home')
            
        finally:
            cursor.close()
            db.close()
            
    except Exception as e:
        print(f"訃聞列表頁面錯誤: {e}")
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': False,
                'error': str(e)
            })
        messages.error(request, '系統錯誤，請稍後再試')
        return redirect('home')

@require_http_methods(["GET", "POST"])
def obituary_search(request):
    """搜尋訃聞"""
    try:
        print("\n" + "="*50)
        print("開始搜尋訃聞...")
        print(f"時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        db = connection_db()
        if not db:
            return JsonResponse({'success': False, 'error': '資料庫連接失敗'})
            
        cursor = db.cursor(dictionary=True)
        
        try:
            service_area = request.GET.get('service_area', '')
            deceased_name = request.GET.get('deceased_name', '')
            
            # 基本條件：必須是公開的訃聞
            base_conditions = ["is_public = 1", "is_draft = 0"]
            params = []
            
            # 添加服務區域條件
            if service_area:
                base_conditions.append("service_area = %s")
                params.append(service_area)
                print(f"搜尋條件 - 服務區域: {service_area}")
            
            # 添加姓名條件
            if deceased_name:
                base_conditions.append("deceased_name LIKE %s")
                params.append(f"%{deceased_name}%")
                print(f"搜尋條件 - 往生者姓名: {deceased_name}")
            
            # 組合 SQL 查詢
            sql = f"""
                SELECT id, deceased_name, service_area, created_at, 
                       COALESCE(view_count, 0) as view_count,
                       is_public
                FROM obituary 
                WHERE {' AND '.join(base_conditions)}
                ORDER BY created_at DESC
            """
            
            print(f"\n執行查詢:")
            print(f"SQL: {sql}")
            print(f"參數: {params}")
            
            cursor.execute(sql, params)
            obituaries = cursor.fetchall()
            
            # 處理日期格式
            for obituary in obituaries:
                if obituary.get('created_at'):
                    obituary['created_at'] = obituary['created_at'].strftime('%Y-%m-%d %H:%M:%S')
            
            print(f"\n搜尋結果:")
            print(f"- 找到 {len(obituaries)} 筆訃聞")
            
            return JsonResponse({
                'success': True,
                'obituaries': obituaries
            })
            
        except Exception as e:
            print(f"搜尋訃聞錯誤: {e}")
            return JsonResponse({
                'success': False,
                'error': str(e)
            })
            
        finally:
            cursor.close()
            db.close()
            
    except Exception as e:
        print(f"處理搜尋請求失敗: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

# ... 其他視圖函數 ...