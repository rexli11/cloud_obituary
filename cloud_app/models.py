from django.db import models
from django.db import connection

class ObituaryClick(models.Model):
    obituary_id = models.IntegerField()  # 對應原有訃聞的 ID
    click_count = models.PositiveIntegerField(default=0)  # 點擊計數
    last_click = models.DateTimeField(auto_now=True)  # 最後點擊時間
    created_at = models.DateTimeField(auto_now_add=True)  # 創建時間

    class Meta:
        db_table = 'obituary_clicks'  # 指定資料表名稱

    @classmethod
    def increment_click(cls, obituary_id):
        """增加點擊次數"""
        with connection.cursor() as cursor:
            try:
                # 先更新計數
                cursor.execute("""
                    UPDATE obituary 
                    SET view_count = COALESCE(view_count, 0) + 1 
                    WHERE id = %s
                """, [obituary_id])
                
                # 然後獲取新的計數值
                cursor.execute("""
                    SELECT view_count 
                    FROM obituary 
                    WHERE id = %s
                """, [obituary_id])
                
                result = cursor.fetchone()
                connection.commit()  # 確保更新被提交
                return result[0] if result else 0
                
            except Exception as e:
                print(f"計數更新錯誤: {e}")
                connection.rollback()  # 發生錯誤時回滾
                return 0
