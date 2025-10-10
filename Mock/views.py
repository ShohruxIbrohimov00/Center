from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate, update_session_auth_hash
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.db.models import Sum, Count, Max, Min, F, Q, Window, Avg
from django.db import transaction
from django.utils import timezone
from django.template.loader import render_to_string
from django.urls import reverse
from django.views.decorators.http import require_POST
from django.db.models.functions import Coalesce, Rank
from django.db import IntegrityError
from django.conf import settings
from datetime import timedelta
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.http import require_POST
from django.db import transaction
import string 
from django.template.loader import render_to_string 
import json
import logging
from .models import *
from .forms import *
import bleach

logger = logging.getLogger(__name__)

def is_teacher(user):
    return user.is_authenticated and user.role == 'teacher'

def is_student(user):
    return user.is_authenticated and user.role == 'student'


# ==========================================================
# RO'YXATDAN O'TISH, KIRISH VA CHIQISH FUNKSIYALARI
# ==========================================================

def signup_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, f"Xush kelibsiz, {user.username}! Akkauntingiz muvaffaqiyatli yaratildi.")
            return redirect('dashboard')
        else:
            # Forma xato bo'lsa, foydalanuvchiga umumiy xabar beramiz.
            # Aniq xatolar shablonning o'zida `form.errors` orqali ko'rsatiladi.
            messages.error(request, "Iltimos, formadagi xatoliklarni to'g'rilang.")
    else:
        form = SignUpForm()
        
    return render(request, 'registration/signup.html', {'form': form})

def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
        
    if request.method == 'POST':
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            # Tizimga kirganda alohida xabar chiqarish shart emas,
            # chunki foydalanuvchi dashboard'ga o'tganidan buni tushunadi.
            
            next_page = request.GET.get('next')
            if next_page:
                return redirect(next_page)
            return redirect('dashboard')
        else:
            # Login yoki parol xato bo'lsa, bu xabar chiqadi.
            # Bu shablondagi `{% if form.errors %}` blokiga qo'shimcha.
            messages.error(request, "Foydalanuvchi nomi yoki parol noto'g'ri kiritildi.")
    else:
        form = LoginForm()
        
    return render(request, 'registration/login.html', {'form': form})

def logout_view(request):
    logout(request)
    messages.info(request, "Siz tizimdan muvaffaqiyatli chiqdingiz. Yana kutib qolamiz!")
    return redirect('index')

def index(request):
    """Bosh sahifani ko'rsatadi."""
    if request.user.is_authenticated:
        return redirect('dashboard') 
    return render(request, 'index.html')

# ==========================================================
# PROFIL VA PAROLNI O'ZGARTIRISH
# ==========================================================

@login_required(login_url='login')
def profile_view(request):
    """Profil sahifasini ko'rsatadi va ma'lumotlarni tahrirlashni boshqaradi."""
    if request.method == 'POST':
        form = ProfileUpdateForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Profilingiz muvaffaqiyatli yangilandi.")
            return redirect('profile')
        else:
            messages.error(request, "Ma'lumotlarni saqlashda xatolik yuz berdi. Iltimos, formalarni to'g'ri to'ldiring.")
    else:
        form = ProfileUpdateForm(instance=request.user)

    subscription = getattr(request.user, 'subscription', None)
    user_balance = getattr(request.user, 'balance', None)
    
    context = {
        'form': form,
        'subscription': subscription,
        'user_balance': user_balance,
    }
    return render(request, 'student/profile.html', context)


@login_required(login_url='login')
def change_password_view(request): 
    """Foydalanuvchining parolini o'zgartirish."""
    if request.method == 'POST':
        form = CustomPasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            messages.success(request, 'Parolingiz muvaffaqiyatli o\'zgartirildi!')
            return redirect('profile')
        else:
            messages.error(request, 'Iltimos, formadagi xatoliklarni to\'g\'rilab, qayta urinib ko\'ring.')
    else:
        form = CustomPasswordChangeForm(request.user)
        
    return render(request, 'registration/change_password.html', {'form': form})

# ==========================================================
# DASHBOARD
# ==========================================================

@login_required(login_url='login')
def dashboard_view(request):
    """
    Foydalanuvchining shaxsiy kabinetini (dashboard) ko'rsatadi.
    Bu yerda faqat ma'lumotlar yig'iladi, shuning uchun `messages` ishlatilmaydi.
    """
    user = request.user
    
    # --- "Aqlli Kun Tartibi" ---
    agenda_items = []
    try:
        review_needed_count = UserFlashcardStatus.objects.filter(user=user, next_review_at__lte=timezone.now()).count()
        if review_needed_count > 0:
            agenda_items.append({
                'priority': 1, 'icon': '🧠', 'title': f"{review_needed_count} ta so'zni takrorlang",
                'description': "Spaced repetition bo'yicha eslatish vaqti keldi.",
                'url': reverse('my_flashcards')
            })
    except Exception as e:
        logger.error(f"Error getting flashcard review count for user {user.id}: {e}")

    latest_attempt = UserAttempt.objects.filter(user=user, is_completed=True).order_by('-completed_at').first()
    if latest_attempt:
        agenda_items.append({
            'priority': 2, 'icon': '📈', 'title': "Oxirgi imtihonni tahlil qiling",
            'description': f"'{latest_attempt.exam.title}'dagi xatolaringiz ustida ishlang.",
            'url': reverse('view_result_detail', args=[latest_attempt.id])
        })
        
    attempted_exam_ids = UserAttempt.objects.filter(user=user).values_list('exam_id', flat=True)
    new_exam_to_start = Exam.objects.filter(is_active=True).exclude(id__in=attempted_exam_ids).order_by('?').first()
    if new_exam_to_start:
        agenda_items.append({
            'priority': 3, 'icon': '🚀', 'title': "Yangi imtihonni boshlang",
            'description': f"'{new_exam_to_start.title}' bilan bilimingizni sinab ko'ring.",
            'url': reverse('all_exams')
        })

    agenda_items = sorted(agenda_items, key=lambda x: x['priority'])[:3]

    # --- "Haftalik Progress" ---
    today = timezone.now().date()
    seven_days_ago = today - timedelta(days=6)
    date_range = [seven_days_ago + timedelta(days=i) for i in range(7)]
    chart_labels = json.dumps([d.strftime("%b %d") for d in date_range])
    
    exam_scores = UserAttempt.objects.filter(user=user, is_completed=True, completed_at__date__range=[seven_days_ago, today]).values('completed_at__date').annotate(avg_score=Avg('final_total_score')).order_by('completed_at__date')
    score_map = {item['completed_at__date']: item['avg_score'] for item in exam_scores}
    exam_score_data = json.dumps([round(score_map.get(d, 0)) for d in date_range])

    try:
        reviews_by_day = FlashcardReviewLog.objects.filter(user=user, timestamp__date__range=[seven_days_ago, today]).values('timestamp__date').annotate(review_count=Count('id'))
        review_map = {item['timestamp__date']: item['review_count'] for item in reviews_by_day}
        flashcard_data = json.dumps([review_map.get(d, 0) for d in date_range])
    except Exception:
        flashcard_data = json.dumps([0] * 7)

    # --- "Liderlar Doskasi" ---
    leaderboard_users = CustomUser.objects.annotate(
        max_score=Max('attempts__final_total_score')
    ).filter(max_score__isnull=False).order_by('-max_score')[:5]
    
    user_rank = None
    if user.is_authenticated:
        user_with_rank = CustomUser.objects.annotate(
            max_score=Max('attempts__final_total_score'),
            rank=Window(expression=Rank(), order_by=F('max_score').desc())
        ).filter(id=user.id).values('rank').first()
        if user_with_rank:
            user_rank = user_with_rank['rank']

    # --- Umumiy Statistika ---
    stats = UserAttempt.objects.filter(user=user, is_completed=True).aggregate(
        highest_score=Coalesce(Max('final_total_score'), 0),
        completed_exam_count=Count('exam', distinct=True)
    )
    learned_flashcards_count = UserFlashcardStatus.objects.filter(user=user, status='learned').count()

    context = {
        'agenda_items': agenda_items,
        'chart_labels': chart_labels,
        'exam_score_data': exam_score_data,
        'flashcard_data': flashcard_data,
        'highest_score': stats['highest_score'],
        'completed_exam_count': stats['completed_exam_count'],
        'learned_flashcards_count': learned_flashcards_count,
        'review_needed_count': review_needed_count,
        'leaderboard_users': leaderboard_users,
        'user_rank': user_rank,
    }
    
    return render(request, 'student/dashboard.html', context)

@login_required
def all_exams_view(request):
    """
    Yangi karusel dizayniga moslashtirilgan va NARX xatoligi tuzatilgan.
    """
    user = request.user
    
    # --- 1-QISM: Ma'lumotlarni to'g'ri olish ---

    # Barcha aktiv imtihonlarni olish va har birining MINIMAL narxini biriktirish
    exams = Exam.objects.filter(is_active=True).prefetch_related(
        'sections', 
        'flashcard_exam'
    ).annotate(
        attempt_count=Count('userattempt', filter=models.Q(userattempt__user=user, userattempt__is_completed=True)),
        min_price=Min('packages__price')  # MUHIM O'ZGARISH: Narxni ExamPackage'dan olamiz
    )

    exam_ids = [exam.id for exam in exams]

    # Eng yaxshi urinishlarni topish
    best_attempts_qs = UserAttempt.objects.filter(
        user=user, 
        is_completed=True,
        exam_id__in=exam_ids
    ).values('exam_id').annotate(max_score=Max('final_total_score'))

    best_attempts_map = {item['exam_id']: item['max_score'] for item in best_attempts_qs}

    # Barcha ma'lumotlarni yig'ish
    all_exams_data = []
    for exam in exams:
        max_score = best_attempts_map.get(exam.id)
        best_attempt_obj = {'id': True, 'final_total_score': max_score} if max_score is not None else None

        all_exams_data.append({
            'type': 'exam',
            'obj': exam, # Endi 'exam' obyektida 'min_price' atributi bor
            'exam_mode_count': exam.attempt_count,
            'total_duration': exam.sections.aggregate(total=Sum('duration_minutes'))['total'] or 0,
            'total_questions': exam.sections.aggregate(total=Sum('max_questions'))['total'] or 0,
            'has_flashcard_exam': hasattr(exam, 'flashcard_exam'),
            'user_best_attempt': best_attempt_obj,
            'can_start_exam': user.has_active_subscription() or (hasattr(user, 'balance') and user.balance.exam_credits > 0),
        })

    # Yangi imtihonlar (qo'shilgan sanasi bo'yicha)
    new_exams = sorted(all_exams_data, key=lambda x: x['obj'].created_at, reverse=True)[:10]

    # Eng ommabop imtihonlar (topshirishlar soni bo'yicha)
    popular_exams = sorted(all_exams_data, key=lambda x: x['exam_mode_count'], reverse=True)[:10]

    # Bepul imtihonlar (minimal narxi yo'q yoki 0 bo'lganlar)
    free_exams = [data for data in all_exams_data if data['obj'].min_price is None or data['obj'].min_price == 0]

    context = {
        'new_exams': new_exams,
        'popular_exams': popular_exams,
        'free_exams': free_exams,
        'user_has_subscription': user.has_active_subscription(),
    }
    
    return render(request, 'student/all_exams.html', context)

@login_required(login_url='login')
def completed_exams_view(request):
    user = request.user
    
    completed_exam_ids = UserAttempt.objects.filter(
        user=user, is_completed=True
    ).values_list('exam_id', flat=True).distinct()

    exam_results = []
    
    for exam_id in completed_exam_ids:
        try:
            exam = Exam.objects.get(id=exam_id)
            attempts = UserAttempt.objects.filter(user=user, exam=exam, is_completed=True)
            
            best_attempt = attempts.order_by('-final_total_score', '-completed_at').first()
            latest_attempt = attempts.order_by('-completed_at').first()
            
            has_flashcard_exam = hasattr(exam, 'flashcard_exam')

            exam_results.append({
                'exam': exam,
                'attempt_count': attempts.count(),
                'best_attempt': best_attempt,
                'latest_attempt': latest_attempt,
                'has_flashcard_exam': has_flashcard_exam,
            })
        except Exam.DoesNotExist:
            logger.warning(f"Exam {exam_id} not found for user {user.username}")
            continue

    # Eng yuqori ballar bo'yicha saralash
    top_results = sorted(
        exam_results, 
        key=lambda x: x['best_attempt'].final_total_score if x['best_attempt'] and x['best_attempt'].final_total_score is not None else 0, 
        reverse=True
    )

    # Oxirgi topshirilganlar bo'yicha saralash
    recent_results = sorted(
        exam_results, 
        key=lambda x: x['latest_attempt'].completed_at if x['latest_attempt'] and x['latest_attempt'].completed_at is not None else timezone.datetime.min, 
        reverse=True
    )

    context = {
        'top_results': top_results,
        'recent_results': recent_results,
    }
    return render(request, 'student/completed_exams.html', context)

# ==========================================================
# IMTIHON URINISHLARI VA DETAL VIEW'LARI
# ==========================================================

@login_required(login_url='login')
def exam_attempts_view(request, exam_id):
    """
    Foydalanuvchining ma'lum bir imtihon bo'yicha barcha yakunlagan urinishlari ro'yxatini ko'rsatadi.
    (Bu faqat ma'lumot ko'rsatish view'si, messages qo'shish mantiqiy emas).
    """
    try:
        exam = get_object_or_404(Exam.objects.prefetch_related('sections'), id=exam_id, is_active=True)
    except:
        messages.error(request, "Imtihon topilmadi yoki aktiv emas.")
        return redirect('all_exams')

    attempts_qs = UserAttempt.objects.filter(
        user=request.user,
        exam=exam,
        is_completed=True
    ).order_by('-completed_at')

    # To'g'ri va noto'g'ri javoblar sonini hisoblash
    # Ushbu hisoblash usuli N+1 muammosini keltirib chiqarishi mumkin, ammo siz yuborgan kodni o'zgartirmayapman.
    # Agar tezlik muammo tug'dirsa, buni bitta so'rovda annotate orqali bajarish tavsiya etiladi.
    total_questions = exam.sections.aggregate(total=Sum('max_questions'))['total'] or 0
    
    for attempt in attempts_qs:
        correct_answers = UserAnswer.objects.filter(
            attempt_section__attempt=attempt, is_correct=True
        ).count()
        incorrect_answers = UserAnswer.objects.filter(
            attempt_section__attempt=attempt, is_correct=False
        ).count()
        
        omitted_answers = total_questions - correct_answers - incorrect_answers

        attempt.correct_answers = correct_answers
        attempt.incorrect_answers = incorrect_answers
        attempt.omitted_answers = omitted_answers

    best_attempt = attempts_qs.order_by('-final_total_score').first()
    latest_attempt = attempts_qs.first()

    context = {
        'exam': exam,
        'attempts': attempts_qs,
        'best_attempt': best_attempt,
        'latest_attempt': latest_attempt,
    }
    
    return render(request, 'student/exam_attempts.html', context)

