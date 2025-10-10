from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from Mock.models import Purchase 

class Command(BaseCommand):
    help = "1 soatdan ortiq 'Tekshirilmoqda' holatida turgan to'lovlarni avtomatik tasdiqlaydi."

    def handle(self, *args, **options):
        one_hour_ago = timezone.now() - timedelta(hours=1)

        # 1 soatdan ortiq kutilayotgan to'lovlarni topish
        purchases_to_approve = Purchase.objects.filter(
            status='moderation',
            updated_at__lte=one_hour_ago
        )
        
        count = 0
        for purchase in purchases_to_approve:
            try:
                # Modelimizdagi on_success metodini chaqiramiz
                purchase.on_success() 
                # Status 'completed' ga o'zgaradi, foydalanuvchiga xizmat beriladi
                self.stdout.write(self.style.SUCCESS(f"Xarid #{purchase.id} avtomatik tasdiqlandi."))
                count += 1
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Xarid #{purchase.id} ni tasdiqlashda xato: {e}"))

        if count > 0:
            self.stdout.write(f"Jami {count} ta xarid muvaffaqiyatli tasdiqlandi.")
        else:
            self.stdout.write("Avtomatik tasdiqlash uchun xaridlar topilmadi.")