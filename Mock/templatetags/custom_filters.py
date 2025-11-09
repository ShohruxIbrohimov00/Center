from django import template
from django.utils.safestring import mark_safe
import re


register = template.Library()
@register.filter
def add(value, arg):
    """HTML stringdan boshlang'ich va oxirgi <p> tegini va bo'shliqlarni olib tashlaydi."""
    try:
        return int(value) + int(arg)
    except (ValueError, TypeError):
        return value
        
@register.filter
def sub(value, arg):
    """Berilgan qiymatlarni bir-biridan ayiradi."""
    try:
        return int(value) - int(arg)
    except (ValueError, TypeError):
        return value
    
@register.filter
def get_item(dictionary, key):
    """
    Ro'yxat, QuerySet yoki lug'atdan indeks/kalit bo'yicha element olish.
    """
    try:
        return dictionary[key]
    except (KeyError, IndexError):
        return None
    
@register.filter
def filter_by_id(queryset, id):
    """
    Queryset ichidan berilgan ID bo'yicha yagona ob'ektni qaytaradi.
    exam_create.html da xato yuz berganda avvalgi tanlangan bo'limlarni 
    tartibda ko'rsatish uchun ishlatiladi.
    """
    try:
        # ID ni integer ga o'tkazamiz, chunki u shablon orqali string bo'lib kelishi mumkin
        return queryset.get(id=int(id))
    except queryset.model.DoesNotExist:
        return None
    except ValueError:
        # Agar ID raqam bo'lmasa
        return None
    
@register.filter
def remove_p_tags(value):
    """HTML stringdan boshlang'ich va oxirgi <p> tegini va bo'shliqlarni olib tashlaydi."""
    if not value:
        return value
        
    if isinstance(value, str):
        # 1. Matnni boshidan va oxiridan bo'shliqlarni olib tashlaymiz
        stripped_value = value.strip()
        
        # 2. Agar matn <p>...</p> bilan boshlanib tugagan bo'lsa (case insensitive)
        p_tag_match = re.match(r'^\s*<p>(.*)</p>\s*$', stripped_value, re.DOTALL | re.IGNORECASE)
        
        if p_tag_match:
            # FAQAT <p>...</p> ichidagi matnni olamiz
            value = p_tag_match.group(1).strip()
            
    return mark_safe(value)

@register.filter
def clean_uzbek_text(value):
    """
    HTML teglarini olib tashlaydi va O'zbek tilidagi apostrof muammolarini (`, ‘, ’) standart (') ga almashtiradi.
    """
    if not value:
        return value
        
    # HTML teglarini olib tashlash
    clean_value = re.sub(r'<[^>]*?>', '', str(value))
    
    # Apostroflarni standartlashtirish
    clean_value = clean_value.replace('‘', "'")
    clean_value = clean_value.replace('’', "'")
    clean_value = clean_value.replace('`', "'")
    
    return mark_safe(clean_value)

@register.filter
def mul(value, arg):
    """
    Ikki sonni ko'paytiradi: {{ 35|mul:60 }} → 2100
    """
    try:
        return int(value) * int(arg)
    except (ValueError, TypeError):
        return 0