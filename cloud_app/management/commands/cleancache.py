from django.core.management.base import BaseCommand
import os
from django.conf import settings
from cloud_app.views import make_obituary
import mysql.connector

class Command(BaseCommand):
    help = '清理並重新生成訃聞快取'

    def handle(self, *args, **options):
        self.stdout.write("開始清理訃聞快取...")
        
        # 清理舊的訃聞檔案
        obituary_dir = os.path.join(settings.STATICFILES_DIRS[0], 'obituaries')
        if os.path.exists(obituary_dir):
            for file in os.listdir(obituary_dir):
                if file.endswith('.html'):
                    os.remove(os.path.join(obituary_dir, file))
                    self.stdout.write(f'已刪除: {file}')

        # 重新生成訃聞檔案
        try:
            db = mysql.connector.connect(
                host=settings.DATABASES['default']['HOST'],
                user=settings.DATABASES['default']['USER'],
                password=settings.DATABASES['default']['PASSWORD'],
                database=settings.DATABASES['default']['NAME'],
                port=settings.DATABASES['default']['PORT']
            )
            
            cursor = db.cursor(dictionary=True)
            cursor.execute("SELECT id FROM obituary")
            obituary_ids = cursor.fetchall()
            
            for obituary in obituary_ids:
                try:
                    # 創建一個模擬的 request 物件
                    class EmptyRequest:
                        method = 'POST'
                        session = {'is_authenticated': True}
                        FILES = {}
                        POST = {}

                    request = EmptyRequest()
                    
                    # 調用 make_obituary 函數重新生成
                    if make_obituary(request, obituary['id']):
                        self.stdout.write(self.style.SUCCESS(f'已重新生成訃聞 ID: {obituary["id"]}'))
                    else:
                        self.stdout.write(self.style.ERROR(f'重新生成訃聞失敗 ID: {obituary["id"]}'))
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'重新生成訃聞失敗 ID: {obituary["id"]}, 錯誤: {e}'))
                    
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'資料庫連接錯誤: {e}'))
            
        finally:
            if 'cursor' in locals():
                cursor.close()
            if 'db' in locals():
                db.close() 