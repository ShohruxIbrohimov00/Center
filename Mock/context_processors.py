# Mock/context_processors.py

from Mock.models import Center  # Markaz modelini import qilish

def global_context(request):
    """
    Har bir so'rovga CENTER_NAME, center va CENTER_SLUG kabi global ma'lumotlarni qo'shadi.
    """
    default_name = "SAT Makon"
    context = {
        'CENTER_NAME': default_name,
        'center': None,
        'CENTER_SLUG': None,
    }

    if request.user.is_authenticated:
        user = request.user
        
        # 1. User Markazga bog'langanmi?
        if hasattr(user, 'center') and user.center:
            current_center = user.center
            
            # 2. Kontekstga markaz ma'lumotlarini qo'shish
            context['center'] = current_center
            context['CENTER_SLUG'] = current_center.slug
            context['CENTER_NAME'] = current_center.name
            
        # 3. Superuser uchun maxsus nomlash
        if user.is_superuser:
            context['CENTER_NAME'] = default_name
            # Superuser uchun center konteksti kerak emas (chunki u bir markazga bog'lanmagan)
            context['center'] = None
            context['CENTER_SLUG'] = None 
            
    return context