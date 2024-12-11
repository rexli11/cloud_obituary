from django.core.management.base import BaseCommand
import os
from django.conf import settings
from cloud_app.views import make_obituary

class Command(BaseCommand):
    help = '清理並重新生成訃聞快取'

    def handle(self, *args, **options):
        # 清理舊的訃聞檔案
        obituary_dir = os.path.join(settings.STATICFILES_DIRS[0], 'obituaries')
        if os.path.exists(obituary_dir):
            for file in os.listdir(obituary_dir):
                if file.endswith('.html'):
                    os.remove(os.path.join(obituary_dir, file))
                    self.stdout.write(f'已刪除: {file}')

        # 重新生成訃聞檔案
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute("SELECT id FROM obituary")
            obituary_ids = cursor.fetchall()
            
            for (obituary_id,) in obituary_ids:
                try:
                    make_obituary(None, obituary_id, regenerate=True)
                    self.stdout.write(f'已重新生成訃聞 ID: {obituary_id}')
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'重新生成訃聞失敗 ID: {obituary_id}, 錯誤: {e}')) 