@login_required(login_url='login')
def exam_detail_view(request, exam_id):
    """
    Imtihon sozlamalari sahifasini ko'rsatadi va imtihonni boshlash uchun dastlabki tekshiruvlarni o'tkazadi.
    """
    exam = get_object_or_404(Exam, id=exam_id, is_active=True)
    user = request.user

    # 1. Foydalanuvchi rolini tekshirish
    if not is_student(user): 
        messages.error(request, "Sizda bu imtihonni boshlash huquqi yo'q.")
        return redirect('index')

    # 2. Pullik imtihon uchun obuna/kredit tekshiruvi
    # is_premium emasligini tekshirish. Agar pullik bo'lmasa, har doim boshlash mumkin.
    user_can_start_exam = not exam.is_premium or user.has_active_subscription() or (hasattr(user, 'balance') and user.balance.exam_credits > 0)
    
    if exam.is_premium and not user_can_start_exam:
        # Pul kerak va foydalanuvchida obuna/kredit yo'q bo'lsa
        messages.error(request, "Bu imtihon pullik. Iltimos, obuna sotib oling yoki kreditlaringizni tekshiring.")
        return redirect('price')

    # 3. Flashcard mavjudligini tekshirish
    has_flashcard_exam = hasattr(exam, 'flashcardexam')

    context = {
        'exam': exam,
        'has_flashcard_exam': has_flashcard_exam,
    }
    return render(request, 'student/exam_detail.html', context)

# =================================================================
# YANGI VIEW: Tariflar sahifasi
# =================================================================
def price_view(request):
    exam_packages = ExamPackage.objects.filter(is_active=True).order_by('price')
    subscription_plans = SubscriptionPlan.objects.filter(is_active=True).order_by('price')
    form = PurchaseForm()

    context = {
        'exam_packages': exam_packages,
        'subscription_plans': subscription_plans,
        'form': form,
    }
    return render(request, 'student/price.html', context)

# =================================================================
# YANGI VIEW: Xarid mantiqi
# =================================================================

@login_required(login_url='login')
@transaction.atomic 
def process_purchase_view(request, purchase_type, item_id):
    """
    Xaridni qayta ishlaydi, promo kodni qo'llaydi va foydalanuvchining balansini/obunasini yangilaydi.
    """
    if request.method != 'POST':
        messages.error(request, "Noto'g'ri so'rov usuli. Xarid POST so'rovi orqali amalga oshirilishi kerak.")
        return redirect('price')

    form = PurchaseForm(request.POST)
    
    if not form.is_valid():
        messages.error(request, "Kiritilgan ma'lumotlarda xatolik bor. Iltimos, formani tekshiring.")
        return redirect('price')

    promo_code_str = form.cleaned_data.get('promo_code')
    user = request.user
    
    try:
        # 1. Tarif yoki paketni topish
        item = None
        item_type_display = ""
        if purchase_type == 'package':
            item = get_object_or_404(ExamPackage, id=item_id, is_active=True)
            item_type_display = f"'{item.name}' paketi"
        elif purchase_type == 'subscription':
            item = get_object_or_404(SubscriptionPlan, id=item_id, is_active=True)
            item_type_display = f"'{item.name}' obunasi"
        else:
            messages.error(request, "Xatolik: Noto'g'ri xarid turi ko'rsatilgan.")
            return redirect('price')

        final_amount = item.price
        promo_code = None

        # 2. Promo kodni qo'llash
        if promo_code_str:
            try:
                promo_code = PromoCode.objects.get(code=promo_code_str, is_active=True)
                
                # Promo kod amal qilishini tekshirish
                if not promo_code.is_valid():
                    messages.error(request, "Ushbu promo kodning muddati tugagan yoki cheklovi bitgan.")
                    return redirect('price')
                
                # Chegirma hisoblash
                if promo_code.discount_type == 'percentage':
                    discount = final_amount * (promo_code.discount_percent / 100)
                    final_amount -= discount
                else: # 'fixed'
                    final_amount -= promo_code.discount_amount
                
                final_amount = max(0, final_amount)
                messages.info(request, f"Promo kod muvaffaqiyatli qo'llandi! Chegirma: {item.price - final_amount:.2f} so'm. Yangi narx: {final_amount:.2f} so'm.")

            except PromoCode.DoesNotExist:
                messages.error(request, "Kiritilgan promo kod noto'g'ri yoki topilmadi.")
                return redirect('price')

        # 3. Xarid yozuvini yaratish (Aslida bu yerda to'lov tizimi chaqiriladi)
        purchase = Purchase.objects.create(
            user=user,
            purchase_type=purchase_type,
            package=item if purchase_type == 'package' else None,
            subscription_plan=item if purchase_type == 'subscription' else None,
            amount=item.price,
            promo_code=promo_code,
            final_amount=final_amount,
            status='completed' # Hozircha to'lovni muvaffaqiyatli deb hisoblaymiz
        )

        # 4. Promo kod hisobini yangilash
        if promo_code:
            promo_code.used_count += 1
            promo_code.save()

        # 5. Foydalanuvchi balansini yangilash
        if purchase_type == 'package':
            balance, created = UserBalance.objects.get_or_create(user=user)
            balance.exam_credits += item.exam_credits
            balance.solution_view_credits += item.solution_view_credits_on_purchase
            balance.save()
        
        elif purchase_type == 'subscription':
            # Avvalgi obunani tugatish (agar mavjud bo'lsa)
            UserSubscription.objects.filter(user=user).delete()
            
            # Yangi obunani yaratish
            UserSubscription.objects.create(
                user=user,
                plan=item,
                start_date=timezone.now(),
                end_date=timezone.now() + timedelta(days=item.duration_days)
            )

        messages.success(request, f"{item_type_display} muvaffaqiyatli xarid qilindi! 🎉")
        return redirect('profile')

    except Exception as e:
        logger.error(f"Xaridni qayta ishlashda kutilmagan xato: {e}", exc_info=True)
        messages.error(request, "Xaridni yakunlashda kutilmagan server xatoligi yuz berdi. Iltimos, keyinroq urinib ko'ring.")
        return redirect('price')

# =================================================================
# IMTIHON TOPSHIRISH MANTIQI
# =================================================================

@login_required(login_url='login')
def exam_mode_view(request, exam_id, attempt_id):
    """
    Imtihon topshirish sahifasini (timer, savollar paneli bilan) ko'rsatadi.
    """
    try:
        # Foydalanuvchiga tegishli va aktiv urinishni olish
        attempt = get_object_or_404(UserAttempt, id=attempt_id, user=request.user, exam__id=exam_id)
        
        # Tugallanmagan bo'lim urinishini topish (imtihon davomiyligini ta'minlash uchun)
        section_attempt = UserAttemptSection.objects.filter(attempt=attempt, is_completed=False).first()
        
        if not section_attempt:
            # Agar bo'lim qolmagan bo'lsa, tugatilgan sahifaga yo'naltiramiz
            messages.info(request, "Imtihon bo'limlari yakunlangan.")
            return redirect('view_result_detail', attempt_id=attempt.id) # view_result_detail ga yo'naltirish
        
        # Timer mantiqi
        total_duration_seconds = section_attempt.section.duration_minutes * 60
        time_remaining_seconds = total_duration_seconds # Default

        if section_attempt.started_at is None:
            # Birinchi marta kirish
            section_attempt.started_at = timezone.now()
            section_attempt.remaining_time_seconds = total_duration_seconds
            section_attempt.save()
            time_remaining_seconds = total_duration_seconds
        else:
            # Avval boshlangan. Qolgan vaqtni qayta hisoblaymiz
            elapsed_seconds = (timezone.now() - section_attempt.started_at).total_seconds()
            
            # Agar avval saqlangan vaqt bo'lsa, o'tgan vaqtni hisobga olib yangilaymiz
            if section_attempt.remaining_time_seconds is not None:
                 # remaining_time_seconds ni yangilab qo'yamiz
                time_remaining_seconds = max(0, int(section_attempt.remaining_time_seconds - elapsed_seconds))
                
                # Agar vaqt tugagan bo'lsa, bo'limni yakunlaymiz
                if time_remaining_seconds == 0:
                    section_attempt.is_completed = True
                    section_attempt.completed_at = timezone.now()
                    section_attempt.save()
                    messages.warning(request, f"Vaqt tugashi sababli '{section_attempt.section.section_type}' bo'limi yakunlandi.")
                    return redirect('exam_mode', exam_id=exam_id, attempt_id=attempt_id) # Keyingi bo'limni chaqirishga urinish
            
            # O'zgarishlarni saqlash
            section_attempt.remaining_time_seconds = time_remaining_seconds
            section_attempt.save()


        # Qo'shimcha optionlarni aniqlash (kalkulyator, spravka)
        extra_options = []
        section_type = section_attempt.section.section_type.lower()
        if section_type == 'math_calc':
            extra_options.append('calculator')
        if section_type in ['math_no_calc', 'math_calc']:
            extra_options.append('reference')
        
        context = {
            'exam': attempt.exam,
            'attempt_id': attempt.id,
            'section_attempt_id': section_attempt.id,
            'section_attempt': section_attempt,
            'time_remaining_seconds': time_remaining_seconds,
            'csrf_token': request.META.get('CSRF_COOKIE', ''),
            'extra_options': extra_options,
        }
        
        return render(request, 'student/exam_mode.html', context)
        
    except UserAttempt.DoesNotExist:
        messages.error(request, "Imtihon urinishi topilmadi.")
        return redirect('all_exams')
    except Exception as e:
        logger.error(f"exam_mode_view xatosi: {str(e)}", exc_info=True)
        messages.error(request, "Imtihon sahifasini yuklashda kutilmagan xato yuz berdi.")
        return redirect('dashboard')

@login_required(login_url='login')
@require_POST
def handle_exam_ajax(request):
    """
    Imtihon davomida AJAX so'rovlarini (javobni saqlash, timer sinxronizatsiyasi, bo'limni tugatish) boshqaradi.
    (Bu funksiya JSON javob qaytargani uchun messages ishlatilmaydi).
    """
    try:
        data = json.loads(request.body)
        action = data.get('action')
        attempt_id = data.get('attempt_id')
        section_attempt_id = data.get('section_attempt_id')
        
        # Muhim: Barcha so'rovlar foydalanuvchiga tegishli ekanligini tekshiramiz
        section_attempt = get_object_or_404(
            UserAttemptSection, 
            id=section_attempt_id, 
            attempt__id=attempt_id, 
            attempt__user=request.user
        )
        attempt = section_attempt.attempt

        if action == 'get_section_data':
            # Savollarni ExamSectionStaticQuestion orqali tartiblangan holda olamiz
            static_questions_in_order = ExamSectionStaticQuestion.objects.filter(
                exam_section=section_attempt.section
            ).order_by('question_number').select_related('question')

            question_ids = [sq.question.id for sq in static_questions_in_order]
            
            if not question_ids:
                return JsonResponse({'status': 'error', 'message': 'Bu bo‘limda savollar mavjud emas.'}, status=400)
            
            # Javob berilgan va belgilangan savollar
            answered_data = UserAnswer.objects.filter(
                attempt_section=section_attempt, question_id__in=question_ids
            ).values('question_id', 'is_marked_for_review')
            
            answered_question_ids = [d['question_id'] for d in answered_data]
            marked_for_review = [d['question_id'] for d in answered_data if d['is_marked_for_review']]

            # Boshlanadigan savol ID sini aniqlash
            last_answered = UserAnswer.objects.filter(
                attempt_section=section_attempt, question_id__in=question_ids
            ).order_by('-id').last()

            initial_question_id = question_ids[0]
            if last_answered:
                try:
                    current_q_index = question_ids.index(last_answered.question_id)
                    # Oxirgi javob berilganidan keyingi savolga o'tamiz, agar mavjud bo'lsa
                    if current_q_index + 1 < len(question_ids):
                        initial_question_id = question_ids[current_q_index + 1]
                    else:
                         # Agar oxirgi savolga javob berilgan bo'lsa, yana birinchi savolga qaytaramiz (yoki oxirgisiga)
                        initial_question_id = question_ids[len(question_ids) - 1]
                except ValueError:
                    initial_question_id = question_ids[0]

            initial_question_data = get_question_data(request, section_attempt, initial_question_id)
            if 'error' in initial_question_data:
                return JsonResponse({'status': 'error', 'message': initial_question_data['error']}, status=500)

            return JsonResponse({
                'status': 'success',
                'question_ids': question_ids,
                'answered_question_ids': answered_question_ids,
                'marked_for_review': marked_for_review,
                'initial_question_id': initial_question_id,
                'initial_question_data': initial_question_data,
                'time_remaining_seconds': section_attempt.remaining_time_seconds or section_attempt.section.duration_minutes * 60
            })

        elif action == 'get_question_by_id':
            question_id = data.get('question_id')
            question_data = get_question_data(request, section_attempt, question_id)
            if 'error' in question_data:
                return JsonResponse({'status': 'error', 'message': question_data['error']}, status=500)
            return JsonResponse({'status': 'success', 'question_data': question_data})

        elif action == 'save_answer':
            question_id = data.get('question_id')
            is_marked_for_review = data.get('is_marked_for_review', False)
            question = get_object_or_404(Question, id=question_id)
            question_format = question.answer_format

            # Tranzaksiya ichida javobni saqlash
            with transaction.atomic():
                user_answer, created = UserAnswer.objects.get_or_create(
                    attempt_section=section_attempt, question=question
                )
                
                user_answer.is_marked_for_review = is_marked_for_review
                is_correct = False
                
                if question_format in ['single', 'multiple']:
                    selected_option_ids = data.get('selected_options', [])
                    if question_format == 'single' and 'selected_option' in data:
                        # Faqat bitta tanlovni olish
                        selected_option_ids = [data['selected_option']] if data.get('selected_option') is not None else []
                    
                    user_answer.selected_options.set(selected_option_ids)
                    user_answer.short_answer_text = None

                    # To'g'rilikni tekshirish
                    correct_options_ids = set(question.options.filter(is_correct=True).values_list('id', flat=True))
                    selected_options_ids_set = set(user_answer.selected_options.values_list('id', flat=True))
                    is_correct = selected_options_ids_set == correct_options_ids

                elif question_format == 'short_answer':
                    short_answer_text = data.get('short_answer_text', '').strip()
                    user_answer.short_answer_text = short_answer_text
                    user_answer.selected_options.clear()

                    # To'g'rilikni tekshirish
                    correct_answer_text = question.correct_short_answer.strip().lower() if question.correct_short_answer else ""
                    user_answer_text = user_answer.short_answer_text.lower() if user_answer.short_answer_text else ""
                    is_correct = user_answer_text == correct_answer_text

                user_answer.is_correct = is_correct
                user_answer.save()

            answered_question_ids = list(UserAnswer.objects.filter(
                attempt_section=section_attempt
            ).values_list('question_id', flat=True))
            
            return JsonResponse({'status': 'success', 'answered_question_ids': answered_question_ids})

        elif action == 'sync_timer':
            time_remaining = data.get('time_remaining')
            if time_remaining is not None:
                section_attempt.remaining_time_seconds = time_remaining
                section_attempt.save()
            return JsonResponse({'status': 'success'})

        elif action == 'finish_section' or action == 'finish_exam':
            with transaction.atomic():
                # Bo'limni yakunlash
                if action == 'finish_section' or action == 'finish_exam':
                    time_remaining = data.get('time_remaining')
                    if time_remaining is not None:
                        section_attempt.remaining_time_seconds = time_remaining
                    section_attempt.is_completed = True
                    section_attempt.completed_at = timezone.now()
                    section_attempt.save()

                # Keyingi bo'limga o'tishni tekshirish
                remaining_sections = UserAttemptSection.objects.filter(
                    attempt=attempt, is_completed=False
                ).count()

                if remaining_sections > 0 and action == 'finish_section':
                    # Keyingi bo'limga yo'naltirish
                    redirect_url = reverse('exam_mode', kwargs={'exam_id': attempt.exam.id, 'attempt_id': attempt.id})
                    return JsonResponse({'status': 'success', 'redirect_url': redirect_url})

                # Imtihon to'liq tugadi, ballarni hisoblash
                if remaining_sections == 0 or action == 'finish_exam':
                    
                    sections_qs = attempt.section_attempts.select_related('section').order_by('section__order')
                    
                    # Barcha javoblardagi to'g'ri sonini bo'limlar bo'yicha olish
                    correct_answers_by_section = UserAnswer.objects.filter(
                        attempt_section__attempt=attempt, is_correct=True
                    ).values('attempt_section__id').annotate(correct_count=Count('id'))
                    correct_map = {item['attempt_section__id']: item['correct_count'] for item in correct_answers_by_section}

                    # Ballarni hisoblash uchun xom ballarni yig'ish (Sizning kodingizdagi mantiq)
                    ebrw_raw = {'M1': None, 'M2': None, 'total': 0}
                    math_raw = {'M1': None, 'M2': None, 'total': 0}
                    for sect_att in sections_qs:
                        section_type = sect_att.section.section_type
                        correct = correct_map.get(sect_att.id, 0)
                        if section_type == 'read_write_m1':
                            ebrw_raw['M1'] = correct
                            ebrw_raw['total'] += correct
                        elif section_type == 'read_write_m2':
                            ebrw_raw['M2'] = correct
                            ebrw_raw['total'] += correct
                        elif section_type == 'math_no_calc':
                            math_raw['M1'] = correct
                            math_raw['total'] += correct
                        elif section_type == 'math_calc':
                            math_raw['M2'] = correct
                            math_raw['total'] += correct

                    # Ballarni o'lchamli shkalaga o'tkazish (get_adaptive_scaled_score funksiyasi mavjud deb hisoblaymiz)
                    # (Bu funksiya sizning utils.py faylingizda bo'lishi kerak)
                    final_ebrw_score = get_adaptive_scaled_score(ebrw_raw['M1'], ebrw_raw['total'], is_math=False)
                    final_math_score = get_adaptive_scaled_score(math_raw['M1'], math_raw['total'], is_math=True)
                    total_sat_score = (final_ebrw_score or 0) + (final_math_score or 0)

                    # Yakuniy natijalarni saqlash
                    attempt.final_ebrw_score = final_ebrw_score
                    attempt.final_math_score = final_math_score
                    attempt.final_total_score = total_sat_score
                    attempt.is_completed = True
                    attempt.completed_at = timezone.now()
                    attempt.save()

                    # Qolgan tugallanmagan bo'limlarni ham yakunlangan deb belgilash (agar qolgan bo'lsa, xatoliklar tufayli)
                    UserAttemptSection.objects.filter(
                        attempt=attempt, is_completed=False
                    ).update(is_completed=True, completed_at=timezone.now())

                    redirect_url = reverse('view_result_detail', kwargs={'attempt_id': attempt.id})
                    return JsonResponse({'status': 'finished', 'redirect_url': redirect_url})

        else:
            return JsonResponse({'status': 'error', 'message': f"Noto‘g‘ri harakat: {action}"}, status=400)

    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Noto‘g‘ri JSON ma’lumot. So‘rov tanasini tekshiring.'}, status=400)
    except UserAttemptSection.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Bo‘lim urinishi topilmadi. ID-larni tekshiring.'}, status=404)
    except Exception as e:
        logger.error(f"Error in handle_exam_ajax: {str(e)}", exc_info=True)
        return JsonResponse({'status': 'error', 'message': f'Server xatosi: {str(e)}'}, status=500)

