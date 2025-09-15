myenv\Scripts\activate
pip install -r requirements.txt
python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver

2 xil rol mavjud talaba, ustoz rollari.
talaba roli ro'yhatdan o'tiboq signin qilib shaxsiy profiliga kirishi mumkin.
Ustoz roli faqat admin tasdiqlagandan keyingina shaxsiy profiliga kira oladi.

Ustoz:
savol yaratish tahrirlash o'chirish
test yaratish savollarni tanlash
testi natijalrini kuzatib borish

talaba:
test ishlash, natijalarni ko'rish

test:
test vaqti, savollar soni, 
