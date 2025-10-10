import json
from Mock.models import Flashcard 
from django.contrib.auth.models import User  

# JSON faylni o'qing
with open('flashcards.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

for item in data:
    # Authorni olish, agar kerak bo'lsa
    author = User.objects.get(id=item['author_id'])

    # Flashcard obyektini yaratish yoki mavjudini yangilash
    flashcard, created = Flashcard.objects.get_or_create(
        english_content=item['english_content'],
        defaults={
            'content_type': item['content_type'],
            'uzbek_meaning': item['uzbek_meaning'],
            'context_sentence': item.get('context_sentence', ''),
            'author': author,
        }
    )
    if not created:
        # Agar kerak bo'lsa mavjud yozuvni yangilash
        flashcard.content_type = item['content_type']
        flashcard.uzbek_meaning = item['uzbek_meaning']
        flashcard.context_sentence = item.get('context_sentence', '')
        flashcard.author = author
        flashcard.save()

print("Flashcards bazaga muvaffaqiyatli yuklandi!")