# =================================================================
# YORDAMCHI FUNKSIYA (VIEW EMAS)
# =================================================================

def get_question_data(request, section_attempt, question_id):
    """
    Berilgan savolning ma'lumotlarini va foydalanuvchining oldingi javobini yuklaydi.
    Bu funksiya AJAX so'rovlariga xizmat qiladi.
    """
    try:
        # 1. Savol va variantlarni olish
        # Savol UserAttemptSection orqali olinishi kerak (M2M aloqasi orqali)
        question = section_attempt.questions.get(id=question_id)
        options = question.options.all()
        
        # 2. Harflarni qo'shish (A, B, C, ...)
        letters = list(string.ascii_uppercase)
        options_with_letters = list(zip(options, letters[:len(options)]))

        # 3. Mavjud UserAnswer ni olish (Oldingi javobni yuklash)
        user_answer = UserAnswer.objects.filter(
            attempt_section=section_attempt,
            question_id=question_id
        ).first()
        
        # 4. Oldingi javob ma'lumotlarini tayyorlash
        selected_option_ids = []
        short_answer = None
        is_marked = False
        
        if user_answer:
            selected_option_ids = list(user_answer.selected_options.values_list('id', flat=True))
            short_answer = user_answer.short_answer_text
            is_marked = user_answer.is_marked_for_review
        
        # 5. Contextni HTML render uchun tayyorlash
        context = {
            'question': question,
            'user_answer': user_answer,
            'options': options,
            'options_with_letters': options_with_letters,  # Harflarni qo'shdik
            'is_study_mode': section_attempt.attempt.mode == 'study',
            'selected_option_ids': selected_option_ids,
            'short_answer_text': short_answer
        }
        
        # 6. HTML render qilish
        options_html = render_to_string('student/question_options.html', context, request=request)
        
        # 7. Question data tayyorlash
        question_data = {
            'id': question.id,
            'question_text': question.text,
            'question_format': question.answer_format,
            'options_html': options_html,
            'question_image_url': question.image.url if question.image else '',
            'user_selected_options': selected_option_ids,
            'user_short_answer': short_answer,
            'is_marked_for_review': is_marked,
        }
        logger.info(f"Generated question data for question {question_id}")
        return question_data
        
    except Question.DoesNotExist:
        logger.error(f"Question {question_id} not found in section {section_attempt.id}")
        return {'error': "Savol bu bo'limda topilmadi."}
    except Exception as e:
        logger.error(f"get_question_data xatosi: {str(e)}", exc_info=True)
        return {'error': f'Savol yuklashda server xatosi: {str(e)}'}
        
        
# =================================================================
# IMTIHONNI BOSHLASH MANTIQI
# =================================================================

@login_required(login_url='login')
def start_exam_view(request, exam_id):
    """
    Imtihonni boshlaydi. Yangi urinish (UserAttempt) va bo'lim urinishlarini (UserAttemptSection) yaratadi.
    Bu funksiya AJAX orqali chaqiriladi va JSON javob qaytaradi.
    """
    # Kirish tekshiruvini @login_required decoratori hal qiladi, shuning uchun ichki tekshiruv keraksiz.
    
    try:
        exam = get_object_or_404(Exam, id=exam_id, is_active=True)
        # Tugallanmagan urinish mavjudligini tekshirish
        attempt = UserAttempt.objects.filter(user=request.user, exam=exam, is_completed=False).first()
        
        with transaction.atomic():
            if not attempt:
                # 1. Yangi urinishni yaratish
                attempt = UserAttempt.objects.create(
                    user=request.user,
                    exam=exam,
                    mode='exam' # Rejimni ko'rsatish
                )
                logger.info(f"New attempt created: {attempt.id} for exam {exam_id}")
                
                # 2. Bo'limlarni olish va UserAttemptSection yaratish
                sections = exam.sections.all().order_by('order')
                if not sections.exists():
                    logger.error(f"No sections found for exam {exam_id}")
                    return JsonResponse({'status': 'error', 'message': 'Bu imtihonda bo‘limlar mavjud emas'}, status=400)
                
                for section in sections:
                    section_attempt = UserAttemptSection.objects.create(
                        attempt=attempt,
                        section=section,
                        # Birinchi bo'lim uchun start_date va remaining_time to'g'ridan-to'g'ri beriladi
                        started_at=timezone.now(),
                        remaining_time_seconds=section.duration_minutes * 60
                    )
                    
                    # 3. Savollarni bog'lash (faqat 'static' examlar uchun)
                    if exam.exam_type == 'static':
                        static_questions = ExamSectionStaticQuestion.objects.filter(exam_section=section).order_by('question_number')
                        if static_questions.exists():
                            # M2M aloqani to'g'ri o'rnatish
                            questions = [sq.question for sq in static_questions]
                            section_attempt.questions.set(questions)
                        else:
                            logger.warning(f"No static questions found for section {section.id}")
                    # Adaptive exam'lar uchun savollar dinamik ravishda yaratiladi/beriladi, bu yerda o'tkazib yuboramiz.
            else:
                logger.info(f"Existing attempt found: {attempt.id} for exam {exam_id}")
            
            # 4. Foydalanuvchini imtihon rejimiga yo'naltirish
            section_attempt = UserAttemptSection.objects.filter(attempt=attempt, is_completed=False).first()
            if not section_attempt:
                logger.error(f"No active sections available for attempt {attempt.id}")
                return JsonResponse({'status': 'error', 'message': 'Imtihon bo‘limlari tugallangan'}, status=400)
            
            # Imtihon rejimiga yo'naltirish URL'ini qaytarish
            exam_url = reverse('exam_mode', kwargs={'exam_id': exam.id, 'attempt_id': attempt.id})
            return JsonResponse({'status': 'success', 'exam_url': exam_url})
        
    except Exam.DoesNotExist:
        logger.error(f"Exam {exam_id} not found or inactive")
        return JsonResponse({'status': 'error', 'message': 'Imtihon topilmadi yoki aktiv emas'}, status=404)
    except Exception as e:
        logger.error(f"start_exam_view error: {str(e)}", exc_info=True)
        return JsonResponse({'status': 'error', 'message': f'Imtihonni boshlashda kutilmagan server xatosi: {str(e)}'}, status=500)

# =================================================================
# STUDY MODE (O'QISH REJIMI) VIEWS
# =================================================================

@login_required(login_url='login')
def study_mode_view(request, exam_id):
    """
    Study Mode uchun asosiy sahifani yuklaydi.
    Yangi urinish (UserAttempt) va uning birinchi bo'limi (UserAttemptSection)ni yaratadi yoki topadi.
    """
    try:
        exam = get_object_or_404(Exam, id=exam_id, is_active=True)
        
        # 1. Study Mode uchun tugallanmagan attempt yaratish/topish
        attempt, created = UserAttempt.objects.get_or_create(
            user=request.user,
            exam=exam,
            mode='study',
            is_completed=False,
            defaults={'started_at': timezone.now()}
        )
        
        # 2. Keyingi/birinchi tugallanmagan bo'limni topish/yaratish
        
        # Avval tugallanmagan bo'lim urinishini qidirish
        section_attempt = UserAttemptSection.objects.filter(
            attempt=attempt, 
            is_completed=False
        ).order_by('section__order').first()

        if not section_attempt:
            # Agar tugallanmagan bo'lim qolmagan bo'lsa, birinchi bo'limni olishga harakat qilamiz
            first_section = exam.sections.all().order_by('order').first()
            
            if first_section:
                 # Agar avval hech qanday bo'lim yaratilmagan bo'lsa, birinchisini yaratamiz
                section_attempt, created = UserAttemptSection.objects.get_or_create(
                    attempt=attempt,
                    section=first_section,
                    defaults={'started_at': timezone.now()}
                )
            else:
                messages.error(request, "Imtihon bo'limlari mavjud emas.")
                return redirect('all_exams')

        # 3. Agar bu yangi bo'lim bo'lsa, uning savollarini bog'lash (faqat Study Mode da)
        if not section_attempt.questions.exists() and exam.exam_type == 'static':
            static_questions = ExamSectionStaticQuestion.objects.filter(exam_section=section_attempt.section).order_by('question_number')
            if static_questions.exists():
                questions = [sq.question for sq in static_questions]
                section_attempt.questions.set(questions)
                logger.info(f"Study Mode: Questions set for new section attempt {section_attempt.id}")
            else:
                 # Bu xato emas, shunchaki ogohlantirish bo'lishi mumkin
                logger.warning(f"No static questions found for section {section_attempt.section.id}")

        
        context = {
            'exam': exam,
            'attempt': attempt,
            'section_attempt': section_attempt,
            'mode': 'study'
        }
        return render(request, 'student/study_mode.html', context)
        
    except Exam.DoesNotExist:
        messages.error(request, "Imtihon topilmadi yoki aktiv emas.")
        return redirect('all_exams')
    except Exception as e:
        logger.error(f"study_mode_view xatosi: {str(e)}", exc_info=True)
        messages.error(request, "O'qish rejimini yuklashda kutilmagan xato yuz berdi.")
        return redirect('dashboard')

