# app_nomi/management/commands/set_bot_menu.py
import requests
from django.core.management.base import BaseCommand
from django.conf import settings

class Command(BaseCommand):
    help = 'Telegram bot uchun Veb Ilova (Web App) menyu tugmasini o`rnatadi'

    def handle(self, *args, **options):
        # settings.py dan tokenni olamiz
        token = settings.TELEGRAM_BOT_TOKEN
        
        # O'rnatiladigan menyu ma'lumotlari
        menu_data = {
            "menu_button": {
                "type": "web_app",
                "text": "🚀 Imtihonlar",  # Tugmada chiqadigan yozuv
                "web_app": {
                    # Web App ochadigan manzil. SAYTINGIZ MANZILIGA O'ZGARTIRING!
                    "url": "https://sizning-domeningiz.uz/all_exams/" 
                }
            }
        }

        # Telegram API'ga so'rov yuborish
        url = f"https://api.telegram.org/bot{token}/setChatMenuButton"
        
        try:
            response = requests.post(url, json=menu_data)
            response_data = response.json()
            
            if response_data.get('ok'):
                self.stdout.write(self.style.SUCCESS("✅ Bot menyusi muvaffaqiyatli o'rnatildi!"))
            else:
                self.stdout.write(self.style.ERROR(f"❌ Xatolik: {response_data.get('description')}"))
        
        except requests.RequestException as e:
            self.stdout.write(self.style.ERROR(f"❌ Ulanishda xatolik: {e}"))