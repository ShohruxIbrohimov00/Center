from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """
    Ro'yxat, QuerySet yoki lug'atdan indeks/kalit bo'yicha element olish.
    """
    try:
        return dictionary[key]
    except (KeyError, IndexError):
        return None