@login_required(login_url='login')
def handle_study_ajax(request):
    """
    Study Mode uchun AJAX so'rovlarini qayta ishlash.
    Yechim kreditlari har bir savol uchun hint/yechim so'ralganda kamayadi.
    (Bu funksiya JSON javob qaytargani uchun messages ishlatilmaydi).
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Noto‘g‘ri so‘rov usuli.'}, status=405)

    try:
        data = json.loads(request.body)
        action = data.get('action')
        attempt_id = data.get('attempt_id')
        section_attempt_id = data.get('section_attempt_id')
        
        attempt = get_object_or_404(UserAttempt, id=attempt_id, user=request.user)
        # section_attempt ga section ham kerak bo'lishi mumkinligi uchun select_related qo'shildi
        section_attempt = get_object_or_404(UserAttemptSection.objects.select_related('section'), id=section_attempt_id, attempt=attempt)
        
        # Study Mode da savollar UserAttemptSection.questions M2M orqali olinadi
        questions_qs = section_attempt.questions.all().order_by('examsectionstaticquestion__question_number') 
        answered_question_ids = set(UserAnswer.objects.filter(attempt_section=section_attempt).values_list('question_id', flat=True))

        if action == 'get_next_question':
            # Faqat javob berilmagan keyingi savolni olish
            next_question = questions_qs.exclude(id__in=answered_question_ids).first()
            
            if next_question:
                question_data = get_question_data(request, section_attempt, next_question.id)
                if 'error' in question_data:
                    return JsonResponse({'status': 'error', 'message': question_data['error']}, status=500)
                
                return JsonResponse({
                    'status': 'success',
                    'question_data': question_data
                })
            
            # Agar barcha savollarga javob berilgan bo'lsa
            with transaction.atomic():
                section_attempt.is_completed = True
                section_attempt.completed_at = timezone.now()
                section_attempt.save()

                # Keyingi bo'limga o'tishni tekshirish
                next_section = attempt.exam.sections.filter(
                    order__gt=section_attempt.section.order
                ).order_by('order').first()
                
                if next_section:
                    # Keyingi bo'lim urinishini yaratish
                    next_section_attempt, created = UserAttemptSection.objects.get_or_create(
                        attempt=attempt,
                        section=next_section,
                        defaults={'started_at': timezone.now()}
                    )
                    # Savollarni bog'lash (agar static bo'lsa)
                    if not next_section_attempt.questions.exists() and attempt.exam.exam_type == 'static':
                        static_questions = ExamSectionStaticQuestion.objects.filter(exam_section=next_section).order_by('question_number')
                        if static_questions.exists():
                            questions = [sq.question for sq in static_questions]
                            next_section_attempt.questions.set(questions)

                    return JsonResponse({
                        'status': 'section_finished',
                        'message': 'Bo‘lim yakunlandi. Keyingi bo‘limga o‘tmoqdasiz.',
                        'redirect_url': reverse('study_mode_view', kwargs={'exam_id': attempt.exam.id})
                    })
                else:
                    # Barcha bo'limlar tugadi - Imtihonni yakunlash
                    attempt.is_completed = True
                    attempt.completed_at = timezone.now()
                    attempt.save()
                    
                    # Foydalanuvchi missiyasi progressini yangilash (agar UserMissionProgress modelingiz bo'lsa)
                    try:
                        progress, _ = UserMissionProgress.objects.get_or_create(user=request.user)
                        progress.study_attempts_completed += 1
                        progress.save()
                    except NameError:
                        logger.warning("UserMissionProgress model is not defined.")

                    return JsonResponse({
                        'status': 'finished',
                        'message': 'Barcha savollar ko‘rib chiqildi. Imtihon yakunlandi.',
                        'redirect_url': reverse('dashboard') # Yoki natijalar sahifasiga
                    })

        # --- Qolgan mantiq to'liq saqlanadi, chunki u Study Mode uchun to'g'ri ishlaydi ---
        
        elif action == 'get_review_question':
            # ... (bu mantiq saqlanadi)
            incorrect_questions = data.get('incorrect_questions', [])
            
            # FAQAT SECTIONNING SAVOLLARI ICHIDAN XATOLARNI TEKSHIRAMIZ
            review_question = questions_qs.filter(id__in=incorrect_questions).exclude(id__in=answered_question_ids).first()

            if review_question:
                question_data = get_question_data(request, section_attempt, review_question.id)
                if 'error' in question_data:
                    return JsonResponse({'status': 'error', 'message': question_data['error']}, status=500)
                return JsonResponse({
                    'status': 'success',
                    'question_data': question_data
                })
            
            return JsonResponse({
                'status': 'finished',
                'message': 'Takrorlash uchun savollar tugadi.'
            })

        elif action == 'check_answer':
            # ... (bu mantiq saqlanadi, faqat AnswerOption import qilinganligiga ishonch hosil qilish kerak)
            question_id = data.get('question_id')
            question = get_object_or_404(Question, id=question_id)
            
            # AnswerOption modelini o'zgartirmasdan, uning importi bor deb hisoblaymiz.
            # Mantiq to'g'ri: javobni saqlaydi va to'g'riligini tekshiradi.
            
            with transaction.atomic():
                user_answer, created = UserAnswer.objects.get_or_create(
                    attempt_section=section_attempt,
                    question=question
                )

                correct_options = set(question.options.filter(is_correct=True).values_list('id', flat=True))
                is_correct = False
                
                # Javobni saqlash mantiqi
                if question.answer_format == 'single':
                    selected_option_id = data.get('selected_option')
                    user_answer.selected_options.set([selected_option_id] if selected_option_id else [])
                    user_answer.short_answer_text = None
                    is_correct = selected_option_id in correct_options if selected_option_id else False
                elif question.answer_format == 'multiple':
                    selected_option_ids = data.get('selected_options', [])
                    user_answer.selected_options.set(selected_option_ids)
                    user_answer.short_answer_text = None
                    is_correct = set(selected_option_ids) == correct_options
                elif question.answer_format == 'short_answer':
                    short_answer_text = data.get('short_answer_text', '').strip()
                    user_answer.short_answer_text = short_answer_text
                    user_answer.selected_options.clear()
                    
                    correct_answer_text = question.correct_short_answer.strip().lower() if question.correct_short_answer else ""
                    user_answer_text = user_answer.short_answer_text.lower() if user_answer.short_answer_text else ""
                    is_correct = user_answer_text == correct_answer_text
                
                user_answer.is_correct = is_correct
                user_answer.answered_at = timezone.now()
                user_answer.save()

                # Yechim ko'rsatish va Kredit kamaytirish mantiqi
                solution_data = None
                if data.get('show_solution', False):
                    user_balance = getattr(request.user, 'balance', None)
                    user_subscription = getattr(request.user, 'subscription', None)
                    has_solution_access = (user_subscription and hasattr(user_subscription, 'is_active') and user_subscription.is_active() and user_subscription.plan.includes_solution_access) if user_subscription else False

                    if not has_solution_access:
                        if not user_balance or user_balance.solution_view_credits <= 0:
                            return JsonResponse({'status': 'error', 'message': 'Yechim ko‘rish uchun kredit yetarli emas.'}, status=403)
                        
                        user_balance.solution_view_credits -= 1
                        user_balance.save()
                        logger.info(f"User {request.user.username} used 1 solution credit for question {question_id}. Remaining: {user_balance.solution_view_credits}")

                    solution_data = {
                        'is_correct': is_correct,
                        'solution_text': question.solution_text or "Yechim mavjud emas.",
                        'correct_answer_ids': list(correct_options)
                    }

                return JsonResponse({
                    'status': 'success',
                    'message': 'Javob tekshirildi',
                    'solution_data': solution_data
                })

        elif action == 'get_hint':
            # ... (bu mantiq saqlanadi, kredit kamaytirish tranzaksiya ichida)
            question_id = data.get('question_id')
            question = get_object_or_404(Question, id=question_id)
            user_balance = getattr(request.user, 'balance', None)
            user_subscription = getattr(request.user, 'subscription', None)
            has_solution_access = (user_subscription and hasattr(user_subscription, 'is_active') and user_subscription.is_active() and user_subscription.plan.includes_solution_access) if user_subscription else False

            if not has_solution_access:
                if not user_balance or user_balance.solution_view_credits <= 0:
                    return JsonResponse({'status': 'error', 'message': 'Yechim ko‘rish uchun kredit yetarli emas.'}, status=403)
                
                with transaction.atomic():
                    user_balance.solution_view_credits -= 1
                    user_balance.save()
                    logger.info(f"User {request.user.username} used 1 solution credit for hint on question {question_id}. Remaining: {user_balance.solution_view_credits}")

            user_answer, _ = UserAnswer.objects.get_or_create(
                attempt_section=section_attempt,
                question=question
            )
            user_answer.hint_used = True
            user_answer.save()

            return JsonResponse({
                'status': 'success',
                'hint_text': question.hint_text or "Tavsiya mavjud emas."
            })

        elif action == 'mark_for_review':
            # ... (bu mantiq saqlanadi)
            question_id = data.get('question_id')
            question = get_object_or_404(Question, id=question_id)
            user_answer, _ = UserAnswer.objects.get_or_create(
                attempt_section=section_attempt,
                question=question
            )
            user_answer.is_marked_for_review = True
            user_answer.save()

            return JsonResponse({
                'status': 'success',
                'message': 'Savol takrorlash uchun belgilandi.'
            })

        else:
            return JsonResponse({'status': 'error', 'message': 'Noma‘lum harakat.'}, status=400)

    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': "Noto'g'ri JSON formati."}, status=400)
    except Exception as e:
        logger.error(f"handle_study_ajax xatosi: {str(e)}", exc_info=True)
        return JsonResponse({'status': 'error', 'message': f'Server xatosi: {str(e)}'}, status=500)
    
# =========================================================================
# ⭐️ 1. FLASHCARDNI BOSHLASH (Redirect View)
# =========================================================================

@login_required
def start_flashcards_view(request, exam_id):
    """
    Foydalanuvchini ma'lum bir testga oid flashcard exam view ga yo'naltiradi.
    """
    try:
        exam = get_object_or_404(Exam, id=exam_id, is_active=True)
    except Exam.DoesNotExist:
        messages.error(request, "Imtihon topilmadi yoki u aktiv emas.")
        return redirect('all_exams')
        
    if hasattr(exam, 'flashcard_exam') and exam.flashcard_exam:
        return redirect('flashcard_exam_view', exam_id=exam.id)
        
    # Agar flashcard exam mavjud bo'lmasa, xabar berish va boshqa sahifaga yo'naltirish
    messages.info(request, "Bu imtihon uchun lug‘at kartochkalari mavjud emas.")
    return redirect('exam_detail', exam_id=exam.id)

# =========================================================================
# ⭐️ 2. FLASHCARD EXAM SAHIFASI (Render View)
# =========================================================================

@login_required
def flashcard_exam_view(request, exam_id):
    """
    Flashcard exam sahifasini ko'rsatadi. Faqat review vaqti kelgan yoki yangi flashcardlarni filtrlaydi.
    """
    try:
        flashcard_exam = get_object_or_404(FlashcardExam, source_exam__id=exam_id)
    except FlashcardExam.DoesNotExist:
        messages.error(request, "Lug‘at kartochkalari bo‘limi topilmadi.")
        return redirect('exam_detail', exam_id=exam_id) # Xato bo'lsa redirect qilamiz
        
    user = request.user
    session_title = f"{flashcard_exam.source_exam.title} bo'yicha takrorlash" 
    
    # 1. Flashcardlar ro'yxatini yuklash
    flashcards_qs = Flashcard.objects.filter(flashcard_exams=flashcard_exam)

    # 2. Review vaqti kelgan yoki yangi flashcardlarni filtrlash (SM-2 logic)
    flashcards_to_review = flashcards_qs.filter(
        Q(user_statuses__user=user, user_statuses__next_review_at__lte=timezone.now()) |
        ~Q(user_statuses__user=user)
    ).distinct()
    
    # 3. Foydalanuvchi statuslarini olish (Repetition Count)
    statuses = UserFlashcardStatus.objects.filter(
        user=user, 
        flashcard__in=flashcards_to_review.values_list('id', flat=True)
    ).values('flashcard_id', 'repetition_count')

    status_map = {s['flashcard_id']: s['repetition_count'] for s in statuses}
    
    # 4. JSON ma'lumotlarini tayyorlash (bleach bilan tozalash saqlangan)
    flashcards_list = []
    for fc in flashcards_to_review:
        repetition_count = status_map.get(fc.id, 0)
        flashcards_list.append({
            'id': fc.id,
            'english_content': bleach.clean(fc.english_content, tags=[], strip=True),
            'uzbek_meaning': bleach.clean(fc.uzbek_meaning, tags=[], strip=True),
            'context_sentence': bleach.clean(fc.context_sentence, tags=[], strip=True) if fc.context_sentence else '',
            'repetition_count': repetition_count,
        })
    
    # 5. Agar hech qanday flashcard topilmasa, keyingi review vaqtini ko'rsatish
    next_review_at = None
    if not flashcards_to_review.exists():
        next_review_status = UserFlashcardStatus.objects.filter(
            user=user
        ).exclude(
             next_review_at__lte=timezone.now()
        ).order_by('next_review_at').first()
        
        if next_review_status:
            next_review_at = next_review_status.next_review_at
    
    flashcards_json = json.dumps(flashcards_list)

    context = {
        'session_title': session_title, 
        'flashcard_exam': flashcard_exam, 
        'flashcards_json': flashcards_json,
        'total_flashcards': len(flashcards_list),
        'next_review_at': next_review_at, 
        'is_practice_session': False,
    }
    return render(request, 'student/flashcard_exam.html', context)

# =========================================================================
# ⭐️ 3. PROGRESS YANGILASH (SM2 mantiqi)
# =========================================================================

import json
import bleach
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.utils import timezone
from datetime import timedelta # SM2 algoritmi uchun timedelta import qilindi
# messages mavjud deb hisoblanadi (asosan redirect holatlari uchun)

# =========================================================================
# ⭐️ 3. PROGRESS YANGILASH (SM2 mantiqi) (AJAX View)
# =========================================================================

@login_required
def update_flashcard_progress(request):
    """
    Foydalanuvchi flashcard progressini yangilaydi (SM2 algoritmi asosida).
    Bu funksiya faqat JSON javob qaytaradi.
    """
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            flashcard_id = data.get('flashcard_id')
            user_response = data.get('user_response') # 'known' yoki 'unknown'

            # Kartochkani olish
            flashcard = Flashcard.objects.get(id=flashcard_id)
            user = request.user
            
            # Statusni olish yoki yaratish
            status, created = UserFlashcardStatus.objects.get_or_create(
                user=user,
                flashcard=flashcard,
                defaults={
                    'status': 'learning', 
                    'review_interval': 1, 
                    'ease_factor': 2.5, # SM2 boshlang'ich qiymati
                    'repetition_count': 0 
                }
            )
            
            min_interval = 1 

            if user_response == 'known':
                # 1. Ease Factor (Osonlik koeffitsiyenti) ni yangilash
                # Soddalashtirilgan SM2 (yoki sizning mantiqingiz) saqlanadi.
                status.ease_factor = status.ease_factor + 0.1
                status.ease_factor = max(1.3, status.ease_factor) 
                
                # 2. Repetition Count va Intervalni hisoblash
                if status.repetition_count == 0:
                    new_interval = 1
                elif status.repetition_count == 1:
                    new_interval = 6
                else:
                    # Intervalni ease_factor asosida oshirish
                    new_interval = status.review_interval * status.ease_factor
                
                # Natijani butun kunga yaxlitlash
                new_interval = round(new_interval)
                status.review_interval = max(min_interval, new_interval)
                status.repetition_count += 1
                status.status = 'learned'

            else:  # 'unknown' (bilinmaydi) yoki qiyin
                status.status = 'learning'
                status.repetition_count = 0 # Qayta boshlash
                status.review_interval = min_interval # Intervalni 1 kunga tiklash
                # Ease Factor kamayadi, minimal 1.3
                status.ease_factor = max(1.3, status.ease_factor - 0.2) 
            
            # 3. Vaqtlarni yangilash va saqlash
            status.last_reviewed_at = timezone.now()
            # next_review_at ni hisoblash uchun timedelta import qilindi
            status.next_review_at = timezone.now() + timedelta(days=status.review_interval)
            status.save()
            
            # JSON javob
            return JsonResponse({
                'success': True, 
                'status': status.status, 
                'next_review': status.next_review_at.isoformat(), 
                'repetition_count': status.repetition_count
            })
        
        except Flashcard.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Flashcard topilmadi'}, status=404)
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'error': 'Noto‘g‘ri JSON formati'}, status=400)
        except Exception as e:
            # Server xatolarini loglash va xabar berish
            # logger.error(f"update_flashcard_progress xatosi: {str(e)}", exc_info=True)
            return JsonResponse({'success': False, 'error': f'Server xatosi: {e}'}, status=500)
    
    return JsonResponse({'success': False, 'error': 'Faqat POST so\'rovlar qabul qilinadi'}, status=405)

# =========================================================================
# ⭐️ 4. MY_FLASHCARDS_VIEW (Statistika sahifasi) (Render View)
# =========================================================================

@login_required
def my_flashcards_view(request):
    """
    Foydalanuvchining barcha flashcardlar bo'yicha umumiy statistikasini ko'rsatadi
    va Donut Chart uchun foizlarni hisoblab beradi.
    """
    user = request.user

    # Barcha mavjud flashcardlar soni
    total_flashcards = Flashcard.objects.count()

    # 1. Foydalanuvchining statuslari bo'yicha hisoblash
    statuses = UserFlashcardStatus.objects.filter(user=user).values('status').annotate(
        count=Count('id')
    )
    
    status_map = {s['status']: s['count'] for s in statuses}

    learned_count = status_map.get('learned', 0)
    learning_count = status_map.get('learning', 0)

    # 2. Yangi kartochkalarni topish
    # Ko'rilgan (statusi mavjud) kartochkalar soni
    seen_flashcards_count = learned_count + learning_count 
    new_count = total_flashcards - seen_flashcards_count
    # new_count ni 0 dan kichik bo'lishini oldini olish
    new_count = max(0, new_count) 
    
    # 3. Bugun takrorlash kerak bo'lganlar
    review_needed_count = UserFlashcardStatus.objects.filter(
        user=user,
        next_review_at__lte=timezone.now()
    ).count()

    # 4. Keyingi takrorlash vaqti
    next_review_at_obj = UserFlashcardStatus.objects.filter(
        user=user,
        next_review_at__gt=timezone.now()
    ).order_by('next_review_at').first()
    
    next_review_at = next_review_at_obj.next_review_at if next_review_at_obj else None

    # 5. Diagramma uchun foizlarni hisoblash
    if total_flashcards > 0:
        learned_percentage = round((learned_count / total_flashcards) * 100)
        learning_percentage = round((learning_count / total_flashcards) * 100)
        
        # Qolgan foiz yangi kartochkalarga tegishli
        remaining_percentage = 100 - learned_percentage - learning_percentage
        new_percentage = max(0, remaining_percentage)
        
        # Yuvarlashdagi kichik xatolarni tuzatish
        if new_count == 0 and remaining_percentage > 0:
             # Agar yangi kartochka nol bo'lsa, qolgan foizni eng katta guruhga qo'shamiz (masalan, o'rganilganlarga)
             learned_percentage += remaining_percentage
             new_percentage = 0
             learned_percentage = min(100, learned_percentage)
             
    else:
        # Agar umuman kartochka bo'lmasa
        learned_percentage = 0
        learning_percentage = 0
        new_percentage = 0

    context = {
        'total_flashcards': total_flashcards,
        'learned_count': learned_count,
        'learning_count': learning_count,
        'new_count': new_count,
        'review_needed_count': review_needed_count,
        'next_review_at': next_review_at,
        
        # Diagramma uchun foizlar
        'learned_percentage': learned_percentage,
        'learning_percentage': learning_percentage,
        'new_percentage': new_percentage,
    }
    
    return render(request, 'student/my_flashcards.html', context)

# =========================================================================
# ⭐️ 5. PRACTICE_FLASHCARDS_VIEW (O'rganilayotgan/O'zlashtirilgan uchun)
# =========================================================================

@login_required
def practice_flashcards_view(request, status_filter):
    """
    Foydalanuvchining ma'lum bir statusdagi ('learning', 'learned', 'new', 'review')
    flashcardlarini mashq qilish uchun yuklaydi.
    """
    user = request.user
    
    # Kiritilgan status to'g'riligini tekshirish
    if status_filter not in ['learning', 'learned', 'new', 'review']:
        messages.error(request, "Noto‘g‘ri mashq statusi tanlandi.")
        return redirect('my_flashcards') 

    # Statusga qarab sarlavha va kartochkalar ro'yxatini shakllantirish
    if status_filter == 'learning':
        practice_title = "O'rganilayotganlarni Takrorlash"
        flashcards_to_practice = Flashcard.objects.filter(
            user_statuses__user=user,
            user_statuses__status='learning'
        ).distinct()

    elif status_filter == 'learned':
        practice_title = "O'zlashtirilganlarni Mustahkamlash"
        flashcards_to_practice = Flashcard.objects.filter(
            user_statuses__user=user,
            user_statuses__status='learned'
        ).distinct()

    elif status_filter == 'review':
        practice_title = "Bugungi Takrorlash"
        flashcards_to_practice = Flashcard.objects.filter(
            user_statuses__user=user,
            user_statuses__next_review_at__lte=timezone.now()
        ).distinct()
        
    else: # status_filter == 'new' holati
        practice_title = "Yangi So'zlarni O'rganish"
        # Foydalanuvchi uchun statusi bo'lmagan (hali ko'rilmagan) barcha kartochkalarni olish
        flashcards_to_practice = Flashcard.objects.exclude(
            user_statuses__user=user
        ).distinct()
        
    # Agar mashq uchun kartochka topilmasa, xabar berish
    if not flashcards_to_practice.exists():
        messages.info(request, f"Hozirda '{practice_title}' uchun kartochkalar mavjud emas.")
        return redirect('my_flashcards')


    # Foydalanuvchi statuslarini olish (Repetition Count uchun)
    statuses = UserFlashcardStatus.objects.filter(
        user=user,
        flashcard__in=flashcards_to_practice.values_list('id', flat=True)
    ).values('flashcard_id', 'repetition_count')
    
    status_map = {s['flashcard_id']: s['repetition_count'] for s in statuses}

    # JSON ma'lumotlarini tayyorlash
    flashcards_list = []
    for fc in flashcards_to_practice:
        repetition_count = status_map.get(fc.id, 0) 
        flashcards_list.append({
            'id': fc.id,
            # Xavfsizlik uchun bleach.clean() ishlatish
            'english_content': bleach.clean(fc.english_content, tags=[], strip=True),
            'uzbek_meaning': bleach.clean(fc.uzbek_meaning, tags=[], strip=True),
            'context_sentence': bleach.clean(fc.context_sentence, tags=[], strip=True) if fc.context_sentence else '',
            'repetition_count': repetition_count,
        })
    
    flashcards_json = json.dumps(flashcards_list)
    
    context = {
        'session_title': practice_title, 
        # flashcard_exam ni lug'at sifatida yuboramiz, chunki html shuni kutadi
        # 'id': 0 qo'shildi, chunki html'da .id ni chaqirishda xato bo'lmasligi kerak
        'flashcard_exam': {'title': practice_title, 'id': 0}, 
        'flashcards_json': flashcards_json,
        'total_flashcards': len(flashcards_list),
        'is_practice_session': True, 
    }
    return render(request, 'student/flashcard_exam.html', context)

# --- MATH (44 savol) Jadvallari ---
MATH_HIGH_CUTOFF = 11
MATH_SCALING_TABLE = { 
    'LOW': { 
        44: 680, 43: 670, 42: 660, 41: 650, 40: 640, 39: 630, 38: 620, 37: 610, 36: 600, 35: 590, 
        34: 580, 33: 570, 32: 560, 31: 550, 30: 540, 29: 530, 28: 520, 27: 510, 26: 500, 25: 490,
        24: 480, 23: 470, 22: 460, 21: 450, 20: 440, 19: 430, 18: 420, 17: 410, 16: 400, 15: 390,
        14: 380, 13: 370, 12: 360, 11: 350, 10: 340, 9: 330, 8: 320, 7: 310, 6: 300, 5: 290, 
        4: 280, 3: 270, 2: 260, 1: 250, 0: 200 
    },
    'HIGH': { 
        44: 800, 43: 790, 42: 780, 41: 770, 40: 760, 39: 750, 38: 740, 37: 730, 36: 720, 35: 710, 
        34: 700, 33: 690, 32: 680, 31: 670, 30: 660, 29: 650, 28: 640, 27: 630, 26: 620, 25: 610, 
        24: 600, 23: 590, 22: 580, 21: 570, 20: 560, 19: 550, 18: 540, 17: 530, 16: 520, 15: 510, 
        14: 500, 13: 490, 12: 480, 11: 470, 10: 460, 9: 450, 8: 440, 7: 430, 6: 420, 5: 410, 
        4: 400, 3: 390, 2: 380, 1: 370, 0: 200 
    },
}

# --- EBRW (54 savol) Jadvallari ---
EBRW_HIGH_CUTOFF = 14
EBRW_SCALING_TABLE = {
    'LOW': { 
        54: 670, 53: 660, 52: 650, 51: 640, 50: 630, 49: 620, 48: 610, 47: 600, 46: 590, 45: 580, 
        44: 570, 43: 560, 42: 550, 41: 540, 40: 530, 39: 520, 38: 510, 37: 500, 36: 490, 35: 480, 
        34: 470, 33: 460, 32: 450, 31: 440, 30: 430, 29: 420, 28: 410, 27: 400, 26: 390, 25: 380,
        24: 370, 23: 360, 22: 350, 21: 340, 20: 330, 19: 320, 18: 310, 17: 300, 16: 290, 15: 280,
        14: 270, 13: 260, 12: 250, 11: 240, 10: 230, 9: 220, 8: 210, 7: 200, 6: 200, 1: 200, 0: 200 
    },
    'HIGH': { 
        54: 800, 53: 790, 52: 780, 51: 770, 50: 760, 49: 750, 48: 740, 47: 730, 46: 720, 45: 710, 
        44: 700, 43: 690, 42: 680, 41: 670, 40: 660, 39: 650, 38: 640, 37: 630, 36: 620, 35: 610,
        34: 600, 33: 590, 32: 580, 31: 570, 30: 560, 29: 550, 28: 540, 27: 530, 26: 520, 25: 510,
        24: 500, 23: 490, 22: 480, 21: 470, 20: 460, 19: 450, 18: 440, 17: 430, 16: 420, 15: 410,
        14: 400, 13: 390, 12: 380, 11: 370, 10: 360, 9: 350, 8: 340, 7: 330, 6: 320, 5: 310, 
        4: 300, 3: 290, 2: 280, 1: 270, 0: 200 
    },
}

def get_adaptive_scaled_score(mod1_raw, total_raw, is_math=False):
    if mod1_raw is None or total_raw is None:
        return None
    
    scaling_table = MATH_SCALING_TABLE if is_math else EBRW_SCALING_TABLE
    cut_score = MATH_HIGH_CUTOFF if is_math else EBRW_HIGH_CUTOFF

    path = 'HIGH' if mod1_raw >= cut_score else 'LOW'
    scaled_score_map = scaling_table.get(path, scaling_table['LOW']) 
    
    return scaled_score_map.get(total_raw, 200)

# =========================================================================
# ⭐️ 1. VIEW_RESULT_DETAIL FUNKSIYASI (Natijalar sahifasi)
# =========================================================================

@login_required(login_url='login')
def view_result_detail(request, attempt_id):
    """
    Foydalanuvchining imtihon urinishi (UserAttempt) bo'yicha to'liq natijalarni ko'rsatadi.
    Ballarni hisoblaydi va tahlil ma'lumotlarini tayyorlaydi.
    """
    try:
        # 1. Asosiy obyektlarni yuklash
        attempt = get_object_or_404(UserAttempt, id=attempt_id, user=request.user)
    except Exception as e:
        messages.error(request, "Natija topilmadi yoki sizga tegishli emas.")
        # logger.error(f"Attempt not found: {str(e)}")
        return redirect('dashboard') 
        
    sections_qs = attempt.section_attempts.select_related('section').order_by('section__order') 
    
    # 2. To'g'ri javoblarni hisoblash uchun xarita
    correct_answers_by_section_attempt = UserAnswer.objects.filter(
        attempt_section__attempt=attempt, is_correct=True
    ).values('attempt_section__id').annotate(correct_count=Count('id'))
    correct_map = {item['attempt_section__id']: item['correct_count'] for item in correct_answers_by_section_attempt}
    
    # 3. Ballarni hisoblash uchun boshlang'ich ma'lumotlar
    ebrw_raw = {'M1': None, 'M2': None, 'total': 0}
    math_raw = {'M1': None, 'M2': None, 'total': 0}
    total_correct = 0
    total_questions = 0
    section_analysis_list = [] 
    
    # Bo'lim turlari qisqartmalari
    EBRW_M1, EBRW_M2 = 'read_write_m1', 'read_write_m2'
    MATH_M1, MATH_M2 = 'math_no_calc', 'math_calc'

    # 4. Barcha bo'limlar bo'ylab iteratsiya va raw score hisobi
    for section_attempt in sections_qs:
        section_type = section_attempt.section.section_type
        correct = correct_map.get(section_attempt.id, 0)
        section_questions = section_attempt.questions.count()

        if section_questions == 0:
            continue

        total_correct += correct
        total_questions += section_questions
        
        # Raw Scorelarni Modullarga joylash
        if section_type == EBRW_M1: ebrw_raw.update({'M1': correct, 'total': ebrw_raw['total'] + correct})
        elif section_type == EBRW_M2: ebrw_raw.update({'M2': correct, 'total': ebrw_raw['total'] + correct})
        elif section_type == MATH_M1: math_raw.update({'M1': correct, 'total': math_raw['total'] + correct})
        elif section_type == MATH_M2: math_raw.update({'M2': correct, 'total': math_raw['total'] + correct})
        
        # Savollar navigatsiyasi uchun javoblarni yuklash (minimal ma'lumot bilan)
        user_answers_for_nav = UserAnswer.objects.filter(
            attempt_section=section_attempt
        ).select_related('question').order_by('question__id')
        
        section_analysis_list.append({
            'section_attempt_id': section_attempt.id,
            'section_name': f"{section_attempt.section.get_section_type_display()} (Modul {section_attempt.section.module_number})",
            'user_answers_nav': user_answers_for_nav,
            'correct_count': correct,
            'total_count': section_questions,
        })
        
    # 5. Yakuniy SAT Ballini hisoblash
    final_ebrw_score = None
    final_math_score = None
    total_sat_score = None
    
    try:
        # get_adaptive_scaled_score funksiyasi mavjud bo'lsa hisoblaymiz
        final_ebrw_score = get_adaptive_scaled_score(ebrw_raw['M1'], ebrw_raw['total'], is_math=False)
        final_math_score = get_adaptive_scaled_score(math_raw['M1'], math_raw['total'], is_math=True)
        total_sat_score = (final_ebrw_score or 0) + (final_math_score or 0)
    except NameError:
        # Agar get_adaptive_scaled_score mavjud bo'lmasa, DB dagi qiymatni olish
        final_ebrw_score = attempt.final_ebrw_score
        final_math_score = attempt.final_math_score
        total_sat_score = attempt.final_total_score
    except TypeError:
         # Hisoblashda xato yuz bersa (None bilan ishlash va h.k.)
        final_ebrw_score = attempt.final_ebrw_score
        final_math_score = attempt.final_math_score
        total_sat_score = attempt.final_total_score

    # 6. Umumiy statistika
    total_omitted = UserAnswer.objects.filter(attempt_section__attempt=attempt, is_correct=None).count()
    total_incorrect = total_questions - total_correct - total_omitted
    total_percentage = round((total_correct / total_questions * 100)) if total_questions > 0 else 0
    
    # 7. Contextni tayyorlash va render qilish
    context = {
        'attempt': attempt,
        'section_analysis_list': section_analysis_list,
        'total_sat_score': total_sat_score, 
        'ebrw_score': final_ebrw_score,
        'math_score': final_math_score,
        'total_correct': total_correct,
        'total_incorrect': total_incorrect,
        'total_omitted': total_omitted,
        'total_percentage': total_percentage,
        'pending_message': None if attempt.is_completed else "Imtihon hali yakunlanmagan. Ballar va tahlillar taxminiy hisoblanmoqda.",
    }
    return render(request, 'student/result_detail.html', context)

# -----------------------------------------------------------------------------
# ⭐️ 2. GET_ANSWER_DETAIL_AJAX FUNKSIYASI (Savol tahlili)
# -----------------------------------------------------------------------------
@login_required(login_url='login')
def get_answer_detail_ajax(request):
    """
    AJAX so'rovi orqali bitta savolning to'liq tahlilini HTML ko'rinishida qaytaradi.
    Bu funksiya faqat JSON javob qaytaradi.
    """
    user_answer_id = request.GET.get('user_answer_id')
    if not user_answer_id:
        # AJAX javob (messages ishlatilmaydi)
        return JsonResponse({'error': 'Savol ID si berilmadi'}, status=400)

    try:
        # Foydalanuvchiga tegishli ekanligini tekshirib, javobni topish
        user_answer = UserAnswer.objects.select_related(
            'question', 'question__passage', 'question__solution', 'attempt_section__attempt'
        ).prefetch_related(
            'selected_options', 'question__options'
        ).get(id=user_answer_id, attempt_section__attempt__user=request.user)
        
        # 1. Yechim ko'rilganmi/bepulmi tekshiruvi (UserSolutionView modeliga bog'liq)
        # UserSolutionView mavjud bo'lmasa, NameError yuz beradi, shuning uchun try/except yaxshi
        try:
             solution_viewed = UserSolutionView.objects.filter(user=request.user, question=user_answer.question).exists()
        except NameError:
             solution_viewed = False
             
        is_solution_free = getattr(user_answer.question, 'is_solution_free', False)
        
        # 2. Variantlarni statusi bilan tayyorlash
        options_with_status = []
        selected_ids = set(user_answer.selected_options.values_list('id', flat=True))
        
        for index, option in enumerate(user_answer.question.options.all()):
            options_with_status.append({
                'option': option,
                'is_user_selected': option.id in selected_ids,
                'is_correct': getattr(option, 'is_correct', False),
                'letter': chr(65 + index), # A, B, C...
            })

        # 3. Contextni tayyorlash
        context = {
            'user_answer': user_answer,
            'question': user_answer.question, # savolni to'g'ridan-to'g'ri olish
            'options_with_status': options_with_status,
            'solution_viewed': solution_viewed,
            'is_solution_free': is_solution_free,
            'attempt': user_answer.attempt_section.attempt,
        }

        # 4. HTML fragmentni render qilib, JSON javobida qaytarish
        html = render_to_string('partials/answer_detail_card.html', context, request=request)
        return JsonResponse({'html': html})

    except UserAnswer.DoesNotExist:
        return JsonResponse({'error': 'Bunday javob topilmadi yoki sizga tegishli emas.'}, status=404)
    except Exception as e:
        # Ishlab chiqish vaqtida xatolikni aniq ko'rish uchun (productionda o'chirib qo'yish kerak)
        print(traceback.format_exc())
        return JsonResponse({'error': 'Serverda kutilmagan xatolik.'}, status=500)

@login_required(login_url='login')
def view_solution(request, question_id):
    """
    Foydalanuvchiga savol yechimini ko'rish uchun ruxsat beradi, kreditlarni tekshiradi va sarflaydi.
    """
    try:
        question = get_object_or_404(Question, id=question_id)
        user = request.user
        attempt_id = request.GET.get('attempt_id')
        
        if not attempt_id:
            # Agar attempt_id mavjud bo'lmasa, uni ko'rsatkichlar sahifasiga qaytarish yaxshi
            messages.error(request, "Imtihon ID'si (Attempt ID) topilmadi.")
            return redirect('dashboard')
        
        # 1. Yechim allaqachon ko'rilganmi yoki bepulmi (GLOBAL tekshiruv)
        solution_viewed = UserSolutionView.objects.filter(user=user, question=question).exists()
        is_solution_free = getattr(question, 'is_solution_free', False)

        if is_solution_free or solution_viewed:
            if not solution_viewed:
                # Agar bepul bo'lsa-yu, lekin avval yozuv bo'lmasa, uni yaratamiz
                UserSolutionView.objects.create(user=user, question=question, credit_spent=False)
                
            # messages.success(request, "Yechim bepul yoki avval ko'rilgan.")
            # Natijalar sahifasiga yo'naltiramiz
            return redirect('view_result_detail', attempt_id=attempt_id)

        # 2. Kredit tekshirish va sarflash
        # select_for_update() yordamida bir vaqtda kirishdan himoyalanamiz
        user_balance = UserBalance.objects.select_for_update().get(user=user)
        

        if user_balance.solution_view_credits > 0:
            with transaction.atomic():
                # Yechimni ko'rganlik yozuvini yaratamiz
                # Kredit sarflanganligi (credit_spent=True) ni belgilaymiz
                UserSolutionView.objects.create(user=user, question=question, credit_spent=True)
                
                # Kreditni yechamiz
                user_balance.solution_view_credits -= 1
                user_balance.save()
                
                messages.success(request, f"Yechim ko'rildi! 1 ta kredit sarflandi. Qolgan kredit: {user_balance.solution_view_credits}")
        else:
            messages.error(request, "Yechimni ko'rish uchun yetarli kredit yo'q!")
        
        return redirect('view_result_detail', attempt_id=attempt_id)

    except UserBalance.DoesNotExist:
        messages.error(request, "Foydalanuvchi balansi topilmadi. Ma’muriyat bilan bog‘laning.")
        return redirect('view_result_detail', attempt_id=request.GET.get('attempt_id') or 'dashboard')
    except Exception as e:
        # logger.error(f"view_solution xatosi: {str(e)}")
        messages.error(request, f"Yechimni ko‘rishda server xatosi yuz berdi: {e}")
        return redirect('view_result_detail', attempt_id=request.GET.get('attempt_id') or 'dashboard')
    
@login_required(login_url='login')
@user_passes_test(is_teacher, login_url='index')
def teacher_view_result_detail(request, attempt_id):
    """O'qituvchi uchun talaba natijasining batafsil ko'rinishi."""
    
    # 1. Urinishni yuklash
    try:
        attempt = get_object_or_404(UserAttempt, id=attempt_id)
    except Exception:
        messages.error(request, "Natija topilmadi.")
        return redirect('teacher_dashboard') # O'qituvchi bosh sahifasiga qaytarish

    # 2. Ruxsatni tekshirish
    if attempt.exam.teacher != request.user:
        messages.error(request, "Siz bu natijani ko'rish huquqiga ega emassiz.")
        return render(request, '403.html', {'message': "Siz bu natijani ko'rish huquqiga ega emassiz."})

    # 3. Umumiy statistika hisobi (kodda to'g'ri yozilgan)
    total_questions = 0
    total_correct_answers = 0
    
    # Ushbu qismda ma'lumotlar bazasi so'rovlarini optimallashtirish mumkin, 
    # lekin mavjud mantiq saqlanadi.
    for section_attempt in attempt.section_attempts.all():
        section = section_attempt.section
        # get_section_questions ning qanday ishlashiga bog'liq
        try:
            section_questions = get_section_questions(section, attempt.exam)
            total_questions += len(section_questions)
            # section_attempt.correct_answers_count fieldi mavjud deb hisoblanadi
            total_correct_answers += section_attempt.correct_answers_count 
        except NameError:
             # Agar get_section_questions mavjud bo'lmasa, xato bo'ladi.
             # Alternativ: total_questions = UserAnswer.objects.filter(attempt_section__attempt=attempt).count()
             total_questions = UserAnswer.objects.filter(attempt_section__attempt=attempt).count()
             total_correct_answers = UserAnswer.objects.filter(attempt_section__attempt=attempt, is_correct=True).count()
             break # Xato bo'lsa, tsikldan chiqish

    total_incorrect_answers = total_questions - total_correct_answers

    # 4. Savol-javoblarni tahlil qilish uchun yuklash
    user_answers = UserAnswer.objects.filter(attempt_section__attempt=attempt).order_by('question__id').select_related('question').prefetch_related('selected_options', 'question__options')

    # 5. Har bir javobga tahlil ma'lumotlarini qo'shish
    for user_answer in user_answers:
        options_with_status = []
        correct_options = set(user_answer.question.options.filter(is_correct=True).values_list('id', flat=True))
        selected_option_ids = set(user_answer.selected_options.values_list('id', flat=True))
        
        for index, option in enumerate(user_answer.question.options.all()):
            options_with_status.append({
                'option': option,
                'is_user_selected': option.id in selected_option_ids,
                'is_correct': option.id in correct_options,
                'letter': chr(65 + index), # A, B, C... belgisini qo'shish
            })
            
        user_answer.options_with_status = options_with_status
        user_answer.passage_text = user_answer.question.passage.text if user_answer.question.passage else None
        user_answer.is_solution_free = getattr(user_answer.question, 'is_solution_free', False) # Attribute tekshiruvi

    # 6. Contextni tayyorlash
    context = {
        'attempt': attempt,
        'user_answers': user_answers,
        'total_correct_answers': total_correct_answers,
        'total_incorrect_answers': total_incorrect_answers,
        'total_questions': total_questions,
        # ability_estimate mavjud bo'lsa
        'ability_estimate': getattr(attempt, 'ability_estimate', 'Noma‘lum'), 
    }
    return render(request, 'teacher_test_result_detail.html', context)

@login_required(login_url='login')
@user_passes_test(is_teacher, login_url='index')
def my_exams(request):
    """Ustozning o'z yaratgan imtihonlarini ko'rish va boshqarish."""
    
    # Har bir imtihon uchun bo'limlar sonini ma'lumotlar bazasida hisoblash (samarali)
    my_exams = Exam.objects.filter(teacher=request.user).annotate(
        section_count=Count('sections')
    ).order_by('-created_at')
    
    context = {'my_exams': my_exams}
    return render(request, 'exam/my_exams.html', context)

@login_required(login_url='login')
@user_passes_test(is_teacher, login_url='index')
def teacher_results(request):
    """Ustozning imtihonlari va talabalar natijalarini ko'rish."""
    
    my_exams = Exam.objects.filter(teacher=request.user).order_by('-created_at').prefetch_related('sections')
    exam_results = []
    
    for exam in my_exams:
        # N+1 muammosini hal qilish uchun optimallashtirilgan so'rov:
        attempts = UserAttempt.objects.filter(exam=exam).select_related('user').prefetch_related(
            'section_attempts' # SectionAttempt ma'lumotlarini bir so'rovda yuklaymiz
        ).order_by('-completed_at')
        
        attempt_details = []
        
        # Bu mantiq har bir urinish uchun barcha bo'lim savollarini qayta hisoblaydi.
        # Agar 'get_section_questions' ma'lumotlar bazasiga kirishni talab qilsa, 
        # bu yerda sekinlashishi mumkin. Lekin mavjud mantiqni saqlaymiz.
        all_sections = list(exam.sections.all())
        
        # Barcha bo'limlardagi umumiy savollar sonini hisoblash (Agar statik bo'lsa, bu samarali)
        try:
             total_questions_in_exam = sum(len(get_section_questions(section, exam)) for section in all_sections)
        except NameError:
             # Agar funksiya aniqlanmagan bo'lsa, xato yuz bermasligi uchun nol
             total_questions_in_exam = 0 
        
        for attempt in attempts:
            
            # Agar savollar soni 0 bo'lsa, natijani hisoblashdan qochish
            if total_questions_in_exam == 0:
                correct_answers = 0
                percentage = 0
            else:
                correct_answers = sum(section.correct_answers_count for section in attempt.section_attempts.all())
                percentage = (correct_answers / total_questions_in_exam * 100)
            
            incorrect_answers = total_questions_in_exam - correct_answers
            
            attempt_details.append({
                'attempt_id': attempt.id,
                # select_related('user') tufayli bu juda tez ishlaydi:
                'user_username': attempt.user.username,
                'correct_answers': correct_answers,
                'incorrect_answers': incorrect_answers,
                'score': attempts.final_total_score,
                'percentage': round(percentage, 2),
                'completed_at': attempt.completed_at,
            })
            
        # Urinishlari bor imtihonlarni natijalar ro'yxatiga qo'shamiz
        if attempt_details:
             exam_results.append({
                'title': exam.title,
                'attempts': attempt_details,
             })
    
    context = {'results': exam_results}
    return render(request, 'teacher_results.html', context)


def get_base_context(request):
    """Umumiy kontekst ma'lumotlarini qaytaruvchi yordamchi funksiya."""
    all_topics = Topic.objects.filter(teacher=request.user).order_by('name')
    all_subtopics = Subtopic.objects.filter(topic__teacher=request.user).order_by('name')
    all_tags = Tag.objects.all()
    return {
        'all_topics': all_topics,
        'all_subtopics': all_subtopics,
        'all_tags': all_tags,
    }

@login_required(login_url='login')
@user_passes_test(is_teacher, login_url='index')
def my_questions_home(request):
    topics = Topic.objects.filter(teacher=request.user).annotate(
        subtopic_count=Count('subtopics', distinct=True),
        question_count=Count('subtopics__questions', distinct=True)
    )
    uncategorized_questions_count = Question.objects.filter(subtopic__isnull=True, author=request.user).count()
    
    context = {
        'topics': topics,
        'uncategorized_questions_count': uncategorized_questions_count,
        **get_base_context(request)
    }
    return render(request, 'questions/my_questions_home.html', context)

@login_required(login_url='login')
@user_passes_test(is_teacher, login_url='index')
def topic_detail(request, topic_id):
    topic = get_object_or_404(Topic, id=topic_id, teacher=request.user)
    subtopics = Subtopic.objects.filter(topic=topic).annotate(question_count=Count('questions'))
    
    context = {
        'topic': topic,
        'subtopics': subtopics,
        **get_base_context(request)
    }
    return render(request, 'questions/topic_detail.html', context)

@login_required(login_url='login')
@user_passes_test(is_teacher, login_url='index')
def subtopic_questions(request, subtopic_id):
    """
    Ichki mavzuga oid savollar ro'yxatini ko'rsatadi.
    """
    subtopic = get_object_or_404(Subtopic, id=subtopic_id, topic__teacher=request.user)

    # Question, Passage, QuestionSolution, AnswerOption, Flashcard va Taglarni yuklab olamiz
    questions = Question.objects.filter(
        subtopic=subtopic,
        author=request.user
    ).select_related(
        'solution',
        'passage'
    ).prefetch_related(
        'options',
        'tags',
        'flashcards'
    ).order_by('-created_at')

    context = {
        'subtopic': subtopic,
        'questions': questions,
        # get_base_context funksiyasi mavjud bo'lsa
        # **get_base_context(request)
    }
    return render(request, 'questions/subtopic_questions.html', context)

@login_required(login_url='login')
@user_passes_test(is_teacher, login_url='index')
def uncategorized_questions(request):
    """
    Mavzulanmagan savollar ro'yxatini ko'rsatadi.
    """
    questions = Question.objects.filter(
        subtopic__isnull=True,
        author=request.user
    ).select_related(
        'solution'
    ).prefetch_related(
        Prefetch('translations', queryset=QuestionTranslation.objects.filter(language='uz')),
        Prefetch('options', queryset=AnswerOption.objects.prefetch_related(
            Prefetch('translations', queryset=AnswerOptionTranslation.objects.filter(language='uz'))
        )),
        'tags',
        'flashcards'
    )
    
    context = {
        'questions': questions,
        'uncategorized_view': True,
        **get_base_context(request)
    }
    return render(request, 'questions/uncategorized_questions.html', context)

@login_required(login_url='login')
@user_passes_test(is_teacher, login_url='index')
def delete_topic(request, topic_id):
    topic = get_object_or_404(Topic, id=topic_id, teacher=request.user)
    
    if request.method == 'POST':
        delete_type = request.POST.get('delete_type')
        if delete_type == 'move':
            target_topic_id = request.POST.get('target_topic')
            if target_topic_id:
                target_topic = get_object_or_404(Topic, id=target_topic_id, teacher=request.user)
                moved_count = Subtopic.objects.filter(topic=topic).update(topic=target_topic)
                topic.delete()
                messages.success(request, f'"{topic.name}" mavzusidagi {moved_count} ta ichki mavzu "{target_topic.name}" ga ko‘chirildi va mavzu o‘chirildi.')
            else:
                messages.error(request, "Savollarni ko'chirish uchun mavzu tanlanmadi.")
        else:
            topic.delete()
            messages.success(request, f'"{topic.name}" mavzusi va unga tegishli barcha savollar o‘chirildi.')
        
        return redirect('my_questions')

    questions_count = Question.objects.filter(subtopic__topic=topic).count()
    all_topics = Topic.objects.filter(teacher=request.user).exclude(id=topic_id)
    
    context = {
        'topic': topic,
        'questions_count': questions_count,
        'all_topics': all_topics,
    }
    return render(request, 'topic/delete_topic.html', context)

@login_required(login_url='login')
@user_passes_test(is_teacher, login_url='index')
def delete_subtopic(request, subtopic_id):
    subtopic = get_object_or_404(Subtopic, id=subtopic_id, topic__teacher=request.user)
    
    if request.method == 'POST':
        delete_type = request.POST.get('delete_type')
        if delete_type == 'move':
            target_subtopic_id = request.POST.get('target_subtopic')
            if target_subtopic_id:
                target_subtopic = get_object_or_404(Subtopic, id=target_subtopic_id, topic__teacher=request.user)
                moved_count = subtopic.questions.update(subtopic=target_subtopic)
                subtopic.delete()
                messages.success(request, f"{moved_count} ta savol '{target_subtopic.name}' ga ko'chirildi va ichki mavzu o'chirildi.")
            else:
                messages.error(request, "Savollarni ko'chirish uchun ichki mavzu tanlanmadi.")
        else:
            subtopic.delete()
            messages.success(request, "Ichki mavzu va unga tegishli barcha savollar o'chirildi.")
        
        return redirect('my_questions')
        
    questions_count = subtopic.questions.count()
    all_subtopics = Subtopic.objects.filter(topic__teacher=request.user).exclude(id=subtopic_id)
    
    context = {
        'subtopic': subtopic,
        'questions_count': questions_count,
        'all_subtopics': all_subtopics,
    }
    return render(request, 'topic/delete_subtopic.html', context)

@login_required(login_url='login')
@user_passes_test(is_teacher, login_url='index')
def create_topic(request):
    if request.method == 'POST':
        form = TopicForm(request.POST)
        if form.is_valid():
            topic = form.save(commit=False)
            topic.teacher = request.user
            topic.save()
            messages.success(request, "Mavzu muvaffaqiyatli yaratildi!")
            return redirect('my_questions')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
    else:
        form = TopicForm()
    
    context = {
        'form': form,
        'title': 'Yangi mavzu yaratish',
        **get_base_context(request)
    }
    return render(request, 'topic/create_topic.html', context)

@login_required(login_url='login')
@user_passes_test(is_teacher, login_url='index')
def edit_topic(request, topic_id):
    topic = get_object_or_404(Topic, id=topic_id, teacher=request.user)
    if request.method == 'POST':
        form = TopicForm(request.POST, instance=topic)
        if form.is_valid():
            form.save()
            messages.success(request, "Mavzu muvaffaqiyatli tahrirlandi!")
            return redirect('my_questions')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
    else:
        form = TopicForm(instance=topic)
    
    context = {
        'form': form,
        'title': 'Mavzuni tahrirlash',
        'topic': topic,
        **get_base_context(request)
    }
    return render(request, 'topic/create_topic.html', context)

@login_required(login_url='login')
@user_passes_test(is_teacher, login_url='index')
def create_subtopic(request, topic_id=None):
    initial = {}
    if topic_id:
        topic = get_object_or_404(Topic, id=topic_id, teacher=request.user)
        initial['topic'] = topic
    
    if request.method == 'POST':
        form = SubtopicForm(request.POST)
        if form.is_valid():
            subtopic = form.save(commit=False)
            if subtopic.topic.teacher != request.user:
                messages.error(request, "Siz faqat o'zingiz yaratgan mavzularga ichki mavzu qo'shishingiz mumkin.")
                return render(request, 'create_subtopic.html', {'form': form, 'title': 'Yangi ichki mavzu yaratish'})
            subtopic.save()
            messages.success(request, "Ichki mavzu muvaffaqiyatli yaratildi!")
            return redirect('topic_detail', topic_id=subtopic.topic.id)
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
    else:
        form = SubtopicForm(initial=initial)
        form.fields['topic'].queryset = Topic.objects.filter(teacher=request.user)
    
    context = {
        'form': form,
        'title': 'Yangi ichki mavzu yaratish',
        'topic_id': topic_id,
        **get_base_context(request)
    }
    return render(request, 'topic/create_subtopic.html', context)

@login_required(login_url='login')
@user_passes_test(is_teacher, login_url='index')
def edit_subtopic(request, subtopic_id):
    subtopic = get_object_or_404(Subtopic, id=subtopic_id, topic__teacher=request.user)
    if request.method == 'POST':
        form = SubtopicForm(request.POST, instance=subtopic)
        if form.is_valid():
            if form.cleaned_data['topic'].teacher != request.user:
                messages.error(request, "Siz faqat o'zingiz yaratgan mavzularga ichki mavzu qo'shishingiz mumkin.")
                return render(request, 'create_subtopic.html', {'form': form, 'title': 'Ichki mavzuni tahrirlash'})
            form.save()
            messages.success(request, "Ichki mavzu muvaffaqiyatli tahrirlandi!")
            return redirect('topic_detail', topic_id=subtopic.topic.id)
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
    else:
        form = SubtopicForm(instance=subtopic)
        form.fields['topic'].queryset = Topic.objects.filter(teacher=request.user)
    
    context = {
        'form': form,
        'title': 'Ichki mavzuni tahrirlash',
        'subtopic': subtopic,
        **get_base_context(request)
    }
    return render(request, 'topic/create_subtopic.html', context)

@login_required(login_url='login')
@user_passes_test(is_teacher, login_url='index')
def move_questions(request, subtopic_id):
    subtopic = get_object_or_404(Subtopic, id=subtopic_id, topic__teacher=request.user)
    
    if request.method == 'POST':
        target_subtopic_id = request.POST.get('target_subtopic')
        if target_subtopic_id:
            target_subtopic = get_object_or_404(Subtopic, id=target_subtopic_id, topic__teacher=request.user)
            moved_count = subtopic.questions.update(subtopic=target_subtopic)
            messages.success(request, f"{moved_count} ta savol '{target_subtopic.name}' ga ko'chirildi.")
        else:
            messages.error(request, "Ko'chirish uchun ichki mavzu tanlanmadi.")
    
    return redirect('subtopic_questions', subtopic_id=subtopic_id)

@login_required(login_url='login')
@user_passes_test(is_teacher, login_url='index')
def list_flashcards(request):
    """Barcha flashcardlarni ko'rsatish. Foydalanuvchi tomonidan filterlash shart emas."""
    flashcards = Flashcard.objects.all().order_by('-created_at')
    return render(request, 'flashcards/list_flashcards.html', {'flashcards': flashcards})

@login_required(login_url='login')
@user_passes_test(is_teacher, login_url='index')
def create_flashcard(request):
    if request.method == 'POST':
        form = FlashcardForm(request.POST, request.FILES)
        if form.is_valid():
            flashcard = form.save(commit=False)
            flashcard.author = request.user # Muallifni avtomatik bog'laymiz
            flashcard.save()
            messages.success(request, "Flashcard muvaffaqiyatli yaratildi!")
            return redirect('list_flashcards')
        # Agar form valid bo'lmasa, xatolar bilan qayta render qilinadi
    else:
        form = FlashcardForm()
    
    return render(request, 'flashcards/create_flashcard.html', {'form': form})

@login_required(login_url='login')
@user_passes_test(is_teacher, login_url='index')
def edit_flashcard(request, pk):
    """Flashcardni tahrirlash."""
    # Barcha o'qituvchilar tahrirlash huquqiga ega deb hisoblaymiz.
    flashcard = get_object_or_404(Flashcard, pk=pk)
    if request.method == 'POST':
        form = FlashcardForm(request.POST, request.FILES, instance=flashcard)
        if form.is_valid():
            form.save()
            messages.success(request, "Flashcard muvaffaqiyatli tahrirlandi!")
            return redirect('list_flashcards')
    else:
        form = FlashcardForm(instance=flashcard)
    return render(request, 'flashcards/edit_flashcard.html', {'form': form})

@login_required(login_url='login')
@user_passes_test(is_teacher, login_url='index')
def delete_flashcard(request, pk):
    """Flashcardni o'chirish."""
    flashcard = get_object_or_404(Flashcard, pk=pk)
    if request.method == 'POST':
        flashcard.delete()
        messages.success(request, "Flashcard muvaffaqiyatli o'chirildi.")
        return redirect('list_flashcards')
    
    messages.error(request, "Ruxsat etilmagan so'rov usuli.")
    return redirect('list_flashcards')

@login_required(login_url='login')
def add_question(request):
    """
    Yangi savol qo'shish. SAT Digital formatiga mos, IRT parametrlari va yechimlar bilan.
    Faqat o'qituvchilar uchun ruxsat beriladi.
    """
    if not is_teacher(request.user):
        messages.error(request, "Faqat o'qituvchilar savol qo'shishi mumkin!")
        return redirect('index')

    if request.method == 'POST':
        form = QuestionForm(request.POST, request.FILES)
        answer_option_formset = AnswerOptionFormSet(request.POST, prefix='options', queryset=AnswerOption.objects.none())

        if form.is_valid() and answer_option_formset.is_valid():
            with transaction.atomic():
                # Savolni saqlash
                question = form.save(commit=False)
                question.author = request.user
                question.save()
                form.save_m2m()

                answer_format = form.cleaned_data['answer_format']
                
                if answer_format in ['single', 'multiple']:
                    valid_options = []
                    correct_options = []
                    
                    # Barcha formsetlarni tekshirish
                    for option_form in answer_option_formset.forms:
                        if option_form.cleaned_data and not option_form.cleaned_data.get('DELETE', False):
                            text = option_form.cleaned_data.get('text', '').strip()
                            if text:  # Faqat bo'sh bo'lmagan matnlarni qo'shamiz
                                valid_options.append(text)
                                if option_form.cleaned_data.get('is_correct', False):
                                    correct_options.append(text)
                    
                    # Validatsiya
                    if len(valid_options) < 2:
                        messages.error(request, "Kamida 2 ta javob varianti kiritilishi shart!")
                        logger.error(f"Valid options: {valid_options}")
                        return render(request, 'questions/add_questions.html', {
                            'form': form,
                            'answer_option_formset': answer_option_formset
                        })

                    if answer_format == 'single' and len(correct_options) != 1:
                        messages.error(request, "Yagona javob formatida faqat bitta to'g'ri javob tanlanishi kerak!")
                        logger.error(f"Correct options: {correct_options}")
                        return render(request, 'questions/add_questions.html', {
                            'form': form,
                            'answer_option_formset': answer_option_formset
                        })

                    if answer_format == 'multiple' and len(correct_options) == 0:
                        messages.error(request, "Bir nechta javob formatida kamida bitta to'g'ri javob tanlanishi kerak!")
                        logger.error(f"Correct options: {correct_options}")
                        return render(request, 'questions/add_questions.html', {
                            'form': form,
                            'answer_option_formset': answer_option_formset
                        })

                    # Eski javob variantlarini o'chirish
                    AnswerOption.objects.filter(question=question).delete()

                    # Yangi javob variantlarini saqlash
                    for option_form in answer_option_formset.forms:
                        if option_form.cleaned_data and not option_form.cleaned_data.get('DELETE', False):
                            text = option_form.cleaned_data.get('text', '').strip()
                            if text:  # Faqat bo'sh bo'lmagan matnlarni saqlaymiz
                                AnswerOption.objects.create(
                                    question=question,
                                    text=bleach.clean(text),
                                    is_correct=option_form.cleaned_data.get('is_correct', False)
                                )

                elif answer_format == 'short_answer':
                    correct_short_answer = form.cleaned_data.get('correct_short_answer', '').strip()
                    if not correct_short_answer:
                        messages.error(request, "Qisqa javob formatida to'g'ri javob kiritilishi shart!")
                        return render(request, 'questions/add_questions.html', {
                            'form': form,
                            'answer_option_formset': answer_option_formset
                        })
                    question.correct_short_answer = bleach.clean(correct_short_answer)
                    question.save()

                hint = form.cleaned_data.get('hint', '').strip()
                detailed_solution = form.cleaned_data.get('detailed_solution', '').strip()
                if hint or detailed_solution:
                    QuestionSolution.objects.create(
                        question=question,
                        hint=bleach.clean(hint),
                        detailed_solution=bleach.clean(detailed_solution)
                    )

            messages.success(request, "Savol muvaffaqiyatli qo'shildi!")
            logger.info(f"Savol ID {question.id} muvaffaqiyatli saqlandi, javob variantlari: {valid_options}")
            if 'save_and_add_another' in request.POST:
                return redirect('add_question')
            return redirect('my_questions')
        else:
            messages.error(request, "Savolni qo'shishda xatolik yuz berdi. Iltimos, ma'lumotlarni tekshiring.")
            logger.error(f"Form errors: {form.errors}, Formset errors: {answer_option_formset.errors}")
    else:
        form = QuestionForm()
        answer_option_formset = AnswerOptionFormSet(prefix='options', queryset=AnswerOption.objects.none())

    return render(request, 'questions/add_questions.html', {
        'form': form,
        'answer_option_formset': answer_option_formset
    })

@login_required(login_url='login')
@user_passes_test(is_teacher, login_url='index')
def edit_question(request, question_id):
    question = get_object_or_404(Question, id=question_id, author=request.user)
    
    initial_data = {
        'hint': question.solution.hint if hasattr(question, 'solution') else '',
        'detailed_solution': question.solution.detailed_solution if hasattr(question, 'solution') else '',
    }

    if request.method == 'POST':
        form = QuestionForm(request.POST, request.FILES, instance=question)
        answer_format = request.POST.get('answer_format')

        if form.is_valid():
            with transaction.atomic():
                question = form.save(commit=False)
                question.author = request.user

                # Short answer format
                if answer_format == 'short_answer':
                    correct_short_answer = bleach.clean(request.POST.get('correct_short_answer', ''))
                    if not correct_short_answer:
                        messages.error(request, "Qisqa javob formatida to'g'ri javob kiritilishi shart!")
                        return render(request, 'questions/edit_question.html', {'form': form, 'question': question})
                    question.correct_short_answer = correct_short_answer
                else:
                    question.correct_short_answer = None

                question.save()
                form.save_m2m()

                # Clear existing answer options and create new ones
                if answer_format in ['single', 'multiple']:
                    question.answeroption_set.all().delete()  # Use answeroption_set instead of options (unless related_name='options' is defined)
                    option_texts = request.POST.getlist('option_text')
                    correct_indices = request.POST.getlist('is_correct')
                    valid_options = [text for text in option_texts if text.strip()]

                    if len(valid_options) < 2:
                        messages.error(request, "Kamida 2 ta javob varianti kiritilishi shart!")
                        return render(request, 'questions/edit_question.html', {'form': form, 'question': question})

                    if answer_format == 'single' and len(correct_indices) != 1:
                        messages.error(request, "Yagona javob formatida faqat bitta to'g'ri javob tanlanishi kerak!")
                        return render(request, 'questions/edit_question.html', {'form': form, 'question': question})

                    if answer_format == 'multiple' and len(correct_indices) == 0:
                        messages.error(request, "Bir nechta javob formatida kamida bitta to'g'ri javob tanlanishi kerak!")
                        return render(request, 'questions/edit_question.html', {'form': form, 'question': question})

                    for i, option_text in enumerate(option_texts):
                        if option_text.strip():
                            is_correct = str(i + 1) in correct_indices
                            cleaned_option_text = bleach.clean(option_text)
                            AnswerOption.objects.create(
                                question=question,
                                text=cleaned_option_text,
                                is_correct=is_correct
                            )

                # Update or create solution
                hint = bleach.clean(form.cleaned_data.get('hint', ''))
                detailed_solution = bleach.clean(form.cleaned_data.get('detailed_solution', ''))
                solution, created = QuestionSolution.objects.get_or_create(question=question)
                solution.hint = hint
                solution.detailed_solution = detailed_solution
                solution

@login_required
def search_flashcards_api(request):
    query = request.GET.get('q', '')
    if query:
        flashcards = Flashcard.objects.filter(
            Q(english_content__icontains=query) | Q(uzbek_meaning__icontains=query)
        ).order_by('english_content')
    else:
        flashcards = Flashcard.objects.all().order_by('-created_at')[:20]

    results = []
    for fc in flashcards:
        english_cleaned = clean(fc.english_content, tags=[], strip=True)
        uzbek_cleaned = clean(fc.uzbek_meaning, tags=[], strip=True)
        text_to_display = f"{english_cleaned} - {uzbek_cleaned}"
        results.append({
            'id': fc.id,
            'text': text_to_display
        })

    return JsonResponse({'results': results})

@login_required(login_url='login')
@user_passes_test(is_teacher, login_url='index')
def delete_question(request, question_id):
    """Savolni o'chirish."""
    question = get_object_or_404(Question, id=question_id, author=request.user)
    
    # Savolni o'chirgandan so'ng qayerga qaytishni aniqlash
    # Subtopic mavjud bo'lsa, o'sha mavzuga qaytish
    redirect_url = 'my_questions'
    if question.subtopic:
        redirect_url = 'subtopic_questions'
        redirect_args = [question.subtopic.id]
    
    if request.method == 'POST':
        question.delete()
        messages.success(request, "Savol muvaffaqiyatli o'chirildi!")
        
        # O'chirilgandan so'ng to'g'ri sahifaga yo'naltirish
        if question.subtopic:
            return redirect('subtopic_questions', subtopic_id=question.subtopic.id)
        else:
            return redirect('my_questions')
            
    return redirect(redirect_url, *redirect_args)

@login_required(login_url='login')
@user_passes_test(is_teacher, login_url='index')
def upload_image(request):
    """TinyMCE rasm yuklashlarini qayta ishlash."""
    if request.method == 'POST' and request.FILES.get('file'):
        file = request.FILES['file']
        file_name = default_storage.save(f'questions/{file.name}', file)
        file_url = default_storage.url(file_name)
        return JsonResponse({'location': file_url})
    return JsonResponse({'error': 'Noto\'g\'ri so\'rov'}, status=400)

@login_required
@user_passes_test(is_teacher)
def passage_list(request):
    """O'qituvchiga tegishli barcha 'passage'lar ro'yxatini ko'rsatadi."""
    passages = Passage.objects.filter(author=request.user).order_by('-created_at')
    return render(request, 'passage/passage_list.html', {'passages': passages})

@login_required
@user_passes_test(is_teacher)
def add_passage(request):
    """Yangi 'passage' yaratish uchun funksiya."""
    if request.method == 'POST':
        form = PassageForm(request.POST)
        if form.is_valid():
            passage = form.save(commit=False)
            passage.author = request.user
            passage.save()
            messages.success(request, "Yangi matn muvaffaqiyatli qo'shildi!")
            return redirect('passage_list')
    else:
        form = PassageForm()
    return render(request, 'passage/add_passage.html', {'form': form})

@login_required
@user_passes_test(is_teacher)
def edit_passage(request, pk):
    """Mavjud 'passage'ni tahrirlash uchun funksiya."""
    passage = get_object_or_404(Passage, pk=pk, author=request.user)
    if request.method == 'POST':
        form = PassageForm(request.POST, instance=passage)
        if form.is_valid():
            form.save()
            messages.success(request, "Matn muvaffaqiyatli tahrirlandi!")
            return redirect('passage_list')
    else:
        form = PassageForm(instance=passage)
    return render(request, 'passage/edit_passage.html', {'form': form, 'passage': passage})

@login_required
@user_passes_test(is_teacher)
def delete_passage(request, pk):
    """'Passage'ni o'chirish uchun funksiya."""
    passage = get_object_or_404(Passage, pk=pk, author=request.user)
    if request.method == 'POST':
        passage.delete()
        messages.success(request, "Matn muvaffaqiyatli o'chirildi.")
        return redirect('passage_list')
    return render(request, 'passage/delete_passage.html', {'passage': passage})

# =========================================================================
# ⭐️ 1. ACHIEVEMENTS_VIEW (Yutuqlar, Nishonlar, Missiyalar, Liderlar)
# =========================================================================

@login_required
def achievements_view(request):
    """
    Foydalanuvchining barcha yutuqlari, missiyalari va liderlar doskasi statistikasini ko'rsatadi.
    Yuqoridagi ikki xil mantiqni birlashtiramiz va haftalik hisob-kitobni saqlaymiz.
    """
    user = request.user
    
    # 1. Joriy hafta raqamini aniqlash
    # isocalendar()[1] ISO hafta raqamini beradi
    current_week = timezone.now().isocalendar()[1] 

    # 2. Nishonlar (Badges) va keyingi nishonni topish
    all_badges = Badge.objects.all().order_by('title')
    earned_badge_ids = set(UserBadge.objects.filter(user=user).values_list('badge_id', flat=True))

    next_badge_to_earn = None
    # Qo'lga kiritilmagan eng birinchi nishonni topamiz
    for badge in all_badges:
        if badge.id not in earned_badge_ids:
            next_badge_to_earn = badge
            break

    # 3. Joriy Missiyalar (Missions) progressi
    # UserMissionProgress modeli orqali yoki dinamik hisoblash orqali (ikkinchi mantiqni qoldiramiz)
    try:
        mission_progress = UserMissionProgress.objects.get(user=user)
    except UserMissionProgress.DoesNotExist:
         # Agar model mavjud bo'lmasa, dinamik hisob-kitob
         mission_progress = {
             'exam_attempts_completed': UserAttempt.objects.filter(user=user, is_completed=True).count(),
             'highest_score': UserAttempt.objects.filter(user=user, is_completed=True).aggregate(max_score=Max('attempts__final_total_score'))['max_score'] or 0,
         }
         
    # 4. Liderlar Doskasi (Leaderboards)
    
    # LeaderboardEntry modeli bo'yicha hisoblash (samaraliroq):
    performance_leaderboard = LeaderboardEntry.objects.filter(
        leaderboard_type='performance',
        week_number=current_week
    ).select_related('user').order_by('-score')[:10] # Top 10
    
    effort_leaderboard = LeaderboardEntry.objects.filter(
        leaderboard_type='effort',
        week_number=current_week
    ).select_related('user').order_by('-score')[:10] # Top 10

    context = {
        'all_badges': all_badges,
        'earned_badge_ids': earned_badge_ids,
        'next_badge_to_earn': next_badge_to_earn,
        'mission_progress': mission_progress,
        'performance_leaderboard': performance_leaderboard,
        'effort_leaderboard': effort_leaderboard,
        'current_week': current_week,
    }
    return render(request, 'student/achievements.html', context)

# =========================================================================
# ⭐️ 2. PROCESS_PURCHASE_VIEW (Xaridni Boshlash)
# =========================================================================

@login_required
def process_purchase_view(request, purchase_type, item_id):
    """
    Yangi xarid obyekti yaratadi va foydalanuvchini skrinshot yuklash sahifasiga yo'naltiradi.
    """
    user = request.user
    item = None
    
    if purchase_type == 'subscription':
        item = get_object_or_404(SubscriptionPlan, id=item_id)
    elif purchase_type == 'package':
        item = get_object_or_404(ExamPackage, id=item_id)
    else:
        messages.error(request, "Xarid turida xatolik. Noto‘g‘ri tur ko‘rsatilgan.")
        return redirect('price') # 'price' url nomi mavjud deb hisoblanadi

    # Yangi xarid obyektini yaratish
    # Tranzaksiya ichida yaratish shart emas, chunki bu faqat pending yozuv yaratish
    purchase = Purchase.objects.create(
        user=user,
        purchase_type=purchase_type,
        package=item if purchase_type == 'package' else None,
        subscription_plan=item if purchase_type == 'subscription' else None,
        amount=item.price,
        final_amount=item.price, # Chegirma logikasi qo'shilishi mumkin
        status='pending'
    )
    
    messages.info(request, f"'{item.name}' xaridi uchun to‘lov kutilyapti. Iltimos, to‘lov skrinshotini yuboring.")

    # Foydalanuvchini skrinshot yuklash sahifasiga yo'naltirish
    return redirect('upload_screenshot', purchase_id=purchase.id)

# =========================================================================
# ⭐️ 3. UPLOAD_SCREENSHOT_VIEW (Skrinshotni Yuklash)
# =========================================================================

@login_required
def upload_screenshot_view(request, purchase_id):
    """
    Foydalanuvchining to'lov skrinshotini yuklash formasini ko'rsatadi va qabul qiladi.
    """
    # 1. Xarid obyektini tekshirib yuklash
    purchase = get_object_or_404(Purchase, id=purchase_id, user=request.user)

    if purchase.status != 'pending':
        messages.info(request, "Bu xarid bo'yicha ma'lumot allaqachon yuborilgan va tekshirilmoqda yoki tasdiqlangan.")
        return redirect('dashboard') 

    # 2. POST so'rovi
    if request.method == 'POST':
        # form instance'ga purchase obyektini bog'laymiz
        form = ScreenshotUploadForm(request.POST, request.FILES, instance=purchase) 
        if form.is_valid():
            purchase = form.save(commit=False)
            purchase.status = 'moderation' # Tasdiqlash uchun statusni o'zgartiramiz
            purchase.save()
            
            messages.success(request, "To'lov ma'lumotlaringiz qabul qilindi. Tez orada tasdiqlanadi!")
            return redirect('dashboard')
        else:
            # Formada xato bo'lsa, xatolikni ko'rsatish
            messages.error(request, "Xato: Iltimos, barcha maydonlarni to‘g‘ri to‘ldiring.")
    else:
        # 3. GET so'rovi (Formani ko'rsatish)
        form = ScreenshotUploadForm(instance=purchase)

    # Admin panelidan sozlamalarni olish (Bank rekvizitlari uchun)
    # objects.first() bu yechim bo'lsa, uni saqlaymiz
    site_settings = SiteSettings.objects.first()

    context = {
        'form': form,
        'purchase': purchase,
        # Xarid qilingan ob'ektni olish
        'item': purchase.subscription_plan or purchase.package, 
        'site_settings': site_settings,
    }
    return render(request, 'student/upload_screenshot.html', context)

def get_section_questions(section, exam):
    """Bo'lim uchun savollar ro'yxatini hisoblash."""
    section_questions = []
    static_questions = section.static_questions.all().select_related('question')
    section_questions.extend([sq.question for sq in static_questions])
    topic_rules = section.topic_rules.all()
    for rule in topic_rules:
        topic_questions = Question.objects.filter(
            subtopic__topic=rule.topic,
            author=exam.teacher
        )[:rule.questions_count]
        section_questions.extend(topic_questions)
    subtopic_rules = section.subtopic_rules.all()
    for rule in subtopic_rules:
        subtopic_questions = Question.objects.filter(
            subtopic=rule.subtopic,
            author=exam.teacher
        )[:rule.questions_count]
        section_questions.extend(subtopic_questions)
    return section_questions
