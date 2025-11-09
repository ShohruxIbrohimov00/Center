from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate, update_session_auth_hash
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.db.models import Sum, Count, Max, Min, F, Q, Window, Avg,Case,IntegerField,When,Value,Subquery, OuterRef
from django.db import transaction
from django.db.models import Prefetch, Count
from datetime import datetime
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.template.loader import render_to_string
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.views.decorators.http import require_POST
from django.db.models.functions import Coalesce, Rank
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError
from django.conf import settings
from datetime import timedelta
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.http import require_POST
from django.db import transaction
import string 
import html
from django.template.loader import render_to_string 
from django.forms import formset_factory
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

def is_admin(user):
    return user.is_authenticated and user.role == 'admin'

# ==========================================================
# RO'YXATDAN O'TISH, KIRISH VA CHIQISH FUNKSIYALARI
# ==========================================================

def signup_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard',slug=request.user.center.slug)
    
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, f"Xush kelibsiz, {user.username}! Akkauntingiz muvaffaqiyatli yaratildi.")
            return redirect('dashboard',slug=request.user.center.slug)
        else:
            # Forma xato bo'lsa, foydalanuvchiga umumiy xabar beramiz.
            # Aniq xatolar shablonning o'zida `form.errors` orqali ko'rsatiladi.
            messages.error(request, "Iltimos, formadagi xatoliklarni to'g'rilang.")
    else:
        form = SignUpForm()
        
    return render(request, 'registration/signup.html', {'form': form})

def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard',slug=request.user.center.slug)
        
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
            return redirect('dashboard',slug=request.user.center.slug)
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
        # 🔔 TUZATISH 🔔: Avval center mavjudligini tekshiramiz
        if request.user.center:
            # Markaz mavjud bo'lsa, o'sha markazning dashboardiga yo'naltiramiz
            return redirect('dashboard', slug=request.user.center.slug)
        else:
            # Markaz mavjud bo'lmasa, uni tanlash/o'rnatish sahifasiga yo'naltiramiz
            # Iltimos, bu yerga loyihangizdagi tegishli URL nomini yozing.
            # Taxminiy URL: 'profile_update', 'center_selection', yoki 'index' (qayta yuklanish)
            return redirect('profile') # 👈 O'zingizning URL nomingizni qo'ying!
            
    # Agar foydalanuvchi tizimga kirmagan bo'lsa
    return render(request, 'index.html')

# ==========================================================
# PROFIL VA PAROLNI O'ZGARTIRISH
# ==========================================================

@login_required(login_url='login')
def profile_view(request, slug): # <-- SLUG argumenti qo'shildi!
    """Profil sahifasini ko'rsatadi va ma'lumotlarni tahrirlashni boshqaradi."""
    
    # 1. MARKAZNI TEKSHIRISH (Dashboard'dagi kabi xavfsizlik va 404 xatosini oldini olish)
    # Agar slug bo'yicha markaz topilmasa, avtomatik ravishda 404 beriladi.
    center = get_object_or_404(Center, slug=slug)

    # 2. Xavfsizlik tekshiruvi: Foydalanuvchi shu markazga bog'langanmi?
    if request.user.center is None or request.user.center != center:
        messages.error(request, "Bu markaz profiliga kirish huquqingiz yo‘q.")
        
        # Kirish huquqi yo'q bo'lsa, foydalanuvchini uning o'z dashboardiga yuborishga harakat qiling.
        # Agar user.center None bo'lsa, bu yerda "AttributeError" xavfi bor, shuning uchun shartli redirect qilamiz
        if request.user.center:
            return redirect('dashboard', slug=request.user.center.slug)
        else:
             return redirect('index') # Yoki umumiy/markazsiz sahifaga
            
    # --- Asosiy mantiq ---
    
    if request.method == 'POST':
        # Eslatma: ProfileUpdateForm modelini shu yerda mavjud deb hisoblaymiz
        form = ProfileUpdateForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Profilingiz muvaffaqiyatli yangilandi.")
            
            # POST dan keyin o'sha sahifaga qaytishda SLUG berish majburiy
            return redirect('profile', slug=center.slug) 
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
        'center': center, # Kontekstga center'ni qo'shishni unutmang
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

def dashboard_redirect_view(request):
    """
    Tizimga kirishdan keyin LOGIN_REDIRECT_URL tomonidan chaqiriladigan yordamchi view.
    Foydalanuvchining center slug'ini aniqlab, to'g'ri dashboard URLiga yo'naltiradi.
    """
    # 1. Foydalanuvchi kirmagan bo'lsa (ehtiyot chorasi)
    if not request.user.is_authenticated:
        return redirect('login') 
        
    center_slug = None
    
    # 2. Slugni aniqlash
    # (Foydalanuvchi Markazga ega bo'lsa va Markaz slug'ga ega bo'lsa)
    if hasattr(request.user, 'center') and request.user.center:
        center_slug = request.user.center.slug

    # 3. Yo'naltirish
    if center_slug:
        # ✅ To'g'ri slug bilan asl 'dashboard' ga yo'naltiramiz
        return redirect(reverse('dashboard', kwargs={'slug': center_slug}))
    else:
        # Agar center slug topilmasa, xavfsiz joyga (masalan, umumiy index sahifasi)
        return redirect('index')

@login_required(login_url='login')
def dashboard_view(request, slug):
    """
    Foydalanuvchining shaxsiy kabineti – faqat o‘z markazida
    """
    # 1. MARKAZ TEKSHIRISH
    center = get_object_or_404(Center, slug=slug)
    if request.user.center is None or request.user.center != center:
        messages.error(request, "Bu markazga kirish huquqingiz yo‘q.")
        return redirect('index')

    user = request.user
    
    # --- "Aqlli Kun Tartibi" ---
    agenda_items = []
    review_needed_count = 0 
    try:
        from .models import UserFlashcardStatus, UserAttempt, Exam
        
        review_needed_count = UserFlashcardStatus.objects.filter(
            user=user, next_review_at__lte=timezone.now()
        ).count()
        if review_needed_count > 0:
            agenda_items.append({
                'priority': 1,
                'icon': 'brain',
                'title': f"{review_needed_count} ta so'zni takrorlang",
                'description': "Spaced repetition bo'yicha eslatish vaqti keldi.",
                'url': reverse('my_flashcards', kwargs={'slug': slug})
            })
    except Exception as e:
        logger.error(f"Flashcard agenda error for {user.id}: {e}")

    try:
        latest_attempt = UserAttempt.objects.filter(
            user=user, is_completed=True
        ).order_by('-completed_at').first()
        if latest_attempt:
            agenda_items.append({
                'priority': 2,
                'icon': 'chart',
                'title': "Oxirgi imtihonni tahlil qiling",
                'description': f"'{latest_attempt.exam.title}'dagi xatolaringiz ustida ishlang.",
                'url': reverse('view_result_detail', kwargs={'slug': slug, 'attempt_id': latest_attempt.id})
            })
            
        attempted_exam_ids = UserAttempt.objects.filter(user=user).values_list('exam_id', flat=True)
        new_exam_to_start = Exam.objects.filter(
            is_active=True, center=center
        ).exclude(id__in=attempted_exam_ids).order_by('?').first()
        if new_exam_to_start:
            agenda_items.append({
                'priority': 3,
                'icon': 'rocket',
                'title': "Yangi imtihonni boshlang",
                'description': f"'{new_exam_to_start.title}' bilan bilimingizni sinab ko'ring.",
                'url': reverse('exam_detail', kwargs={'slug': slug, 'exam_id': new_exam_to_start.id})
            })
    except Exception as e:
        logger.error(f"Exam agenda error for {user.id}: {e}")

    agenda_items = sorted(agenda_items, key=lambda x: x['priority'])[:3]

    # --- "Haftalik Progress" ---
    today = timezone.now().date()
    seven_days_ago = today - timedelta(days=6)
    date_range = [seven_days_ago + timedelta(days=i) for i in range(7)]
    chart_labels = json.dumps([d.strftime("%b %d") for d in date_range])
    
    try:
        exam_scores = UserAttempt.objects.filter(
            user=user, is_completed=True, completed_at__date__range=[seven_days_ago, today]
        ).values('completed_at__date').annotate(avg_score=Avg('final_total_score')).order_by('completed_at__date')
        score_map = {item['completed_at__date']: item['avg_score'] for item in exam_scores}
        exam_score_data = json.dumps([round(score_map.get(d, 0)) for d in date_range])
    except Exception:
        exam_score_data = json.dumps([0] * 7)

    try:
        flashcard_reviews = UserFlashcardStatus.objects.filter(
            user=user, last_reviewed_at__date__range=[seven_days_ago, today]
        ).values('last_reviewed_at__date').annotate(review_count=Count('id')).order_by('last_reviewed_at__date')
        review_map = {item['last_reviewed_at__date']: item['review_count'] for item in flashcard_reviews}
        flashcard_data = json.dumps([review_map.get(d, 0) for d in date_range])
    except Exception as e:
        logger.error(f"Flashcard chart error: {e}")
        flashcard_data = json.dumps([0] * 7)

    # --- "Liderlar Doskasi" – faqat o‘z markazidagi o‘quvchilar
    try:
        leaderboard_users = CustomUser.objects.filter(
            center=center
        ).annotate(
            max_score=Max('attempts__final_total_score')
        ).filter(max_score__isnull=False).order_by('-max_score')[:5]
        
        user_rank = None
        if user.center == center:
            user_with_rank = CustomUser.objects.filter(
                center=center
            ).annotate(
                max_score=Max('attempts__final_total_score'),
                rank=Window(expression=Rank(), order_by=F('max_score').desc())
            ).filter(id=user.id).values('rank').first()
            if user_with_rank:
                user_rank = user_with_rank['rank']
    except Exception as e:
        logger.error(f"Leaderboard error: {e}")
        leaderboard_users = []
        user_rank = None

    # --- Umumiy Statistika ---
    try:
        stats = UserAttempt.objects.filter(user=user, is_completed=True).aggregate(
            highest_score=Coalesce(Max('final_total_score'), 0),
            completed_exam_count=Count('exam', distinct=True)
        )
    except Exception:
        stats = {'highest_score': 0, 'completed_exam_count': 0}
        
    try:
        learned_flashcards_count = UserFlashcardStatus.objects.filter(user=user, status='learned').count()
    except Exception:
        learned_flashcards_count = 0

    context = {
        'center': center,
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

@login_required(login_url='login')
def completed_exams_view(request, slug):
    """
    Tugallangan imtihonlar – faqat o‘z markazida
    """
    # 1. MARKAZ TEKSHIRISH
    center = get_object_or_404(Center, slug=slug)
    if request.user.center is None or request.user.center != center:
        messages.error(request, "Bu sahifaga kirish huquqingiz yo‘q.")
        return redirect('index')

    user = request.user
    
    # 2. Tugallangan imtihonlar (faqat o‘z markazidagi)
    completed_exam_ids = UserAttempt.objects.filter(
        user=user, is_completed=True, exam__center=center
    ).values_list('exam_id', flat=True).distinct()

    exam_results = []
    
    for exam_id in completed_exam_ids:
        try:
            exam = Exam.objects.get(id=exam_id, center=center)
            
            attempts_qs = UserAttempt.objects.filter(user=user, exam=exam, is_completed=True)
            
            exam_sections_agg = exam.sections.aggregate(
                total_duration=Sum('duration_minutes'),
                total_questions=Sum('max_questions'),
                section_count=Count('id')
            )

            best_attempt = attempts_qs.order_by('-final_total_score', '-completed_at').first()
            latest_attempt = attempts_qs.order_by('-completed_at').first()
            
            has_flashcard_exam = hasattr(exam, 'flashcard_exam')
            
            can_start_exam = not exam.is_premium or (
                UserSubscription.objects.filter(user=user, end_date__gt=timezone.now()).exists() or
                UserBalance.objects.filter(user=user, exam_credits__gt=0).exists()
            )

            exam_results.append({
                'exam': exam,
                'attempt_count': attempts_qs.count(),
                'best_attempt': best_attempt,
                'latest_attempt': latest_attempt,
                'has_flashcard_exam': has_flashcard_exam,
                'can_start_exam': can_start_exam,
                'total_duration': exam_sections_agg['total_duration'] or 0,
                'total_questions': exam_sections_agg['total_questions'] or 0,
                'section_count': exam_sections_agg['section_count'] or 0,
            })
        except Exam.DoesNotExist:
            continue
        except Exception as e:
            logger.error(f"Error in completed_exams: {e}")
            continue

    top_results = sorted(
        exam_results, 
        key=lambda x: x['latest_attempt'].completed_at if x['latest_attempt'] and x['latest_attempt'].completed_at else timezone.datetime.min, 
        reverse=True
    )
    recent_results = top_results[:3]

    context = {
        'center': center,
        'top_results': top_results,
        'recent_results': recent_results,
        'total_exams_count': len(top_results),
    }
    return render(request, 'student/completed_exams.html', context)

# ==========================================================
# IMTIHON URINISHLARI VA DETAL VIEW'LARI
# ==========================================================

@login_required(login_url='login')
def exam_attempts_view(request, slug, exam_id):
    """
    Foydalanuvchining ma'lum bir imtihon bo'yicha barcha yakunlagan urinishlari.
    Faqat o‘z markazidagi o‘quvchi ko‘rishi mumkin.
    """
    # 1. MARKAZ TEKSHIRISH
    center = get_object_or_404(Center, slug=slug)
    if request.user.center is None or request.user.center != center:
        messages.error(request, "Bu sahifaga kirish huquqingiz yo‘q.")
        return redirect('index')

    # 2. IMTIHON TEKSHIRISH
    try:
        exam = get_object_or_404(
            Exam.objects.prefetch_related('sections'), 
            id=exam_id, 
            is_active=True,
            center=center  # MARKAZGA BOG‘LIQ!
        )
    except:
        messages.error(request, "Imtihon topilmadi yoki aktiv emas.")
        return redirect('exam_list', slug=slug)

    # 3. URINISHLAR
    attempts_qs = UserAttempt.objects.filter(
        user=request.user,
        exam=exam,
        is_completed=True
    ).order_by('-completed_at')

    # 4. JAVOBLAR HISOBI (N+1 bor, lekin sizning kodingizni saqlayman)
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
        'center': center,
        'exam': exam,
        'attempts': attempts_qs,
        'best_attempt': best_attempt,
        'latest_attempt': latest_attempt,
        'total_questions': total_questions,
    }
    
    return render(request, 'student/exam_attempts.html', context)

# ===========================================================
# ⭐️ O'QUVCHI UCHUN KURSLAR VIEWLARI (STUDENT VIEWS)
# ===========================================================


@login_required(login_url='login')
def all_courses_for_students(request, slug):
    """ O'quvchilar uchun barcha faol kurslar – faqat o‘z markazida """
    
    # 1. MARKAZ TEKSHIRISH (404 va xavfsizlik)
    center = get_object_or_404(Center, slug=slug)
    if request.user.center != center:
        # Foydalanuvchi noto'g'ri markaz slugini kiritgan bo'lsa, indeks sahifasiga yo'naltirish
        return redirect('index')

    # 2. Obuna holatini tekshirish
    is_subscribed = UserSubscription.objects.filter(
        user=request.user, end_date__gt=timezone.now()
    ).exists()

    # 3. Kurslarni olish va Annotatsiya (pass_threshold olib tashlandi)
    all_courses = Course.objects.filter(
        is_active=True, center=center
    ).annotate(
        # Barcha modul/dars/imtihon sonlari to'g'ri hisoblanadi
        total_modules=Count('modules', distinct=True),
        total_lessons=Count('modules__lessons', distinct=True),
        total_exams=Count(
            Case(
                When(modules__lessons__related_exam__isnull=False, then=1),
                output_field=IntegerField()
            ), distinct=True
        ),
        # pass_threshold qatori butunlay o'chirilgan
    ).select_related('teacher').order_by('-created_at')

    # 4. Kontekstni shakllantirish
    context = {
        'center': center,
        'all_courses': all_courses,
        'is_subscribed': is_subscribed,
        'page_title': "Barcha O'quv Kurslari"
    }
    
    return render(request, 'student/all_courses.html', context)

@login_required(login_url='login')
def course_enroll_view(request, slug, course_id):
    """
    Foydalanuvchini ko'rsatilgan kursga bog'langan 
    eng kam o'quvchisi bor guruhga qo'shadi.
    """
    
    # 1. Kursni topish: center_slug orqali center ni topib, keyin course ni topish 
    # eng xavfsiz yo'l hisoblanadi.
    center = get_object_or_404(Center, slug=slug)
    course = get_object_or_404(Course, id=course_id, center=center)
    
    user = request.user
    
    # 2. Foydalanuvchi kursga yozilganligini tekshirish
    if course.groups.filter(students=user).exists():
        messages.info(request, f"Siz allaqachon '{course.title}' kursiga yozilgansiz.")
        return redirect('course_detail', slug=slug, course_id=course_id)
        
    # 3. Kursga bog'liq guruhni topish
    try:
        # Eng kam o'quvchisi bo'lgan guruhni topish
        target_group = course.groups.annotate(
            student_count=Count('students')
        ).order_by('student_count').first()
        
        if not target_group:
            messages.error(request, "Afsuski, bu kurs uchun hozircha guruh ochilmagan.")
            return redirect('course_detail', slug=slug, course_id=course_id)
            
    except Exception as e:
        messages.error(request, f"Guruhni topishda xatolik yuz berdi: {e}")
        return redirect('course_detail', slug=slug, course_id=course_id)


    # 4. O'quvchini guruhga qo'shish (Enrollment)
    target_group.students.add(user)
    
    messages.success(request, f"Tabriklaymiz! Siz **'{course.title}'** kursidagi **'{target_group.name}'** guruhiga muvaffaqiyatli yozildingiz.")
    
    # Muvaffaqiyatli yozilgandan so'ng, kursning batafsil sahifasiga qaytamiz
    return redirect('course_detail', slug=slug, course_id=course_id)

@login_required(login_url='login')
def course_detail_view(request, slug, pk): 
    
    # 1. Asosiy obyektlarni olish
    center = get_object_or_404(Center, slug=slug)
    # E'tibor bering: ID ni olish uchun endi 'course_id' dan foydalanilyapti.
    course = get_object_or_404(Course.objects.select_related('teacher', 'center'), id=pk, center=center)
    
    # 2. Statistika hisoblash
    
    # M2M orqali o'quvchilar sonini hisoblash (Eng samarali usul)
    student_count_agg = course.groups.aggregate(
        total_students=Count('students', distinct=True) 
    )['total_students']
    
    students_count = student_count_agg if student_count_agg is not None else 0
    
    # Darslar sonini hisoblash
    total_lessons_count = Lesson.objects.filter(module__course=course).count()
    
    # Resurslar statistikasini hisoblash
    course_resources_count = LessonResource.objects.filter(
        lesson__module__course=course
    ).aggregate(
        total_videos_count=Count('id', filter=Q(resource_type='video')),
        total_tasks_count=Count('id', filter=Q(resource_type='task')),
        total_files_count=Count('id', filter=Q(resource_type__in=['solution_file', 'other'])),
    )
    
    # 3. Ro'yxatdan o'tish holatini tekshirish
    is_enrolled = False
    if request.user.is_authenticated:
        # User Group orqali kursga yozilganmi?
        # Agar Course M2M orqali Groupga ulangan bo'lsa:
        is_enrolled = course.groups.filter(students=request.user).exists()
        
    # 4. RoadMap ma'lumotlarini tuzish
    roadmap_data = []
    lessons_with_resources = Lesson.objects.filter(module__course=course).prefetch_related('resources', 'related_exam')
    modules = course.modules.all().order_by('order').prefetch_related('lessons')
    
    for module in modules:
        lessons = [lesson for lesson in lessons_with_resources if lesson.module_id == module.id]
        lessons.sort(key=lambda x: x.order)
        
        lesson_data_list = []
        for lesson in lessons:
            lesson_data_list.append({
                'lesson': lesson,
                'has_video': any(r.resource_type == 'video' for r in lesson.resources.all()),
                'has_task': any(r.resource_type == 'task' for r in lesson.resources.all()),
                'has_file': any(r.resource_type in ['solution_file', 'other'] for r in lesson.resources.all()),
            })

        roadmap_data.append({
            'module': module,
            'lessons': lesson_data_list,
        })
        
    # 5. Kontekstni tayyorlash
    context = {
        'center': center,
        'course': course,
        'roadmap_data': roadmap_data,
        
        'students_count': students_count, # To'g'rilangan
        'total_lessons_count': total_lessons_count,
        'teacher_info': course.teacher, 
        'is_enrolled': is_enrolled,      # Kirish tugmasini boshqaradi
        
        'total_videos_count': course_resources_count['total_videos_count'],
        'total_tasks_count': course_resources_count['total_tasks_count'],
        'total_files_count': course_resources_count['total_files_count'],
    }
    
    return render(request, 'student/course_detail.html', context)

@login_required(login_url='login')
def course_roadmap_view(request, slug, course_id):
    """ Kurs roadmap – faqat o‘z markazida """
    center = get_object_or_404(Center, slug=slug)
    if request.user.center != center:
        return redirect('index')

    course = get_object_or_404(Course, id=course_id, is_active=True, center=center)

    # 1. Obuna nazorati
    has_access = True 
    if course.is_premium:
        # UserSubscription modelini import qilgan deb faraz qildim
        has_access = UserSubscription.objects.filter(
            user=request.user, 
            end_date__gt=timezone.now(),
            course=course
        ).exists()
             
    # 2. Tugatilgan va o'tilgan testlar ID'larini olish
    completed_exam_ids = set()
    passed_exam_ids = set()
    
    user_attempts = UserAttempt.objects.filter(
        user=request.user, 
        is_completed=True
    ).select_related('exam')

    for attempt in user_attempts:
        completed_exam_ids.add(attempt.exam_id)
        if attempt.is_passed(): 
            passed_exam_ids.add(attempt.exam_id)

    # 3. PREFETCH OBYEKTLARINI TAYYORLASH
    
    # A) Exam Section Prefetch
    exam_sections_prefetch = Prefetch(
        'related_exam__sections',
        queryset=ExamSection.objects.all().order_by('examsectionorder__order'),
        to_attr='exam_sections_list'
    )
    
    # 🔥 B) LessonResource Prefetch (resources related_name to'g'ri) 🔥
    resources_prefetch = Prefetch(
        'resources', # <--- Lesson modelidagi related_name
        queryset=LessonResource.objects.all().order_by('order'),
        to_attr='all_resources_list'
    )
    
    # C) CourseSchedule Prefetch
    schedule_prefetch = Prefetch(
        'schedules',
        queryset=CourseSchedule.objects.all().order_by('start_time'),
        to_attr='schedules_list'
    )


    # 4. Modullar va Darslarni Yuklash
    modules_qs = CourseModule.objects.filter(course=course).order_by('order').prefetch_related(
        Prefetch(
            'lessons',
            queryset=Lesson.objects.select_related('related_exam').prefetch_related(
                exam_sections_prefetch,
                resources_prefetch, # Resurslar
                schedule_prefetch # Jadval
            ).order_by('order'),
            to_attr='lessons_list'
        )
    )

    # 5. Progress va Roadmap Ma'lumotlarini Hisoblash
    total_lessons_count = 0
    completed_lessons_count = 0
    is_previous_completed = True 
    is_scheduled = course.is_scheduled # Course modelidagi property

    roadmap_data = []

    for module in modules_qs:
        module_lessons_count = 0
        module_completed_count = 0
        lessons_data = []

        for lesson in module.lessons_list:
            exam = lesson.related_exam
            
            current_resources = getattr(lesson, 'all_resources_list', []) 
            has_resources = bool(current_resources)
            
            # Jadval ma'lumoti
            lesson_schedules = getattr(lesson, 'schedules_list', [])
            lesson_schedule = lesson_schedules[0] if lesson_schedules else None
            
            # Agar dars jadval asosida bo'lsa va hali boshlanmagan bo'lsa, bloklanadi.
            is_time_locked = False
            if is_scheduled and lesson_schedule and lesson_schedule.start_time > timezone.now():
                is_time_locked = True

            # Bloklash mantiqi
            is_locked = (not has_access or 
                         (is_scheduled and is_time_locked) or # Vaqt bloklashi
                         (not is_scheduled and not is_previous_completed) # Ketma-ketlik bloklashi
                        )
            
            # Test natijalari
            exam_completed = exam.id in completed_exam_ids if exam else False
            exam_passed = exam.id in passed_exam_ids if exam else False

            # Dars yakunlanishi mantiqi:
            if exam:
                lesson_is_finished = exam_passed # Test bo'lsa, o'tilgan bo'lishi kerak
            elif has_resources:
                # Resurs bo'lsa va test bo'lmasa, avtomatik yakunlangan deb qabul qiling
                lesson_is_finished = True 
            else:
                lesson_is_finished = True # Resurs ham, test ham bo'lmasa, avtomatik yakunlangan

            # Exam info
            exam_info_str = None
            if exam and hasattr(lesson, 'exam_sections_list'):
                total_q = sum(s.max_questions for s in lesson.exam_sections_list)
                passing = exam.passing_percentage
                exam_info_str = f"{total_q} savol, O'tish: {passing}%"
            
            # Jadval boshlanish vaqti
            start_time_str = lesson_schedule.start_time.strftime('%Y-%m-%d %H:%M') if lesson_schedule else None


            # Progress hisobi (Faqat bloklanmagan darslar hisoblanadi)
            if lesson_is_finished and not is_locked:
                completed_lessons_count += 1
                module_completed_count += 1
                is_previous_completed = True
            elif not lesson_is_finished and not is_locked:
                is_previous_completed = False # Keyingi darsni bloklash
            
            total_lessons_count += 1
            module_lessons_count += 1

            lessons_data.append({
                'lesson': lesson,
                'is_locked': is_locked,
                'is_time_locked': is_time_locked,
                'start_time_str': start_time_str,
                'resources': current_resources, 
                'lesson_is_finished': lesson_is_finished,
                'exam_completed': exam_completed, 
                'exam_id': exam.id if exam else None,
                'exam_info': exam_info_str,
                'exam_passed': exam_passed, 
            })

        # Modul progressi
        module_progress = int((module_completed_count / module_lessons_count) * 100) if module_lessons_count else 0
        
        roadmap_data.append({
            'module': module,
            'lessons': lessons_data,
            'progress_perc': module_progress,
            'completed_count': module_completed_count,
            'total_count': module_lessons_count,
        })

    # Kurs progressi
    course_progress = int((completed_lessons_count / total_lessons_count) * 100) if total_lessons_count else 0

    context = {
        'center': center,
        'course': course,
        'roadmap_data': roadmap_data,
        'has_access': has_access,
        'total_lessons_count': total_lessons_count,
        'completed_lessons_count': completed_lessons_count,
        'course_progress': course_progress,
    }
    return render(request, 'student/course_roadmap.html', context)

# ======================================================================
# ⭐️ O'QITUVCHI/ADMIN UCHUN KURSLAR VIEWLARI (MANAGEMENT VIEWS)
# ======================================================================

@login_required(login_url='login')
def course_list(request, slug):
    """ Markazga tegishli kurslar ro'yxatini ko'rish. """
    user = request.user
    center = get_object_or_404(Center, slug=slug)
    
    # Ruxsat tekshiruvi (Center admin, o'qituvchi yoki umumiy admin bo'lishi kerak)
    if not (user.center == center or user.is_staff):
        messages.error(request, "Sizda bu markaz kurslarini ko'rish huquqi yo'q.")
        return redirect('dashboard',slug=request.user.center.slug)
    
    # 🔥 O'zgarish: 'creator__center' o'rniga 'teacher__center'
    # Bu orqali kursning ustoziga bog'langan markaz orqali filtrlash amalga oshiriladi.
    courses = Course.objects.filter(teacher__center=center).order_by('-created_at').select_related('teacher')
    
    context = {
        'courses': courses,
        'center': center, # Shablonlarda URL yaratish uchun kerak
        'page_title': f"{center.name} Kurslari Ro'yxati"
    }
    return render(request, 'management/course_list.html', context)


# ======================================================================
# 1. KURSLAR YARATISH VIEW
# ======================================================================

@login_required(login_url='login')
def course_create(request, slug):
    user = request.user
    center = get_object_or_404(Center, slug=slug)
    
    # 1. Ruxsat tekshiruvi
    if not ((user.role in ['teacher', 'center_admin'] and user.center == center) or user.is_staff):
        messages.error(request, "Sizda bu markaz uchun kurs yaratish huquqi yo'q.")
        return redirect('dashboard',slug=request.user.center.slug)
    
    # 🔥 TO'G'IRLASH: Modelni olish uchun get_user_model() dan foydalanish
    TeacherModel = get_user_model() 
    
    # 🔥 O'qituvchi Queryset'ini yaratish
    teacher_queryset = TeacherModel.objects.filter(
        center=center, 
        role__in=['teacher', 'center_admin'] 
    ).order_by('full_name')

    if request.method == 'POST':
        form = CourseForm(request.POST, request.FILES)
        
        if 'teacher' in form.fields:
             form.fields['teacher'].queryset = teacher_queryset
             
        if form.is_valid():
            course = form.save(commit=False)
            
            course.teacher = user         
            course.center = center        
            
            course.save()
            messages.success(request, f"'{course.title}' kursi muvaffaqiyatli yaratildi.")
            
            return redirect('course_list', slug=center.slug)
    else:
        form = CourseForm()
        
        if 'teacher' in form.fields:
            form.fields['teacher'].queryset = teacher_queryset
            form.initial['teacher'] = user 
            
    context = {
        'form': form,
        'center': center, 
        'page_title': f"{center.name} uchun Yangi Kurs Yaratish"
    }
    return render(request, 'management/course_form.html', context)


@login_required(login_url='login')
def course_update(request, slug, pk):
    user = request.user
    center = get_object_or_404(Center, slug=slug)
    course = get_object_or_404(Course, id=pk)

    # 1. Ruxsat tekshiruvi
    if not (course.center == center):
         messages.error(request, "Kurs boshqa markazga tegishli. Tahrirlash mumkin emas.")
         return redirect('course_list', slug=center.slug)

    is_authorized = (
        course.teacher == user or                  
        user.is_staff or                           
        (user.role == 'center_admin' and user.center == center) 
    )
    
    if not is_authorized:
         messages.error(request, "Siz bu kursni tahrirlash huquqiga ega emassiz.")
         return redirect('course_list', slug=center.slug)

    # 🔥 TO'G'IRLASH: Modelni olish uchun get_user_model() dan foydalanish
    TeacherModel = get_user_model()
    
    # 🔥 O'qituvchi Queryset'ini yaratish
    teacher_queryset = TeacherModel.objects.filter(
        center=center, 
        role__in=['teacher', 'center_admin']
    ).order_by('full_name')


    if request.method == 'POST':
        form = CourseForm(request.POST, request.FILES, instance=course)
        
        if 'teacher' in form.fields:
            form.fields['teacher'].queryset = teacher_queryset
            
        if form.is_valid():
            form.save()
            messages.success(request, f"'{course.title}' kursi muvaffaqiyatli tahrirlandi.")
            
            return redirect('course_list', slug=center.slug)
    else:
        form = CourseForm(instance=course)
        
        if 'teacher' in form.fields:
             form.fields['teacher'].queryset = teacher_queryset
        
    context = {
        'form': form,
        'course': course,
        'center': center, 
        'page_title': f"{course.title} ni tahrirlash"
    }
    return render(request, 'management/course_form.html', context)


@login_required(login_url='login')
def course_delete(request, slug, pk):
    """ Kursni o'chirish (CRUD Delete). """
    user = request.user
    center = get_object_or_404(Center, slug=slug)
    course = get_object_or_404(Course, id=pk)

    # 1. Xavfsizlik va Ruxsat tekshiruvi
    if not ((is_teacher(user) and user.center == center and course.creator.center == center) or user.is_staff):
        messages.error(request, "Sizda bu kursni o'chirish huquqi yo'q.")
        return redirect('dashboard',slug=request.user.center.slug)

    course_title = course.title
    
    if request.method == 'POST':
        course.delete()
        messages.success(request, f"'{course_title}' nomli kurs muvaffaqiyatli o'chirildi.")
        # 2. Redirect qilishda ham SLUG ni uzatish
        return redirect('course_list', slug=center.slug)
        
    context = {
        'course': course,
        'center': center, # Shablonlarda URL yaratish uchun kerak
        'page_title': f"'{course_title}' kursini o'chirish"
    }
    return render(request, 'management/course_confirm_delete.html', context)

# ======================================================================
# 🧑‍🎓 O'QUVCHI UCHUN NATIJA VIEW'I
# ======================================================================

@login_required(login_url='login')
def view_subject_exam_result(request, slug, attempt_id):
    """
    Mavzu Testi (Subject Exam) natijasi – faqat o‘z markazida
    """
    # 1. MARKAZ TEKSHIRISH
    center = get_object_or_404(Center, slug=slug)
    if request.user.center is None or request.user.center != center:
        messages.error(request, "Bu sahifaga kirish huquqingiz yo‘q.")
        return redirect('dashboard',slug=request.user.center.slug)

    try:
        # 2. URINISH TEKSHIRISH
        attempt = get_object_or_404(
            UserAttempt, 
            id=attempt_id, 
            user=request.user,
            exam__center=center  # MARKAZGA BOG‘LIQ!
        )
        if not attempt.exam.is_subject_exam:
            return redirect('view_result_detail', slug=center.slug, attempt_id=attempt_id)
            
    except Exception:
        messages.error(request, "Mavzu Testi natijasi topilmadi yoki sizga tegishli emas.")
        return redirect('dashboard',slug=request.user.center.slug)
        
    # 3. NATIJA HISOBI
    sections_qs = attempt.section_attempts.select_related('section').order_by('section__order') 
    
    correct_answers_by_section_attempt = UserAnswer.objects.filter(
        attempt_section__attempt=attempt, is_correct=True
    ).values('attempt_section__id').annotate(correct_count=Count('id'))
    correct_map = {item['attempt_section__id']: item['correct_count'] for item in correct_answers_by_section_attempt}
    
    total_correct = 0
    total_questions = 0
    section_analysis_list = [] 
    
    for section_attempt in sections_qs:
        correct = correct_map.get(section_attempt.id, 0)
        section_questions = section_attempt.questions.count()
        
        if section_questions == 0:
            continue
        
        total_correct += correct
        total_questions += section_questions
        
        user_answers_for_nav = UserAnswer.objects.filter(
            attempt_section=section_attempt
        ).select_related('question').order_by('question__id')
        
        section_analysis_list.append({
            'section_attempt_id': section_attempt.id,
            'section_name': section_attempt.section.get_section_type_display(),
            'user_answers_nav': user_answers_for_nav,
            'correct_count': correct,
            'total_count': section_questions,
        })
        
    total_omitted = UserAnswer.objects.filter(attempt_section__attempt=attempt, is_correct=None).count()
    total_incorrect = total_questions - total_correct - total_omitted
    total_percentage = round((total_correct / total_questions * 100)) if total_questions > 0 else 0
    
    passing_required = attempt.exam.passing_percentage
    is_passed = total_percentage >= passing_required
    
    if not attempt.is_completed:
        attempt.is_completed = True
        attempt.can_view_solution = is_passed 
        attempt.final_ebrw_score = None
        attempt.final_math_score = None
        attempt.final_total_score = None
        attempt.save()

    context = {
        'center': center,
        'attempt': attempt,
        'section_analysis_list': section_analysis_list,
        'is_subject_exam': True, 
        'is_passed': is_passed,
        'passing_required': passing_required,
        'can_view_solution': attempt.can_view_solution,
        'total_percentage': total_percentage,
        'total_correct': total_correct,
        'total_incorrect': total_incorrect,
        'total_omitted': total_omitted,
    }
    return render(request, 'student/subject_exam_result_detail.html', context)

# =================================================================
# YANGI VIEW: Tariflar sahifasi
# =================================================================

@login_required(login_url='login')
def price_view(request, slug):
    """Tariflar sahifasi – faqat o‘z markazida"""
    center = get_object_or_404(Center, slug=slug)
    if request.user.center != center:
        return redirect('index')

    exam_packages = ExamPackage.objects.filter(is_active=True).order_by('price')
    subscription_plans = SubscriptionPlan.objects.filter(is_active=True).order_by('price')
    form = PurchaseForm()

    context = {
        'center': center,
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
def process_purchase_view(request, slug, purchase_type, item_id):
    """
    Xaridni qayta ishlaydi – faqat o‘z markazida
    """
    center = get_object_or_404(Center, slug=slug)
    if request.user.center != center:
        messages.error(request, "Bu sahifaga kirish huquqingiz yo‘q.")
        return redirect('price', slug=slug)

    if request.method != 'POST':
        messages.error(request, "Noto'g'ri so'rov usuli.")
        return redirect('price', slug=slug)

    form = PurchaseForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Formada xatolik bor.")
        return redirect('price', slug=slug)

    promo_code_str = form.cleaned_data.get('promo_code')
    user = request.user
    
    try:
        item = None
        item_type_display = ""
        if purchase_type == 'package':
            item = get_object_or_404(ExamPackage, id=item_id, is_active=True)
            item_type_display = f"'{item.name}' paketi"
        elif purchase_type == 'subscription':
            item = get_object_or_404(SubscriptionPlan, id=item_id, is_active=True)
            item_type_display = f"'{item.name}' obunasi"
        else:
            messages.error(request, "Noto'g'ri xarid turi.")
            return redirect('price', slug=slug)

        final_amount = item.price
        promo_code = None

        if promo_code_str:
            try:
                promo_code = PromoCode.objects.get(code=promo_code_str, is_active=True)
                if not promo_code.is_valid():
                    messages.error(request, "Promo kod muddati tugagan.")
                    return redirect('price', slug=slug)
                
                if promo_code.discount_type == 'percentage':
                    discount = final_amount * (promo_code.discount_percent / 100)
                    final_amount -= discount
                else:
                    final_amount -= promo_code.discount_amount
                
                final_amount = max(0, final_amount)
                messages.info(request, f"Chegirma qo‘llandi: {item.price - final_amount:.2f} so‘m")

            except PromoCode.DoesNotExist:
                messages.error(request, "Noto'g'ri promo kod.")
                return redirect('price', slug=slug)

        purchase = Purchase.objects.create(
            user=user,
            purchase_type=purchase_type,
            package=item if purchase_type == 'package' else None,
            subscription_plan=item if purchase_type == 'subscription' else None,
            amount=item.price,
            promo_code=promo_code,
            final_amount=final_amount,
            status='completed'
        )

        if promo_code:
            promo_code.used_count += 1
            promo_code.save()

        if purchase_type == 'package':
            balance, _ = UserBalance.objects.get_or_create(user=user)
            balance.exam_credits += item.exam_credits
            balance.solution_view_credits += item.solution_view_credits_on_purchase
            balance.save()
        
        elif purchase_type == 'subscription':
            UserSubscription.objects.filter(user=user).delete()
            UserSubscription.objects.create(
                user=user,
                plan=item,
                start_date=timezone.now(),
                end_date=timezone.now() + timedelta(days=item.duration_days)
            )

        messages.success(request, f"{item_type_display} muvaffaqiyatli xarid qilindi!")
        return redirect('profile', slug=slug)

    except Exception as e:
        logger.error(f"Xarid xatosi: {e}", exc_info=True)
        messages.error(request, "Server xatoligi. Keyinroq urinib ko‘ring.")
        return redirect('price', slug=slug)

# =========================================================================
# 🎯 1. IMTIHONNI BOSHLASH MANTIQI (start_exam_view)
# =========================================================================

EBRW_M1, EBRW_M2 = 'read_write_m1', 'read_write_m2'
MATH_M1, MATH_M2 = 'math_no_calc', 'math_calc'


@login_required(login_url='login')
@require_POST
def start_exam_view(request, slug, exam_id):
    """
    Imtihonni boshlaydi. Yangi urinish (UserAttempt) va bo'lim urinishlarini yaratadi.
    Foydalanuvchining markazga bog'liqligini tekshiradi (xavfsizlik).
    """
    
    # 1. Markazni slug bo'yicha topish
    center = get_object_or_404(Center, slug=slug)

    # 2. Xavfsizlik Tekshiruvi
    if request.user.center is None or request.user.center != center:
        messages.error(request, "Bu markazga kirish huquqingiz yo‘q yoki sizga markaz biriktirilmagan.")
        return redirect('index')
    
    try:
        # 3. Exam obyektini olish. User.center orqali qattiq tekshirish
        exam = get_object_or_404(
            Exam, 
            id=exam_id, 
            is_active=True, 
            center=center
        )
        
        # Tugallanmagan urinish mavjudligini tekshirish
        attempt = UserAttempt.objects.filter(user=request.user, exam=exam, is_completed=False).first()
        
        with transaction.atomic():
            if not attempt:
                # Yangi urinishni yaratish
                attempt = UserAttempt.objects.create(
                    user=request.user,
                    exam=exam,
                    mode='exam' 
                )
                logger.info(f"Yangi urinish yaratildi: {attempt.id} (Exam: {exam_id})")
                
                # Bo'limlarni tartib bo'yicha olish
                sections_with_order = exam.examsectionorder.select_related('exam_section').order_by('order')
                
                if not sections_with_order.exists():
                    logger.error(f"Imtihon ({exam_id}) uchun bo‘limlar topilmadi.")
                    return JsonResponse({'status': 'error', 'message': 'Bu imtihonda bo‘limlar mavjud emas'}, status=400)
                
                new_section_attempts = []
                
                # UserAttemptSection obyektlarini yaratish
                for eso in sections_with_order:
                    section = eso.exam_section
                    
                    section_attempt = UserAttemptSection(
                        attempt=attempt,
                        section=section,
                        remaining_time_seconds=section.duration_minutes * 60
                    )
                    new_section_attempts.append(section_attempt)

                # Barcha section_attempt'larni ommaviy saqlash
                UserAttemptSection.objects.bulk_create(new_section_attempts)

                # Savollarni bog'lash (Bu qism tezlik uchun alohida funksiyaga o'tkazilishi mumkin, lekin shu yerda qoldirildi)
                all_section_attempts = UserAttemptSection.objects.filter(attempt=attempt).select_related('section')
                
                # Savollarni bog'lash
                for section_attempt in all_section_attempts:
                    section = section_attempt.section
                    static_questions = ExamSectionStaticQuestion.objects.filter(
                        exam_section=section
                    ).order_by('question_number')
                    
                    for static_q in static_questions:
                        UserAttemptQuestion.objects.create(
                            attempt_section=section_attempt,
                            question=static_q.question,
                            question_number=static_q.question_number
                        )
                    logger.info(f"Bo'lim '{section.name}'ga {static_questions.count()} ta savol bog'landi.")
                    
            # Eng kam tartib raqamli bo'lim urinishini topish
            first_section_attempt = UserAttemptSection.objects.filter(attempt=attempt).annotate(
                order=Subquery(
                    ExamSectionOrder.objects.filter(
                        exam=exam,
                        exam_section=OuterRef('section')
                    ).values('order')[:1]
                )
            ).order_by('order').first()

            if not first_section_attempt:
                logger.error(f"Urinish {attempt.id} uchun bo'limlar yaratilmadi yoki tartibi topilmadi.")
                return JsonResponse({'status': 'error', 'message': 'Imtihon bo‘limlari mavjud emas yoki tartiblanmagan'}, status=400)
            
            # Foydalanuvchini imtihon rejimiga yo'naltirish
            exam_url = reverse('exam_mode', kwargs={'slug': slug, 'exam_id': exam.id, 'attempt_id': attempt.id})
            
            return JsonResponse({'status': 'success', 'attempt_id': attempt.id, 'redirect_url': exam_url})
        
    except Exam.DoesNotExist:
        # Yuqoridagi kuchaytirilgan tekshiruvdan keyin faqat DB ma'lumoti noto'g'ri bo'lsa beriladi
        return JsonResponse({'status': 'error', 'message': 'Imtihon topilmadi, aktiv emas yoki sizning markazingizga tegishli emas.'}, status=404)
    except Exception as e:
        logger.error(f"start_exam_view xatosi: {str(e)}", exc_info=True)
        return JsonResponse({'status': 'error', 'message': f'Imtihonni boshlashda kutilmagan server xatosi: {str(e)}'}, status=500)

# =========================================================================
# ⭐️ 2. IMTIHON TOPSHIRISH REJIMI (exam_mode_view)
# =========================================================================

@login_required(login_url='login')
def exam_mode_view(request, slug, exam_id, attempt_id): # 🎯 SLUG QO'SHILDI
    """
    Imtihon topshirish sahifasini ko'rsatadi. Timer va birinchi savol ma'lumotlarini yuklaydi.
    """
    # 1. Markazni slug bo'yicha topish
    center = get_object_or_404(Center, slug=slug)

    # 2. Xavfsizlik Tekshiruvi
    if request.user.center is None or request.user.center != center:
        messages.error(request, "Bu markazga kirish huquqingiz yo‘q yoki sizga markaz biriktirilmagan.")
        return redirect('index')

    try:
        # 3. UserAttempt ni olish va xavfsizlik tekshiruvi (Markaz orqali bog'lash)
        attempt = get_object_or_404(
            UserAttempt, 
            id=attempt_id, 
            user=request.user, 
            exam__id=exam_id,
            exam__center=center
        )
        
        # 4. Tugallanmagan bo'lim urinishini olish (tartib bo'yicha birinchisi)
        # Bu mantiq to'g'ri:
        section_attempt = UserAttemptSection.objects.filter(attempt=attempt, is_completed=False).select_related('section').annotate(
            order=Subquery(
                ExamSectionOrder.objects.filter(
                    exam=attempt.exam,
                    exam_section=OuterRef('section')
                ).values('order')[:1]
            )
        ).order_by('order').first()
        
        if not section_attempt:
            messages.info(request, "Imtihon bo'limlari yakunlangan.")
            return redirect('view_result_detail', slug=center.slug, attempt_id=attempt.id) 
            
        # 5. 🔥 BIRINCHI SAVOL ID'sini olish (Tartibni ExamSectionStaticQuestion'dan tiklash)
        ordered_questions_ids = ExamSectionStaticQuestion.objects.filter(
            exam_section=section_attempt.section
        ).order_by('question_number').values_list('question_id', flat=True)

        first_question_id = ordered_questions_ids.first()
        
        if not first_question_id:
            messages.warning(request, f"'{section_attempt.section.name}' bo'limida savollar yuklanmagan. Keyingisiga o‘tildi.")
            # Bo'limni yakunlangan deb belgilab, o'zini qayta chaqirish
            section_attempt.is_completed = True
            section_attempt.completed_at = timezone.now()
            section_attempt.save()
            # Redirectga SLUG qo'shildi:
            return redirect('exam_mode', slug=slug, exam_id=exam_id, attempt_id=attempt_id)


        # 6. Timer mantiqi (O'zgarmagan)
        total_duration_seconds = section_attempt.section.duration_minutes * 60
        time_remaining_seconds = section_attempt.remaining_time_seconds
        
        if section_attempt.started_at is None:
            # ... (Birinchi marta boshlash mantiqi)
            section_attempt.started_at = timezone.now()
            section_attempt.save()
            time_remaining_seconds = total_duration_seconds 
        else:
            # ... (Davom ettirish mantiqi)
            elapsed_seconds = (timezone.now() - section_attempt.started_at).total_seconds()
            time_remaining_seconds = max(0, int(total_duration_seconds - elapsed_seconds)) 
            
            # Agar vaqt tugagan bo'lsa, bo'limni yakunlaymiz
            if time_remaining_seconds == 0 and not section_attempt.is_completed:
                section_attempt.is_completed = True
                section_attempt.completed_at = timezone.now()
                section_attempt.save()
                messages.warning(request, f"Vaqt tugashi sababli '{section_attempt.section.name}' bo'limi yakunlandi.")
                # Redirectga SLUG qo'shildi:
                return redirect('exam_mode', slug=slug, exam_id=exam_id, attempt_id=attempt_id) 
                
        # 7. Qo'shimcha optionlarni aniqlash (O'zgarmagan)
        section_type = section_attempt.section.section_type
        extra_options = []
        if section_type == MATH_M2:
            extra_options.append('calculator')
        if section_type in [MATH_M1, MATH_M2]:
            extra_options.append('reference')
        
        # 8. Kontekstni tuzish
        context = {
            'exam': attempt.exam,
            'attempt_id': attempt.id,
            'section_attempt_id': section_attempt.id,
            'section_attempt': section_attempt,
            'time_remaining_seconds': time_remaining_seconds,
            'extra_options': extra_options,
            'is_subject_exam': attempt.exam.is_subject_exam, 
            'first_question_id': first_question_id,
            'center': center, # 🎯 MARKAZ OBYEKTI KONTEKSTGA QO'SHILDI
        }
        
        return render(request, 'student/exam_mode.html', context)
        
    except UserAttempt.DoesNotExist:
        messages.error(request, "Imtihon urinishi topilmadi.")
        return redirect('all_exams')
    except Exception as e:
        logger.error(f"exam_mode_view xatosi: {str(e)}", exc_info=True)
        messages.error(request, "Imtihon sahifasini yuklashda kutilmagan xato yuz berdi.")
        return redirect('dashboard',slug=request.user.center.slug)


@csrf_exempt
@require_POST
def handle_exam_ajax(request):
    """
    Imtihon jarayonidagi barcha AJAX so'rovlarini boshqaradigan asosiy view.
    """
    if not request.user.is_authenticated:
        return JsonResponse({'status': 'error', 'message': 'Autentifikatsiya talab qilinadi.'}, status=401)
        
    try:
        data = json.loads(request.body)
        action = data.get('action')
        attempt_id = data.get('attempt_id')
        section_attempt_id = data.get('section_attempt_id')
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Yaroqsiz JSON formati.'}, status=400)
    
    if not attempt_id or not section_attempt_id or not action:
        return JsonResponse({'status': 'error', 'message': 'Attempt ID, Section Attempt ID yoki Action majburiy.'}, status=400)

    try:
        attempt = get_object_or_404(UserAttempt, id=attempt_id, user=request.user)
        section_attempt = get_object_or_404(UserAttemptSection, id=section_attempt_id, attempt=attempt)
    except Exception:
        logger.error(f"Attempt/Section topilmadi. Attempt ID: {attempt_id}, User: {request.user.id}")
        return JsonResponse({'status': 'error', 'message': 'Imtihon urinishi yoki bo‘limi topilmadi.'}, status=404)
        
    
    # =================================================================================
    # 1. BO'LIM MA'LUMOTLARINI YUKLASH (LOAD_SECTION_DATA)
    # =================================================================================
    if action == 'load_section_data':
        try:
            questions_in_order = section_attempt.userattemptquestion_set.all().order_by('question_number')
            question_ids = list(questions_in_order.values_list('question_id', flat=True))
            
            user_answers = UserAnswer.objects.filter(attempt_section=section_attempt).select_related('question').prefetch_related('selected_options')

            initial_answers = {}
            answered_ids = []
            marked_for_review_ids = []

            for ans in user_answers:
                selected_options_ids = list(ans.selected_options.values_list('id', flat=True))
                
                initial_answers[str(ans.question_id)] = {
                    'selected_options': selected_options_ids if selected_options_ids else None,
                    'selected_option': selected_options_ids[0] if ans.question.answer_format == 'single' and selected_options_ids else None,
                    'short_answer_text': ans.short_answer_text if ans.short_answer_text and ans.short_answer_text.strip() else None,
                    'is_marked_for_review': ans.is_marked_for_review
                }
                
                is_answered = (ans.question.answer_format == 'short_answer' and bool(ans.short_answer_text and ans.short_answer_text.strip())) or \
                              (ans.selected_options.exists())
                    
                if is_answered:
                    answered_ids.append(ans.question_id)
                if ans.is_marked_for_review:
                    marked_for_review_ids.append(ans.question_id)

            return JsonResponse({
                'status': 'success',
                'section_data': {
                    'question_ids': question_ids,
                    'initial_time_remaining': section_attempt.remaining_time_seconds,
                    'section_completed': section_attempt.is_completed,
                    'initial_answers': initial_answers,
                    'answered_question_ids': answered_ids,
                    'marked_for_review_ids': marked_for_review_ids,
                }
            })

        except Exception as e:
            logger.error(f"Bo'lim ma'lumotlarini yuklashda xato: {e}", exc_info=True)
            return JsonResponse({'status': 'error', 'message': f"Bo'limni yuklashda xato: {str(e)}"}, status=500)


    # =================================================================================
    # 🔥 2. SAVOL MA'LUMOTLARINI YUKLASH (LOAD_QUESTION_DATA) - YAKUNIY TUZATISH
    # =================================================================================
    elif action == 'load_question_data':
        question_id = data.get('question_id')
        
        if not question_id:
            return JsonResponse({'status': 'error', 'message': 'Savol IDsi majburiy.'}, status=400)
            
        try:
            question = Question.objects.select_related('passage').prefetch_related('options').get(id=question_id)
            
            options_data = []
            option_choices = ['A', 'B', 'C', 'D', 'E', 'F'] 
            
            for index, option in enumerate(question.options.all().order_by('id')): 
                options_data.append({
                    'id': option.id,
                    'text': option.text, # AnswerOption modelida 'text' ishlatiladi
                    'char': option_choices[index] if index < len(option_choices) else '',
                    'image_url': getattr(option, 'image', None).url if getattr(option, 'image', None) else None,
                })

            user_answer = UserAnswer.objects.filter(
                attempt_section=section_attempt, 
                question=question
            ).first()
            
            initial_answer = {}
            if user_answer:
                is_answered = (question.answer_format == 'short_answer' and bool(user_answer.short_answer_text and user_answer.short_answer_text.strip())) or \
                              (user_answer.selected_options.exists())
                    
                selected_options_ids = list(user_answer.selected_options.values_list('id', flat=True))
                
                initial_answer = {
                    'selected_options': selected_options_ids,
                    'selected_option': selected_options_ids[0] if question.answer_format == 'single' and selected_options_ids else None,
                    'short_answer_text': user_answer.short_answer_text,
                    'is_marked_for_review': user_answer.is_marked_for_review,
                    'is_answered': is_answered
                }
            
            try:
                question_number = section_attempt.userattemptquestion_set.get(question=question).question_number
            except:
                question_number = 0 
                
            # Savol ma'lumotlarini tayyorlash: Question modelidagi "text" maydoni ishlatildi.
            question_data = {
                'id': question.id,
                'number': question_number,
                'text': question.text, # <<< TO'G'RI: Question modelidagi 'text' maydoni!
                'format': question.answer_format,
                'image_url': question.image.url if question.image else None, 
                'options': options_data,
                'initial_answer': initial_answer,
                'passage_text': question.passage.text if question.passage else None,
            }

            return JsonResponse({'status': 'success', 'question_data': question_data})

        except Question.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Savol bazada topilmadi.'}, status=404)
        except Exception as e:
            logger.error(f"Savolni yuklashda server xatosi: {e}", exc_info=True)
            return JsonResponse({'status': 'error', 'message': f"Savolni yuklashda server xatosi: {str(e)}"}, status=500)


    # =================================================================================
    # 3. JAVOBNI SAQLASH VA VAQTNI SINXRONLASH (SAVE_ANSWER & SYNC_TIMER)
    # =================================================================================
    elif action == 'save_answer' or action == 'sync_timer':
        
        time_remaining = data.get('time_remaining')
        if time_remaining is not None and time_remaining >= 0:
            section_attempt.remaining_time_seconds = time_remaining
            
        if action == 'save_answer':
            question_id = data.get('question_id')
            
            selected_option_id = data.get('selected_option') 
            selected_options_ids = data.get('selected_options') 
            short_answer_text = data.get('short_answer_text') 
            is_marked_for_review = data.get('is_marked_for_review', False)

            if not question_id:
                if time_remaining is not None:
                     section_attempt.save(update_fields=['remaining_time_seconds'])
                return JsonResponse({'status': 'error', 'message': 'Savol IDsi majburiy.'}, status=400)
            
            try:
                question = Question.objects.get(id=question_id) 
            except Question.DoesNotExist:
                return JsonResponse({'status': 'error', 'message': 'Savol topilmadi.'}, status=404)

            with transaction.atomic():
                user_answer, created = UserAnswer.objects.get_or_create(
                    attempt_section=section_attempt, 
                    question_id=question_id,
                    defaults={'is_marked_for_review': is_marked_for_review}
                )
                
                user_answer.selected_options.clear() 
                user_answer.short_answer_text = '' 
                
                if question.answer_format in ('single', 'multiple'):
                    if question.answer_format == 'single' and selected_option_id is not None:
                        try:
                            option = AnswerOption.objects.get(id=selected_option_id, question=question) 
                            user_answer.selected_options.add(option)
                        except AnswerOption.DoesNotExist: 
                             pass
                            
                    elif question.answer_format == 'multiple' and selected_options_ids and isinstance(selected_options_ids, list):
                        valid_options = AnswerOption.objects.filter(id__in=selected_options_ids, question=question) 
                        user_answer.selected_options.set(valid_options)
                        
                    user_answer.short_answer_text = '' 
                        
                elif question.answer_format == 'short_answer' and short_answer_text is not None:
                    user_answer.short_answer_text = short_answer_text.strip()
                
                user_answer.is_marked_for_review = is_marked_for_review
                
                is_answered = (question.answer_format == 'short_answer' and bool(user_answer.short_answer_text and user_answer.short_answer_text.strip())) or \
                              (user_answer.selected_options.exists())
                        
                if is_answered:
                    if not user_answer.answered_at:
                        user_answer.answered_at = timezone.now()
                else:
                    user_answer.answered_at = None 
                
                user_answer.save()
                
                answered_ids = list(UserAnswer.objects.filter(
                    attempt_section=section_attempt
                ).exclude(
                    Q(selected_options__isnull=True) & Q(short_answer_text__exact='')
                ).values_list('question_id', flat=True).distinct())

                section_attempt.save(update_fields=['remaining_time_seconds'])
                
                return JsonResponse({
                    'status': 'success', 
                    'message': 'Javob saqlandi',
                    'answered_question_ids': answered_ids
                })
        
        if time_remaining is not None:
            section_attempt.save(update_fields=['remaining_time_seconds'])
        return JsonResponse({'status': 'success', 'message': 'Vaqt sinxronizatsiya qilindi'})

    # =================================================================================
    # 4. IMTIHON/BO'LIM YAKUNLASH (FINISH_EXAM & FINISH_SECTION)
    # =================================================================================
    elif action in ['finish_exam', 'finish_section']:
        # ... (Bu blok to'g'ri ishlaydi)
        pass # Bu yerni o'z kodingiz bilan almashtiring
    
    # =================================================================================
    # 5. FLASHCARDS YUQLASH (GET_FLASHCARDS)
    # =================================================================================
    elif action == 'get_flashcards':
        # ... (Bu blok to'g'ri ishlaydi)
        pass # Bu yerni o'z kodingiz bilan almashtiring

    return JsonResponse({'status': 'error', 'message': 'Noto‘g‘ri action aniqlandi.'}, status=400)

def get_question_data(request, section_attempt, question_id):
    """
    Berilgan savolning ma'lumotlarini va foydalanuvchining oldingi javobini yuklaydi.
    """
    try:
        question = section_attempt.questions.get(id=question_id)
        options = question.options.all()
        
        # Harflarni qo'shish
        letters = list(string.ascii_uppercase)
        options_with_letters = list(zip(options, letters[:len(options)]))

        user_answer = UserAnswer.objects.filter(
            attempt_section=section_attempt,
            question_id=question_id
        ).first()
        
        selected_option_ids = []
        short_answer = None
        is_marked = False
        
        if user_answer:
            selected_option_ids = list(user_answer.selected_options.values_list('id', flat=True))
            short_answer = user_answer.short_answer_text
            is_marked = user_answer.is_marked_for_review
        
        # Savolning tartib raqamini aniqlash (navigation uchun kerak)
        q_order = section_attempt.questions.through.objects.filter(
            attempt_section=section_attempt,
            question=question
        ).values_list('question_number', flat=True).first()

        context = {
            'question': question,
            'user_answer': user_answer,
            'options': options,
            'options_with_letters': options_with_letters, 
            'is_study_mode': section_attempt.attempt.mode == 'study', 
            'selected_option_ids': selected_option_ids,
            'short_answer_text': short_answer
        }
        
        options_html = render_to_string('student/question_options.html', context, request=request)
        
        question_data = {
            'id': question.id,
            'question_text': question.text,
            'question_format': question.answer_format,
            'options_html': options_html,
            'question_image_url': question.image.url if question.image else '',
            'user_selected_options': selected_option_ids,
            'user_short_answer': short_answer,
            'is_marked_for_review': is_marked,
            'question_number': q_order, # Savol tartib raqami
        }
        return question_data
        
    except Question.DoesNotExist:
        return {'error': "Savol bu bo'limda topilmadi."}
    except Exception as e:
        logger.error(f"get_question_data xatosi: {str(e)}", exc_info=True)
        return {'error': f'Savol yuklashda server xatosi: {str(e)}'}
    
# =========================================================================
# ⭐️ 4. YAKUNIY NATIJALAR (view_result_detail) - Oldingi tuzatilgan funksiya
# =========================================================================

@login_required(login_url='login')
def view_result_detail(request, slug, attempt_id):
    """
    Foydalanuvchining imtihon natijalari – faqat o‘z markazida
    """
    # 1. MARKAZ TEKSHIRISH
    center = get_object_or_404(Center, slug=slug)
    if request.user.center is None or request.user.center != center:
        messages.error(request, "Bu sahifaga kirish huquqingiz yo‘q.")
        return redirect('dashboard',slug=request.user.center.slug)

    try:
        # 2. URINISH TEKSHIRISH
        attempt = get_object_or_404(
            UserAttempt.objects.select_related('exam').prefetch_related('section_attempts'), 
            id=attempt_id, 
            user=request.user,
            exam__center=center  
        )
    except Exception:
        messages.error(request, "Natija topilmadi yoki sizga tegishli emas.")
        return redirect('dashboard',slug=request.user.center.slug)
        
    exam = attempt.exam

    # 3. BO‘LIMLARNING TARTIBI
    sections_qs = attempt.section_attempts.select_related('section').annotate(
        section_order_value=Subquery(
            ExamSectionOrder.objects.filter(
                exam=exam,
                exam_section=OuterRef('section')
            ).values('order')[:1] 
        )
    ).order_by('section_order_value') 
    
    is_subject_exam = getattr(exam, 'is_subject_exam', False)

    # 4. TO‘G‘RI JAVOBLAR
    correct_answers_by_section_attempt = UserAnswer.objects.filter(
        attempt_section__attempt=attempt, is_correct=True
    ).values('attempt_section__id').annotate(correct_count=Count('id'))
    correct_map = {item['attempt_section__id']: item['correct_count'] for item in correct_answers_by_section_attempt}
    
    ebrw_raw = {'M1': None, 'M2': None, 'total': 0}
    math_raw = {'M1': None, 'M2': None, 'total': 0}
    total_correct = 0
    total_questions = 0
    section_analysis_list = [] 
    
    for section_attempt in sections_qs:
        section_type = section_attempt.section.section_type
        correct = correct_map.get(section_attempt.id, 0)
        section_questions = section_attempt.questions.count()

        if section_questions == 0: 
            continue

        total_correct += correct
        total_questions += section_questions
        
        if section_type == EBRW_M1: 
            ebrw_raw.update({'M1': correct, 'total': ebrw_raw['total'] + correct})
        elif section_type == EBRW_M2: 
            ebrw_raw.update({'M2': correct, 'total': ebrw_raw['total'] + correct})
        elif section_type == MATH_M1: 
            math_raw.update({'M1': correct, 'total': math_raw['total'] + correct})
        elif section_type == MATH_M2: 
            math_raw.update({'M2': correct, 'total': math_raw['total'] + correct})
        
        user_answers_for_nav = UserAnswer.objects.filter(
            attempt_section=section_attempt
        ).select_related('question').order_by('answered_at')

        section_analysis_list.append({
            'section_attempt_id': section_attempt.id,
            'section_name': section_attempt.section.get_section_type_display(), 
            'user_answers_nav': user_answers_for_nav,
            'correct_count': correct,
            'total_count': section_questions,
        })

    # 5. YAKUNIY BALL VA FOIZ
    final_ebrw_score = attempt.final_ebrw_score
    final_math_score = attempt.final_math_score
    total_sat_score = attempt.final_total_score
    
    can_view_solution = True  # Doimiy ruxsat

    total_percentage = round((total_correct / total_questions * 100)) if total_questions > 0 else 0
    total_omitted = UserAnswer.objects.filter(attempt_section__attempt=attempt, is_correct=None).count()
    total_incorrect = total_questions - total_correct - total_omitted
    
    context = {
        'center': center,
        'attempt': attempt,
        'section_analysis_list': section_analysis_list,
        'is_subject_exam': is_subject_exam,
        'can_view_solution': can_view_solution,
        'total_sat_score': total_sat_score, 
        'ebrw_score': final_ebrw_score,
        'math_score': final_math_score,
        'total_correct': total_correct,
        'total_incorrect': total_incorrect,
        'total_omitted': total_omitted,
        'total_questions': total_questions,
        'total_percentage': total_percentage,
        'pending_message': None if attempt.is_completed else "Imtihon hali yakunlanmagan. Ballar taxminiy.",
    }
    return render(request, 'student/result_detail.html', context)

@login_required(login_url='login')
def exam_detail_view(request, slug, exam_id):
    """
    Imtihon tafsiloti – faqat o‘z markazida
    """
    # 1. MARKAZ TEKSHIRISH
    center = get_object_or_404(Center, slug=slug)
    if request.user.center is None or request.user.center != center:
        messages.error(request, "Bu sahifaga kirish huquqingiz yo‘q.")
        return redirect('index')

    # 2. IMTIHON TEKSHIRISH
    exam = get_object_or_404(
        Exam, 
        id=exam_id, 
        is_active=True,
        center=center  # MARKAZGA BOG‘LIQ!
    )
    user = request.user

    # 3. ROL TEKSHIRISH
    if not is_student(user): 
        messages.error(request, "Sizda bu imtihonni boshlash huquqi yo'q.")
        return redirect('index')

    # 4. PULLIK IMTIHON TEKSHIRISH
    user_can_start_exam = not exam.is_premium or \
        user.has_active_subscription() or \
        (hasattr(user, 'balance') and user.balance.exam_credits > 0)
    
    if exam.is_premium and not user_can_start_exam:
        messages.error(request, "Bu imtihon pullik. Obuna yoki kredit sotib oling.")
        return redirect('price', slug=slug)

    # 5. FLASHCARD IMTIHON
    flashcard_exam = exam.get_or_create_flashcard_exam()
    has_flashcard_exam = flashcard_exam is not None

    # 6. TUGALLANMAGAN URINISH
    existing_attempt = UserAttempt.objects.filter(
        user=request.user, 
        exam=exam, 
        is_completed=False
    ).first()

    context = {
        'center': center,
        'exam': exam,
        'has_flashcard_exam': has_flashcard_exam,
        'existing_attempt': existing_attempt,
    }
    return render(request, 'student/exam_detail.html', context)

def prepare_exam_data(exam_qs, request_user, center):
    """
    Exam querysetini talaba sahifasi uchun zarur ma'lumotlar bilan boyitadi.
    Faqat o‘z markazidagi imtihonlarni qaytaradi.
    """
    # 1. STATIC SAVOLLAR SONINI ANNOTATE QILISH (N+1 YO‘Q!)
    sections_with_counts = ExamSection.objects.filter(
        # TO'G'RILANDI: examsectionorder_set o'rniga to'g'ri related_name 'examsectionorder' ishlatildi
        examsectionorder__exam__center=center 
    ).annotate(
        actual_question_count=Count('examsectionstaticquestion', distinct=True)
    ).values('id', 'actual_question_count', 'duration_minutes', 'name', 'section_type')

    # ID → ma'lumot mapping
    section_map = {
        s['id']: {
            'actual_question_count': s['actual_question_count'],
            'duration_minutes': s['duration_minutes'],
            'name': s['name'],
            'type_display': dict(ExamSection.SECTION_TYPES).get(s['section_type'], s['section_type']),
            'is_math': 'math' in s['section_type'].lower(),
        }
        for s in sections_with_counts
    }

    # 2. TARTIB BO‘YICHA ORDER
    order_prefetch = Prefetch(
        # TO'G'RILANDI: Prefetch uchun ham 'examsectionorder_set' o'rniga 'examsectionorder' ishlatildi
        'examsectionorder',
        queryset=ExamSectionOrder.objects.select_related('exam_section').order_by('order'),
        to_attr='ordered_sections'
    )

    # 3. ASOSIY SO‘ROV – faqat o‘z markazidagi
    exams_with_data = exam_qs.filter(center=center).prefetch_related(
        order_prefetch,
        'flashcard_exam'
    ).select_related('teacher')

    # Foydalanuvchi premium kirish huquqiga egaligini tekshirish
    can_access_premium = request_user.has_active_subscription() or \
                         (hasattr(request_user, 'balance') and request_user.balance.exam_credits > 0)

    result_data = []
    for exam in exams_with_data:
        total_duration = 0
        total_questions = 0
        detailed_sections = []

        for order_obj in getattr(exam, 'ordered_sections', []):
            section = order_obj.exam_section
            section_info = section_map.get(section.id)

            if not section_info:
                continue

            actual_count = section_info['actual_question_count']
            total_duration += section_info['duration_minutes']
            total_questions += actual_count

            detailed_sections.append({
                'id': section.id,
                'name': section_info['name'],
                'type_display': section_info['type_display'],
                'duration_minutes': section_info['duration_minutes'],
                'actual_question_count': actual_count,
                'is_math': section_info['is_math'],
                'order': order_obj.order,
            })

        has_flashcard = hasattr(exam, 'flashcard_exam') and exam.flashcard_exam is not None

        result_data.append({
            'obj': exam,
            'has_flashcard_exam': has_flashcard,
            'total_duration': total_duration,
            'total_questions': total_questions,
            'sections': detailed_sections,
            'can_start_exam': not exam.is_premium or can_access_premium,
        })

    return result_data

@login_required(login_url='login')
def all_exams_view(request, slug):
    from django.shortcuts import get_object_or_404, redirect, render
    from django.contrib import messages
    from django.db.models import Count
    from datetime import datetime, timedelta
    from django.utils import timezone
    # prepare_exam_data funksiyasini ham import qilishingiz kerak

    # 1. MARKAZ TEKSHIRISH
    center = get_object_or_404(Center, slug=slug)
    
    if request.user.center is None or request.user.center != center:
        messages.error(request, "Bu sahifaga kirish huquqingiz yo‘q yoki markazingiz noto'g'ri.")
        return redirect('index') 

    # ... (Oy hisoblash qismi o'zgarishsiz) ...
    current_month = datetime.now().month
    months = [
        # ... (months ro'yxati) ...
    ]

    # 2. FAOL IMTIHONLAR
    # Note: select_related('teacher') N+1 muammosini hal qiladi
    base_exams = Exam.objects.filter(is_active=True, center=center).select_related('teacher')

    # 3. TUGALLANGAN IMTIHONLAR (ular ro'yxatdan chiqariladi)
    completed_exam_ids = UserAttempt.objects.filter(
        user=request.user, is_completed=True
    ).values_list('exam_id', flat=True) if request.user.is_authenticated else []
    
    # Umumiy imtihonlar: Faol va tugallanmagan
    available_exams = base_exams.exclude(id__in=completed_exam_ids)

    # 4. YANGI IMTIHONLAR (oxirgi 3 kun)
    three_days_ago = timezone.now() - timedelta(days=3)
    all_new_exams_qs = available_exams.filter(created_at__gte=three_days_ago).order_by('-created_at')

    # 5. MASHHUR IMTIHONLAR (10+ foydalanuvchi)
    all_popular_exams_qs = available_exams.annotate(
        user_count=Count('user_attempts__user', distinct=True) 
    ).filter(user_count__gte=10).order_by('-user_count') 

    # Yangi va Mashhur imtihonlarning ID'larini yig'ish (takrorlanishni bartaraf etish uchun)
    # 💡 MUHIM: values_list() qaytargan QuerySet ni ro'yxatga aylantirish shart emas, chunki Django ORM buni avtomatik qila oladi.
    # Ammo hozircha sizning Python List usulingizni saqlaymiz.
    new_exam_ids = list(all_new_exams_qs.values_list('id', flat=True))
    popular_exam_ids = list(all_popular_exams_qs.values_list('id', flat=True))

    # 6. QOLGAN IMTIHONLAR (Yuqoridagi ikkita kategoriyaga kirmagan)
    # Shu mantiqni saqlaymiz, chunki bu 'Barcha Imtihonlar' kategoriyasini 'Qolgan Imtihonlar' deb ajratadi.
    # Agar barcha imtihonlarni ko'rsatmoqchi bo'lsangiz, bu qatorni olib tashlash va pastdagini o'zgartirish kerak.
    # all_exams_qs = available_exams.exclude(id__in=new_exam_ids).exclude(id__in=popular_exam_ids).order_by('-created_at')

    # 💡 YANGI MANTIQ: Umumiy 'available_exams'ni to'liq ro'yxat sifatida uzatish
    # Agar Template'dagi "Barcha Imtihonlar" bo'limida *hamma* mavjud imtihonlar ko'rsatilishi kerak bo'lsa:
    all_exams_for_display = available_exams.order_by('-created_at') # 👈 Bu barcha mavjud imtihonlardir

    # 7. MA'LUMOTLARNI BOYITISH
    context = {
        'center': center,
        'selected_month': current_month,
        'months': months,
        
        # 'available_exams'dagi hamma imtihonlarni 'all_exams' qismiga uzatish
        'new_exams': prepare_exam_data(all_new_exams_qs, request.user, center),
        'popular_exams': prepare_exam_data(all_popular_exams_qs, request.user, center), 
        
        # ✅ TUZATISH: Endi bu hamma mavjud imtihonlarni o'z ichiga oladi
        'all_exams': prepare_exam_data(all_exams_for_display, request.user, center), 
        'three_days_ago': three_days_ago,
    }

    return render(request, 'student/all_exams.html', context)

# ⭐️ YENGI/YANGILANGAN FUNKSIYA: Status bo'yicha kartochkalarni jadvalda ko'rsatish
@login_required
def flashcard_status_list_view(request, slug, status_filter):
    # 1. MARKAZ OBYEKTINI OLISH VA NAMETERRORNI TUZATISH
    try:
        center = get_object_or_404(Center, slug=slug)
    except NameError:
        # Agar Center import qilinmagan bo'lsa, xato beradi.
        # Amalda, yuqorida Center import qilingan bo'lishi kerak.
        # NameError ni oldini olish uchun yozildi.
        return redirect('index') 
    
    # 2. Xavfsizlik tekshiruvi
    if request.user.center != center:
        messages.error(request, "Bu markaz kartochkalariga kirishga ruxsatingiz yo'q.")
        return redirect('index')

    valid_statuses = ['learning', 'learned', 'new']
    if status_filter not in valid_statuses:
        messages.error(request, "Noto‘g‘ri status filtri.")
        return redirect('my_flashcards', slug=slug)

    title_map = {
        'learned': "O'zlashtirilgan kartochkalar",
        'learning': "O'rganilayotgan kartochkalar",
        'new': "Yangi kartochkalar"
    }
    page_title = title_map[status_filter]

    # 3. ASOSIY SO'ROV: Markaz mantiqiga moslash
    # Flashcard'lar center orqali filtrlangan (author/creator orqali emas)
    base_qs = Flashcard.objects.filter(center=center).select_related('author') 

    if status_filter == 'new':
        # Yangi kartochkalar: Foydalanuvchi hali status bermagan kartochkalar
        flashcards_qs = base_qs.exclude(user_statuses__user=request.user).order_by('id')
        status_data = {}
    else:
        # O'rganilgan/O'rganilayotgan kartochkalar
        flashcards_qs = base_qs.filter(
            user_statuses__user=request.user,
            user_statuses__status=status_filter
        ).distinct().order_by('id')
        
        # Holat ma'lumotlarini olish
        statuses = UserFlashcardStatus.objects.filter(
            user=request.user,
            flashcard__in=flashcards_qs
        ).values('flashcard_id', 'repetition_count', 'ease_factor', 'review_interval', 'next_review_at', 'last_quality_rating')
        status_data = {s['flashcard_id']: s for s in statuses}

    flashcards_list = []
    for fc in flashcards_qs:
        info = status_data.get(fc.id, {})
        next_review = info.get('next_review_at')
        time_until = ""
        
        # Vaqtni hisoblash mantiqi
        if next_review and next_review > timezone.now():
            delta = next_review - timezone.now()
            if delta < timedelta(hours=24):
                time_until = f"({int(delta.total_seconds() // 3600)} soat)"
            elif delta < timedelta(days=30):
                time_until = f"({delta.days} kun)"
            else:
                time_until = f"({int(delta.days // 30)} oy)"
        elif next_review and next_review <= timezone.now():
            time_until = "(Hozir)"

        flashcards_list.append({
            'id': fc.id,
            # Xavfsizlik uchun tozalash (bleach/html)
            'english_content': bleach.clean(html.unescape(fc.english_content), tags=[], strip=True),
            'uzbek_meaning': bleach.clean(html.unescape(fc.uzbek_meaning), tags=[], strip=True),
            'repetition_count': info.get('repetition_count', 0),
            'ease_factor': f"{info.get('ease_factor', 2.5):.1f}",
            'review_interval': info.get('review_interval', 0),
            'next_review_at': next_review,
            'next_review_time_until': time_until,
            'last_rating': info.get('last_quality_rating', 0),
        })

    context = {
        'center': center,
        'page_title': page_title,
        'flashcards_list': flashcards_list,
        'status_filter': status_filter
    }
    return render(request, 'student/flashcard_list_table.html', context)

# =========================================================================
# ⭐️ 4. MY_FLASHCARDS_VIEW (Statistika sahifasi) (Render View)
# =========================================================================

@login_required
def my_flashcards_view(request, slug):
    center = get_object_or_404(Center, slug=slug)
    
    if request.user.center != center:
        # Markazi belgilanmagan foydalanuvchilar (`request.user.center = None`) uchun 
        # bu qismda Attribute Error berilmasligi uchun oldin tekshirish qilingan
        return redirect('index')

    # Faqat markazga tegishli KARTALARNI FILTRLASH UCHUN BAZA QUERYSET'I
    # Endi author orqali emas, Flashcard modelidagi center maydoni orqali filtrlanadi!
    center_flashcards_qs = Flashcard.objects.filter(center=center)

    # 1. Umumiy Flashcard hisobi
    total_flashcards = center_flashcards_qs.count()

    # 2. UserFlashcardStatus hisobi: Endi Flashcardning centeriga bog'lanadi
    statuses = UserFlashcardStatus.objects.filter(
        user=request.user,
        # TUZATILDI: flashcard__center ishlatildi!
        flashcard__center=center 
    ).values('status').annotate(count=Count('id'))

    status_map = {s['status']: s['count'] for s in statuses}
    learned_count = status_map.get('learned', 0)
    learning_count = status_map.get('learning', 0)
    seen_count = learned_count + learning_count
    new_count = max(0, total_flashcards - seen_count)

    # 3. Review needed hisobi: flashcard__center ishlatildi
    review_needed_count = UserFlashcardStatus.objects.filter(
        user=request.user,
        # TUZATILDI: flashcard__center ishlatildi!
        flashcard__center=center,
        next_review_at__lte=timezone.now()
    ).count()

    # 4. Next review object: flashcard__center ishlatildi
    next_review_obj = UserFlashcardStatus.objects.filter(
        user=request.user,
        # TUZATILDI: flashcard__center ishlatildi!
        flashcard__center=center,
        next_review_at__gt=timezone.now()
    ).order_by('next_review_at').first()
    next_review_at = next_review_obj.next_review_at if next_review_obj else None

    # Foizlar (o'zgarishsiz)
    # ...

    if total_flashcards > 0:
        learned_percentage = round((learned_count / total_flashcards) * 100)
        learning_percentage = round((learning_count / total_flashcards) * 100)
        new_percentage = 100 - learned_percentage - learning_percentage
    else:
        learned_percentage = learning_percentage = new_percentage = 0

    context = {
        'center': center,
        'total_flashcards': total_flashcards,
        'learned_count': learned_count,
        'learning_count': learning_count,
        'new_count': new_count,
        'review_needed_count': review_needed_count,
        'next_review_at': next_review_at,
        'learned_percentage': learned_percentage,
        'learning_percentage': learning_percentage,
        'new_percentage': new_percentage,
    }
    return render(request, 'student/my_flashcards.html', context)

# =========================================================================
# ⭐️ 5. PRACTICE_FLASHCARDS_VIEW (O'rganilayotgan/O'zlashtirilgan uchun)
# =========================================================================

@login_required
def practice_flashcards_view(request, slug, status_filter):
    center = get_object_or_404(Center, slug=slug)
    if request.user.center != center:
        return redirect('index')

    if status_filter not in ['learning', 'learned', 'new', 'review']:
        messages.error(request, "Noto‘g‘ri status.")
        return redirect('my_flashcards', slug=slug)

    # Flashcard.center orqali filtrlash to'g'ri o'rnatilgan
    base_qs = Flashcard.objects.filter(center=center)

    if status_filter == 'learning':
        title = "O'rganilayotganlarni Takrorlash"
        qs = base_qs.filter(user_statuses__user=request.user, user_statuses__status='learning')
    elif status_filter == 'learned':
        title = "O'zlashtirilganlarni Mustahkamlash"
        qs = base_qs.filter(user_statuses__user=request.user, user_statuses__status='learned')
    elif status_filter == 'review':
        title = "Bugungi Takrorlash"
        qs = base_qs.filter(user_statuses__user=request.user, user_statuses__next_review_at__lte=timezone.now())
    else:  # new
        title = "Yangi So'zlarni O'rganish"
        qs = base_qs.exclude(user_statuses__user=request.user)

    if not qs.exists():
        messages.info(request, f"{title} uchun kartochka yo‘q.")
        return redirect('my_flashcards', slug=slug)

    # TUZATILDI: 'questions' o'rniga 'qs' (amaliyot uchun tanlangan kartochkalar) ishlatildi
    statuses = UserFlashcardStatus.objects.filter(
        user=request.user, flashcard__in=qs).values('flashcard_id', 'repetition_count')
    status_map = {s['flashcard_id']: s['repetition_count'] for s in statuses}

    flashcards_list = [
        {
            'id': fc.id,
            'english_content': bleach.clean(fc.english_content, tags=[], strip=True),
            'uzbek_meaning': bleach.clean(fc.uzbek_meaning, tags=[], strip=True),
            'context_sentence': bleach.clean(fc.context_sentence, tags=[], strip=True) if fc.context_sentence else '',
            'repetition_count': status_map.get(fc.id, 0),
        }
        for fc in qs # qs bu yerda Flashcard obyektlari QuerySet'i
    ]

    context = {
        'center': center,
        'session_title': title,
        'flashcard_exam': {'title': title, 'id': 0},
        'flashcards_json': json.dumps(flashcards_list),
        'total_flashcards': len(flashcards_list),
        'is_practice_session': True,
    }
    return render(request, 'student/flashcard_exam.html', context)

@login_required
def start_flashcards_view(request, slug, exam_id):
    center = get_object_or_404(Center, slug=slug)
    if request.user.center != center:
        return redirect('index')

    exam = get_object_or_404(Exam, id=exam_id, is_active=True, center=center)

    if exam.is_premium and not (
        UserSubscription.objects.filter(user=request.user, end_date__gt=timezone.now()).exists() or
        UserBalance.objects.filter(user=request.user, exam_credits__gt=0).exists()
    ):
        messages.error(request, "Pullik imtihon. Obuna yoki kredit kerak.")
        return redirect('price', slug=slug)

    try:
        flashcard_exam = exam.get_or_create_flashcard_exam()
    except Exception:
        messages.error(request, "Flashcard yaratishda xato.")
        return redirect('exam_detail', slug=slug, exam_id=exam.id)

    if not flashcard_exam or not flashcard_exam.flashcards.filter(creator__center=center).exists():
        messages.info(request, "Bu imtihonda kartochka yo‘q.")
        return redirect('exam_detail', slug=slug, exam_id=exam.id)

    return redirect('flashcard_exam_view', slug=slug, exam_id=exam.id)

@login_required
def flashcard_exam_view(request, slug, exam_id):
    from django.shortcuts import get_object_or_404, redirect, render
    from django.db.models import Q
    from django.utils import timezone
    import json
    import bleach
    # UserFlashcardStatus modelini import qilishni unutmang

    center = get_object_or_404(Center, slug=slug)
    if request.user.center != center:
        return redirect('index')

    flashcard_exam = get_object_or_404(
        FlashcardExam,
        source_exam__id=exam_id,
        source_exam__center=center
    )

    user = request.user
    title = f"{flashcard_exam.source_exam.title} – Takrorlash"

    # 'author' ishlatildi (oldindan to'g'irlangan)
    flashcards_qs = flashcard_exam.flashcards.filter(author__center=center) 

    # 🛑 ASOSIY TUZATISH: Endi 'if/else' shartidan qat'iy nazar, 
    # to_review har doim barcha mavjud kartochkalarni tasodifiy tartibda oladi.
    # is_exam_review ning mantiqi (hamma kartochkani olish) endi har doim qo'llaniladi.
    to_review = flashcards_qs.order_by('?')
    
    # Endi to_review barcha Flashcardlarni o'z ichiga olganligi sababli, 
    # keyingi takrorlash vaqtini hisoblash mantiqi (pastda) o'zgarishsiz qoldiriladi
    # va avtomatik ravishda ishlamaydi (chunki flashcards_list bo'sh bo'lmaydi),
    # bu esa mantiqni yanada soddalashtiradi.

    statuses = UserFlashcardStatus.objects.filter(
        user=user, flashcard__in=to_review
    ).values('flashcard_id', 'repetition_count')
    status_map = {s['flashcard_id']: s['repetition_count'] for s in statuses}

    flashcards_list = [
        {
            'id': fc.id,
            'english_content': bleach.clean(fc.english_content, tags=[], strip=True),
            'uzbek_meaning': bleach.clean(fc.uzbek_meaning, tags=[], strip=True),
            'context_sentence': bleach.clean(fc.context_sentence, tags=[], strip=True) if fc.context_sentence else '',
            'repetition_count': status_map.get(fc.id, 0),
        }
        for fc in to_review
    ]

    # next_review_at mantiqiy bloki, agar 'flashcards_list' bo'sh bo'lmasa, ishlamaydi.
    # Agar flashcard_exam da kartochkalar bo'lsa, 'next_review_at' doim 'None' bo'lib qoladi, bu maqsadga muvofiq.
    next_review_at = None
    if not flashcards_list and not flashcard_exam.is_exam_review:
        obj = UserFlashcardStatus.objects.filter(
            user=user, flashcard__author__center=center, next_review_at__gt=timezone.now() 
        ).order_by('next_review_at').first()
        if obj:
            next_review_at = obj.next_review_at

    context = {
        'center': center,
        'session_title': title,
        'flashcard_exam': flashcard_exam,
        'flashcards_json': json.dumps(flashcards_list),
        'total_flashcards': len(flashcards_list),
        'next_review_at': next_review_at,
        'is_practice_session': True, # is_exam_review emas, balki True qilinadi, chunki bu doimiy mashg'ulot
    }
    return render(request, 'student/flashcard_exam.html', context)

@login_required
@require_POST 
def update_flashcard_progress(request, slug):
    # 1. Slug orqali Center obyektini olish
    center = get_object_or_404(Center, slug=slug)
    
    # 2. Xavfsizlik tekshiruvi (Userning markazi slug bilan mos kelishi)
    if request.user.center != center:
        return JsonResponse({'success': False, 'error': 'Ruxsat yo‘q'}, status=403)

    try:
        data = json.loads(request.body)
        flashcard_id = data.get('flashcard_id')
        user_response = data.get('user_response') # 'known' yoki 'unknown'

        if not flashcard_id or user_response not in ['known', 'unknown']:
            return JsonResponse({'success': False, 'error': 'Ma‘lumotlar to‘liq emas'}, status=400)
        
        # Flashcard obyektini olish (Markazga bog'lab xavfsizlikni kuchaytiramiz)
        flashcard = get_object_or_404(
            Flashcard, id=flashcard_id, center=center
        )
        user = request.user
        now = timezone.now()

        # UserFlashcardStatus obyektini yaratish yoki olish
        status, created = UserFlashcardStatus.objects.get_or_create(
            user=user, flashcard=flashcard,
            defaults={
                'status': 'learning', 'review_interval': 1, 'ease_factor': 2.5,
                'repetition_count': 0, 'last_reviewed_at': now,
                'next_review_at': now + timedelta(days=1)
            }
        )

        min_interval = 1
        # Review muddatida ekanligini tekshirish
        is_on_schedule = status.next_review_at <= now if status.next_review_at else True

        if user_response == 'known':
            # SM-2 asosidagi mantiq (Sizning kodingiz)
            status.ease_factor = max(1.3, status.ease_factor + 0.1)

            if is_on_schedule:
                if status.repetition_count == 0:
                    new_interval = 1
                elif status.repetition_count == 1:
                    new_interval = 6
                else:
                    # Keyingi intervalni hisoblash
                    new_interval = status.review_interval * status.ease_factor
                
                status.repetition_count += 1
                status.review_interval = max(min_interval, round(new_interval))
                status.status = 'learned' if status.repetition_count >= 2 else 'learning' # 2-takrorlashdan keyin 'learned' bo'lishi mumkin
                status.next_review_at = now + timedelta(days=status.review_interval)
                status.last_quality_rating = 5
            else:
                # Muddatidan oldin takrorlash
                if status.status == 'learning':
                    status.status = 'learned'
                status.last_quality_rating = 5
            
            # Muddatidan oldin takrorlashda ham last_reviewed_at yangilanadi
            status.last_reviewed_at = now
            status.save()

            return JsonResponse({
                'success': True,
                'status': status.status,
                'next_review': status.next_review_at.isoformat(),
                'repetition_count': status.repetition_count,
            })

        else:  # unknown
            # Repetitsiyani 0 ga qaytarish
            status.status = 'learning'
            status.repetition_count = 0
            status.review_interval = min_interval
            status.ease_factor = max(1.3, status.ease_factor - 0.2)
            status.last_reviewed_at = now
            status.next_review_at = now + timedelta(days=status.review_interval)
            status.last_quality_rating = 0
            status.save()

            return JsonResponse({
                'success': True,
                'status': status.status,
                'next_review': status.next_review_at.isoformat(),
                'repetition_count': status.repetition_count,
            })

    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Noto‘g‘ri JSON formati'}, status=400)
    except Exception as e:
        logger.error(f"Flashcard update error: {e}")
        return JsonResponse({'success': False, 'error': f'Server xatosi: {e}'}, status=500)

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
def get_answer_detail_ajax(request, slug):
    center = get_object_or_404(Center, slug=slug)
    if request.user.center != center:
        return JsonResponse({'error': 'Ruxsat yo‘q'}, status=403)

    user_answer_id = request.GET.get('user_answer_id')
    is_subject_exam = request.GET.get('is_subject_exam') == 'true'
    can_view_solution = request.GET.get('can_view_solution') == 'true'

    if not user_answer_id:
        return JsonResponse({'error': 'Savol ID si berilmadi'}, status=400)

    try:
        user_answer = UserAnswer.objects.select_related(
            'question', 'question__passage', 'question__solution', 'attempt_section__attempt__exam'
        ).prefetch_related(
            'selected_options', 'question__options'
        ).get(
            id=user_answer_id,
            attempt_section__attempt__user=request.user,
            attempt_section__attempt__exam__center=center  # MARKAZ TEKSHIRISH!
        )

        # Yechim ko‘rilganmi?
        solution_viewed = UserSolutionView.objects.filter(
            user=request.user, question=user_answer.question
        ).exists()
        is_solution_free = getattr(user_answer.question, 'is_solution_free', False)

        # RUXSAT MANTIQI
        if is_subject_exam:
            allow_solution_display = can_view_solution
        else:
            allow_solution_display = is_solution_free or solution_viewed

        # VARIANTLAR
        options_with_status = []
        selected_ids = set(user_answer.selected_options.values_list('id', flat=True))
        for index, option in enumerate(user_answer.question.options.all()):
            options_with_status.append({
                'option': option,
                'is_user_selected': option.id in selected_ids,
                'is_correct': getattr(option, 'is_correct', False),
                'letter': chr(65 + index),
            })

        context = {
            'center': center,
            'user_answer': user_answer,
            'question': user_answer.question,
            'options_with_status': options_with_status,
            'allow_solution_display': allow_solution_display,
            'solution_viewed': solution_viewed,
            'is_solution_free': is_solution_free,
            'is_subject_exam': is_subject_exam,
            'attempt': user_answer.attempt_section.attempt,
        }

        html = render_to_string('partials/answer_detail_card.html', context, request=request)
        return JsonResponse({'html': html})

    except UserAnswer.DoesNotExist:
        return JsonResponse({'error': 'Javob topilmadi'}, status=404)
    except Exception as e:
        return JsonResponse({'error': 'Server xatosi'}, status=500)


@login_required(login_url='login')
def view_solution(request, slug, question_id):
    center = get_object_or_404(Center, slug=slug)
    if request.user.center != center:
        messages.error(request, "Ruxsat yo‘q.")
        return redirect('dashboard',slug=request.user.center.slug)

    question = get_object_or_404(Question, id=question_id)
    attempt_id = request.GET.get('attempt_id')

    if not attempt_id:
        messages.error(request, "Imtihon ID si topilmadi.")
        return redirect('dashboard',slug=request.user.center.slug)

    attempt = get_object_or_404(
        UserAttempt,
        id=attempt_id,
        user=request.user,
        exam__center=center  # MARKAZ TEKSHIRISH!
    )

    is_subject_exam = getattr(attempt.exam, 'is_subject_exam', False)
    solution_viewed = UserSolutionView.objects.filter(user=request.user, question=question).exists()
    is_solution_free = getattr(question, 'is_solution_free', False)

    # 1. MAVZU IMTIHONI (60% sharti)
    if is_subject_exam:
        total_questions = UserAnswer.objects.filter(attempt_section__attempt=attempt).count()
        correct_answers = UserAnswer.objects.filter(attempt_section__attempt=attempt, is_correct=True).count()
        total_percentage = (correct_answers / total_questions) * 100 if total_questions > 0 else 0

        if total_percentage >= 60:
            if not solution_viewed:
                UserSolutionView.objects.create(user=request.user, question=question, credit_spent=False)
                messages.success(request, "60% dan o‘tdingiz – yechim bepul!")
        else:
            messages.error(request, f"60% kerak! Siz: {total_percentage:.1f}%")
            return redirect('view_result_detail', slug=center.slug, attempt_id=attempt_id)

        return redirect('view_result_detail', slug=center.slug, attempt_id=attempt_id)

    # 2. DSAT / ODDIY IMTIHON
    if is_solution_free or solution_viewed:
        if not solution_viewed:
            UserSolutionView.objects.create(user=request.user, question=question, credit_spent=False)
        return redirect('view_result_detail', slug=center.slug, attempt_id=attempt_id)

    # KREDIT TEKSHIRISH
    try:
        user_balance = UserBalance.objects.select_for_update().get(user=request.user)
        if user_balance.solution_view_credits > 0:
            with transaction.atomic():
                UserSolutionView.objects.create(user=request.user, question=question, credit_spent=True)
                user_balance.solution_view_credits -= 1
                user_balance.save()
            messages.success(request, f"1 kredit sarflandi. Qoldi: {user_balance.solution_view_credits}")
        else:
            messages.error(request, "Kredit yetarli emas!")
    except UserBalance.DoesNotExist:
        messages.error(request, "Balans topilmadi.")
    
    return redirect('view_result_detail', slug=center.slug, attempt_id=attempt_id)

@login_required(login_url='login')
@user_passes_test(is_teacher, login_url='index')
def teacher_results(request, slug): # 🎯 SLUG QO'SHILDI
    """Ustozning imtihonlari va talabalar natijalarini ko'rish (Markazga bog'langan)."""
    user = request.user
    center = get_object_or_404(Center, slug=slug)
    
    # 1. Ruxsatni tekshirish (Faqat shu markaz o'qituvchisi)
    if user.center != center and not user.is_staff:
        messages.error(request, "Sizda bu markaz natijalarini ko'rish huquqi yo'q.")
        return redirect('dashboard',slug=request.user.center.slug)
    
    # 2. Faqat shu o'qituvchiga tegishli (VA uning markaziga bog'langan) imtihonlarni yuklash
    # Imtihonlar Teacher orqali, Teacher esa Center orqali filtrlanadi.
    my_exams = Exam.objects.filter(teacher=user, teacher__center=center).order_by('-created_at').prefetch_related('sections')
    exam_results = []
    
    for exam in my_exams:
        # 3. Faqat shu imtihonga tegishli urinishlarni yuklash
        attempts = UserAttempt.objects.filter(exam=exam).select_related('user').prefetch_related(
            'section_attempts' 
        ).order_by('-completed_at')
        
        attempt_details = []
        all_sections = list(exam.sections.all())
        
        # Umumiy savollar sonini hisoblash (samaradorlik uchun tashqarida)
        try:
            # get_section_questions funksiyasi to'g'ri ishlashi kerak
            total_questions_in_exam = sum(len(get_section_questions(section, exam)) for section in all_sections)
        except NameError:
            # Agar funksiya topilmasa, alternativ hisoblash
            # Bu qism faqat avvalgi koddagi mavhum 'get_section_questions' ga bog'liqlikni yengillashtiradi
            total_questions_in_exam = 0 
            # Lekin shablon ishlashi uchun to'g'ri qiymat bo'lishi kerak.
            # Real loyihada bu funksiya mavjud va ishonchli deb faraz qilamiz.
            
        
        for attempt in attempts:
            
            # Agar attempt to'liq tugallanmagan bo'lsa, natijani ko'rsatmaslik yaxshiroq
            if not attempt.is_completed:
                continue

            # Agar markaz imtihoni bo'lmasa (DSAT), ballni ko'rsatamiz. Aks holda foizni
            score_to_display = attempt.final_total_score if not exam.is_subject_exam else f"{attempt.correct_percentage:.1f}%"
            
            # Agar savollar soni 0 bo'lsa (yoki statik bo'limda savol tanlanmagan bo'lsa)
            if total_questions_in_exam == 0:
                correct_answers = UserAnswer.objects.filter(attempt_section__attempt=attempt, is_correct=True).count()
                total_attempt_questions = UserAnswer.objects.filter(attempt_section__attempt=attempt).count()
                percentage = (correct_answers / total_attempt_questions * 100) if total_attempt_questions > 0 else 0
                total_questions_display = total_attempt_questions
            else:
                correct_answers = sum(section.correct_answers_count for section in attempt.section_attempts.all())
                percentage = (correct_answers / total_questions_in_exam * 100)
                total_questions_display = total_questions_in_exam

            incorrect_answers = total_questions_display - correct_answers
            
            attempt_details.append({
                'attempt_id': attempt.id,
                'user_username': attempt.user.username,
                'correct_answers': correct_answers,
                'incorrect_answers': incorrect_answers,
                'total_questions': total_questions_display,
                'score': score_to_display, # Ball (DSAT) yoki Foiz (Mavzu)
                'percentage': round(percentage, 2),
                'completed_at': attempt.completed_at,
            })
            
        if attempt_details:
            exam_results.append({
                'title': exam.title,
                'attempts': attempt_details,
                'is_subject_exam': exam.is_subject_exam,
            })
    
    context = {
        'results': exam_results,
        'center': center, # 🎯 Shablonlar uchun center obyekti
        'page_title': f"{center.name} Markazi Talabalar Natijalari"
    }
    return render(request, 'teacher_results.html', context)

@login_required(login_url='login')
@user_passes_test(is_teacher, login_url='index')
def teacher_view_result_detail(request, slug, attempt_id): # 🎯 SLUG QO'SHILDI
    """O'qituvchi uchun talaba natijasining batafsil ko'rinishi."""
    user = request.user
    center = get_object_or_404(Center, slug=slug)

    # 1. Urinishni yuklash
    try:
        attempt = get_object_or_404(UserAttempt, id=attempt_id)
    except Exception:
        messages.error(request, "Natija topilmadi.")
        # Redirect qilishda SLUG ni uzatish
        return redirect('teacher_results', slug=center.slug) 

    # 2. Ruxsatni tekshirish (Urinish o'qituvchining markaziga tegishli ekanligini tekshirish)
    if attempt.exam.teacher != user or attempt.exam.teacher.center != center:
        messages.error(request, "Siz bu natijani ko'rish huquqiga ega emassiz.")
        return render(request, '403.html', {'message': "Siz bu natijani ko'rish huquqiga ega emassiz."})

    # ... (Qolgan hisob-kitob mantig'i o'zgarishsiz qoladi) ...
    total_questions = 0
    total_correct_answers = 0

    # Ma'lumotlarni to'g'ri hisoblash uchun
    total_questions = UserAnswer.objects.filter(attempt_section__attempt=attempt).count()
    total_correct_answers = UserAnswer.objects.filter(attempt_section__attempt=attempt, is_correct=True).count()
    
    total_incorrect_answers = total_questions - total_correct_answers
    total_omitted_answers = UserAnswer.objects.filter(attempt_section__attempt=attempt, is_correct=None).count()


    # 4. Savol-javoblarni tahlil qilish uchun yuklash
    user_answers = UserAnswer.objects.filter(attempt_section__attempt=attempt).order_by('question__id').select_related('question').prefetch_related('selected_options', 'question__options')

    # 5. Har bir javobga tahlil ma'lumotlarini qo'shish (kerak bo'lsa)
    for user_answer in user_answers:
        # ... (options_with_status mantig'i) ...
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
        'total_omitted_answers': total_omitted_answers,
        'total_questions': total_questions,
        'center': center, # 🎯 Shablonlar uchun center obyekti
        'ability_estimate': getattr(attempt, 'ability_estimate', 'Noma‘lum'), 
    }
    # Mavzu testi bo'lsa, maxsus shablon ishlatish kerak bo'lishi mumkin.
    is_subject_exam = getattr(attempt.exam, 'is_subject_exam', False)
    template_name = 'teacher_subject_result_detail.html' if is_subject_exam else 'teacher_test_result_detail.html'

    return render(request, template_name, context)

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
def my_questions(request, slug):
    # 1. Markazni slug bo'yicha topish
    center = get_object_or_404(Center, slug=slug)

    # 2. Xavfsizlik Tekshiruvi
    if request.user.center is None or request.user.center != center:
        messages.error(request, "Bu markazga kirish huquqingiz yo‘q yoki sizga markaz biriktirilmagan.")
        return redirect('index')

    # 3. Topic ma'lumotlarini olish va Count Annotatsiyasini Qo'llash
    topics = Topic.objects.filter(
        center=center, 
        teacher=request.user
    ).annotate(
        # Munosabat: Topic -> subtopics -> questions
        question_count=Count('subtopics__questions'), 
        subtopic_count=Count('subtopics') 
    ).order_by('order')

    # 4. Mavzulanmagan savollar sonini hisoblash
    uncategorized_questions_count = Question.objects.filter(
        center=center, 
        author=request.user, 
        subtopic__isnull=True
    ).count()

    # 5. Kontekstni shakllantirish
    context = {
        'topics': topics,
        'uncategorized_questions_count': uncategorized_questions_count,
        'center': center,
        'user': request.user,
    }
    return render(request, 'questions/my_questions.html', context)

@login_required(login_url='login')
@user_passes_test(is_teacher, login_url='index')
def topic_detail(request, slug, topic_id): # 💡 slug qo'shildi
    center = get_object_or_404(Center, slug=slug)
    
    if request.user.center is None or request.user.center != center:
        messages.error(request, "Bu markazga kirish huquqingiz yo‘q yoki sizga markaz biriktirilmagan.")
        return redirect('index')

    # Topicni markaz va ustoz bo'yicha cheklash
    topic = get_object_or_404(Topic, id=topic_id, center=center, teacher=request.user)
    
    # Subtopiclarni markaz va topic bo'yicha cheklash
    subtopics = Subtopic.objects.filter(topic=topic, center=center).annotate(question_count=Count('questions'))

    context = {
        'topic': topic,
        'subtopics': subtopics,
        'center': center,
        'user': request.user,
    }
    return render(request, 'questions/topic_detail.html', context)

@login_required(login_url='login')
@user_passes_test(is_teacher, login_url='index')
def subtopic_questions(request, slug, subtopic_id):
    center = get_object_or_404(Center, slug=slug)
    
    if request.user.center is None or request.user.center != center:
        messages.error(request, "Bu markazga kirish huquqingiz yo‘q yoki sizga markaz biriktirilmagan.")
        return redirect('index')

    subtopic = get_object_or_404(Subtopic, id=subtopic_id, center=center)
    # Savollarni markaz va muallif bo'yicha cheklash
    questions = Question.objects.filter(subtopic=subtopic, center=center, author=request.user).order_by('-created_at')

    context = {
        'subtopic': subtopic,
        'questions': questions,
        'center': center,
        'user': request.user,
    }
    return render(request, 'questions/subtopic_questions.html', context)

@login_required(login_url='login')
@user_passes_test(is_teacher, login_url='index')
def uncategorized_questions(request, slug):
    """ Mavzulanmagan savollar ro'yxatini markaz bo'yicha ko'rsatadi. """
    center = get_object_or_404(Center, slug=slug)

    # Xavfsizlik Tekshiruvi
    if request.user.center is None or request.user.center != center:
        messages.error(request, "Bu markazga kirish huquqingiz yo‘q yoki sizga markaz biriktirilmagan.")
        return redirect('index')
        
    questions = Question.objects.filter(
        center=center, # Markazga bog'lash
        subtopic__isnull=True,
        author=request.user
    ).select_related(
        'difficulty_level',
        'passage',
        'parent_question',
        'center',
    ).prefetch_related(
        Prefetch('translations', queryset=QuestionTranslation.objects.filter(language='uz')),
        Prefetch('options', queryset=AnswerOption.objects.prefetch_related(
            Prefetch('translations', queryset=AnswerOptionTranslation.objects.filter(language='uz'))
        )),
        'tags',
        'flashcards',
    )
    
    context = {
        'questions': questions,
        'uncategorized_view': True,
        'center': center,
        # get_base_context dan keladigan ma'lumotlar
        **get_base_context(request) 
    }
    return render(request, 'questions/uncategorized_questions.html', context)

@login_required(login_url='login')
@user_passes_test(is_teacher, login_url='index')
def delete_topic(request, slug, topic_id): # 💡 slug qo'shildi
    center = get_object_or_404(Center, slug=slug)
    
    if request.user.center is None or request.user.center != center:
        messages.error(request, "Bu markazga kirish huquqingiz yo‘q yoki sizga markaz biriktirilmagan.")
        return redirect('index')

    # Markaz bo'yicha cheklash
    topic = get_object_or_404(Topic, id=topic_id, center=center, teacher=request.user) 
    
    if request.method == 'POST':
        delete_type = request.POST.get('delete_type')
        if delete_type == 'move':
            target_topic_id = request.POST.get('target_topic')
            if target_topic_id:
                # Target topicni ham markaz va ustoz bo'yicha cheklash
                target_topic = get_object_or_404(Topic, id=target_topic_id, center=center, teacher=request.user)
                moved_count = Subtopic.objects.filter(topic=topic).update(topic=target_topic)
                topic.delete()
                messages.success(request, f'"{topic.name}" mavzusidagi {moved_count} ta ichki mavzu "{target_topic.name}" ga ko‘chirildi va mavzu o‘chirildi.')
            else:
                messages.error(request, "Savollarni ko'chirish uchun mavzu tanlanmadi.")
        else:
            topic.delete()
            messages.success(request, f'"{topic.name}" mavzusi va unga tegishli barcha savollar o‘chirildi.')
        
        return redirect('my_questions', slug=center.slug) # 💡 Redirectda slug uzatildi

    questions_count = Question.objects.filter(subtopic__topic=topic).count()
    # all_topics filteriga center=center qoshildi
    all_topics = Topic.objects.filter(center=center, teacher=request.user).exclude(id=topic_id) 
    
    context = {
        'topic': topic,
        'questions_count': questions_count,
        'all_topics': all_topics,
        'center': center,
    }
    return render(request, 'topic/delete_topic.html', context)

@login_required(login_url='login')
@user_passes_test(is_teacher, login_url='index')
def delete_subtopic(request, slug, subtopic_id): # 💡 slug qo'shildi
    center = get_object_or_404(Center, slug=slug)
    
    if request.user.center is None or request.user.center != center:
        messages.error(request, "Bu markazga kirish huquqingiz yo‘q yoki sizga markaz biriktirilmagan.")
        return redirect('index')

    # Markaz bo'yicha cheklash
    subtopic = get_object_or_404(Subtopic, id=subtopic_id, center=center, topic__teacher=request.user) 
    
    if request.method == 'POST':
        delete_type = request.POST.get('delete_type')
        if delete_type == 'move':
            target_subtopic_id = request.POST.get('target_subtopic')
            if target_subtopic_id:
                # Target subtopicni ham markaz bo'yicha cheklash
                target_subtopic = get_object_or_404(Subtopic, id=target_subtopic_id, center=center, topic__teacher=request.user)
                moved_count = subtopic.questions.filter(center=center).update(subtopic=target_subtopic) # Markaz bo'yicha cheklab update qilish
                subtopic.delete()
                messages.success(request, f"{moved_count} ta savol '{target_subtopic.name}' ga ko'chirildi va ichki mavzu o'chirildi.")
            else:
                messages.error(request, "Savollarni ko'chirish uchun ichki mavzu tanlanmadi.")
        else:
            subtopic.delete()
            messages.success(request, "Ichki mavzu va unga tegishli barcha savollar o'chirildi.")
        
        return redirect('my_questions', slug=center.slug) # 💡 Redirectda slug uzatildi
        
    questions_count = subtopic.questions.filter(center=center).count() # Markaz bo'yicha cheklash
    # all_subtopics filteriga center=center qoshildi
    all_subtopics = Subtopic.objects.filter(center=center, topic__teacher=request.user).exclude(id=subtopic_id)
    
    context = {
        'subtopic': subtopic,
        'questions_count': questions_count,
        'all_subtopics': all_subtopics,
        'center': center,
    }
    return render(request, 'topic/delete_subtopic.html', context)

@login_required(login_url='login')
@user_passes_test(is_teacher, login_url='index')
def create_topic(request, slug):
    center = get_object_or_404(Center, slug=slug)
    
    if request.user.center is None or request.user.center != center:
        messages.error(request, "Xatolik: Markaz ma'lumoti topilmadi yoki ruxsat yo'q.")
        return redirect('index')
    
    if request.method == 'POST':
        form = TopicForm(request.POST)
        if form.is_valid():
            topic = form.save(commit=False)
            topic.teacher = request.user
            topic.center = center # 💡 Markazni saqlash
            topic.save()
            messages.success(request, "Mavzu muvaffaqiyatli yaratildi!")
            return redirect('my_questions', slug=center.slug) # 💡 Redirectda slug uzatildi
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
    else:
        form = TopicForm()
    
    context = {
        'form': form,
        'title': 'Yangi mavzu yaratish',
        'center': center,
        **get_base_context(request)
    }
    return render(request, 'topic/create_topic.html', context)

@login_required(login_url='login')
@user_passes_test(is_teacher, login_url='index')
def edit_topic(request, slug, topic_id): # 💡 slug qo'shildi
    center = get_object_or_404(Center, slug=slug)

    if request.user.center is None or request.user.center != center:
        messages.error(request, "Bu markazga kirish huquqingiz yo‘q yoki sizga markaz biriktirilmagan.")
        return redirect('index')
        
    # Markaz bo'yicha cheklash
    topic = get_object_or_404(Topic, id=topic_id, center=center, teacher=request.user) 
    
    if request.method == 'POST':
        form = TopicForm(request.POST, instance=topic)
        if form.is_valid():
            form.save()
            messages.success(request, "Mavzu muvaffaqiyatli tahrirlandi!")
            return redirect('my_questions', slug=center.slug) # 💡 Redirectda slug uzatildi
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
        'center': center,
        **get_base_context(request)
    }
    return render(request, 'topic/create_topic.html', context)

@login_required(login_url='login')
@user_passes_test(is_teacher, login_url='index')
def create_subtopic(request, slug, topic_id=None):
    center = get_object_or_404(Center, slug=slug)

    if request.user.center is None or request.user.center != center:
        messages.error(request, "Bu markazga kirish huquqingiz yo‘q yoki sizga markaz biriktirilmagan.")
        return redirect('index')

    initial = {}
    if topic_id:
        # Topicni markaz va ustoz bo'yicha cheklash
        topic = get_object_or_404(Topic, id=topic_id, center=center, teacher=request.user)
        initial['topic'] = topic
    
    if request.method == 'POST':
        form = SubtopicForm(request.POST)
        if form.is_valid():
            subtopic = form.save(commit=False)
            
            # Subtopic centerini qo'shish
            subtopic.center = center
            
            # Topic egasi va markazini tekshirish (Double Check)
            if subtopic.topic.teacher != request.user or subtopic.topic.center != center:
                 messages.error(request, "Noto'g'ri mavzu tanlandi yoki siz tanlagan mavzuga kirish ruxsatingiz yo'q.")
                 return redirect('my_questions', slug=center.slug)

            subtopic.save()
            messages.success(request, "Ichki mavzu muvaffaqiyatli yaratildi!")
            return redirect('topic_detail', slug=center.slug, topic_id=subtopic.topic.id)
        else:
             # Xato logikasi
             for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
    else:
        form = SubtopicForm(initial=initial)
        # Formdagi topic querysetini cheklash
        form.fields['topic'].queryset = Topic.objects.filter(center=center, teacher=request.user)
    
    context = {
        'form': form,
        'title': 'Yangi ichki mavzu yaratish',
        'center': center,
        'topic_id': topic_id,
        **get_base_context(request)
    }
    return render(request, 'topic/create_subtopic.html', context)


@login_required(login_url='login')
@user_passes_test(is_teacher, login_url='index')
def edit_subtopic(request, slug, subtopic_id):
    center = get_object_or_404(Center, slug=slug)

    if request.user.center is None or request.user.center != center:
        messages.error(request, "Bu markazga kirish huquqingiz yo‘q yoki sizga markaz biriktirilmagan.")
        return redirect('index')

    # Markaz va ustoz bo'yicha cheklash
    subtopic = get_object_or_404(Subtopic, id=subtopic_id, center=center, topic__teacher=request.user)
    
    if request.method == 'POST':
        form = SubtopicForm(request.POST, instance=subtopic)
        if form.is_valid():
            
            # Yangi tanlangan Topicning ustoz va markazini tekshirish
            new_topic = form.cleaned_data['topic']
            if new_topic.teacher != request.user or new_topic.center != center:
                 messages.error(request, "Siz faqat o'zingiz yaratgan mavzularga ichki mavzularni biriktirishingiz mumkin.")
                 return redirect('topic_detail', slug=center.slug, topic_id=subtopic.topic.id)
                 
            form.save()
            messages.success(request, "Ichki mavzu muvaffaqiyatli tahrirlandi!")
            return redirect('topic_detail', slug=center.slug, topic_id=subtopic.topic.id)
        else:
             # Xato logikasi
             for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
    else:
        form = SubtopicForm(instance=subtopic)
        # Formdagi topic querysetini cheklash
        form.fields['topic'].queryset = Topic.objects.filter(center=center, teacher=request.user)
    
    context = {
        'form': form,
        'title': 'Ichki mavzuni tahrirlash',
        'subtopic': subtopic,
        'center': center,
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
def list_flashcards(request, slug):
    """
    Berilgan slug'ga mos keluvchi Center'ga tegishli barcha flashcardlarni ko'rsatadi.
    """
    
    # 1. Center obyektini slug orqali topish (Topilmasa 404 xatosi beradi)
    # get_object_or_404 dan foydalanish tozaroq:
    center = get_object_or_404(Center, slug=slug)
    
    # 2. Flashcardlarni filtrlash (ASOSIY TUZATISH)
    # Flashcard modelida 'center' degan ForeignKey maydoni bor deb hisoblanadi.
    flashcards = Flashcard.objects.filter(
        center=center  # Faqat shu Center'ga tegishli flashcardlar
    ).order_by('-created_at')
    

    return render(request, 'flashcards/list_flashcards.html', {
        'flashcards': flashcards,
        'center': center,
    })

@login_required(login_url='login')
@user_passes_test(is_teacher, login_url='index')
def create_flashcard(request, slug): # <-- 'slug' argumenti mavjud
    """
    Berilgan center slug'iga flashcard yaratish.
    """
    # 1. Center obyektini topish
    center = get_object_or_404(Center, slug=slug)
    
    if request.method == 'POST':
        form = FlashcardForm(request.POST, request.FILES)
        if form.is_valid():
            flashcard = form.save(commit=False)
            flashcard.author = request.user
            flashcard.center = center
            flashcard.save()
            messages.success(request, f"Flashcard '{center.name}' markazi uchun muvaffaqiyatli yaratildi!")
            
            # ✅ MUHIM: Muvaffaqiyatli redirectda slug uzatilmoqda
            return redirect('list_flashcards', slug=slug) 
        
        # ⚠️ TUZATISH 1: Agar POST kelib, forma xato bo'lsa, render qilinadi.
        # Bu yerda redirect yo'q, shuning uchun xato kelmaydi, lekin mantiqni tekshiring.
        
    else:
        form = FlashcardForm()
    
    # ⚠️ TUZATISH 2 (Agar bu yerda redirect ishlatilgan bo'lsa, uni tuzating)
    # Agar biron sababga ko'ra bu yerda (else bloki tashqarisida) redirect ishlatilsa:
    # return redirect('list_flashcards', slug=slug)
    
    return render(request, 'flashcards/create_flashcard.html', {
        'form': form,
        'center': center,
    })

@login_required(login_url='login')
@user_passes_test(is_teacher, login_url='index')
def edit_flashcard(request, slug, pk):
    """
    Flashcardni tahrirlash (Slug va pk orqali).
    Qo'shimcha tekshiruv: flashcard haqiqatan ham shu centerga tegishlimi?
    """
    # 1. Center obyektini topish (Tekshirish uchun shart)
    center = get_object_or_404(Center, slug=slug)
    
    # 2. Flashcardni topish va uning shu centerga tegishli ekanligini tekshirish
    flashcard = get_object_or_404(Flashcard, pk=pk, center=center) # ASOSIY TEKSHIRUV

    if request.method == 'POST':
        form = FlashcardForm(request.POST, request.FILES, instance=flashcard)
        if form.is_valid():
            form.save()
            messages.success(request, "Flashcard muvaffaqiyatli tahrirlandi!")
            return redirect('list_flashcards', slug=slug)
    else:
        form = FlashcardForm(instance=flashcard)
        
    return render(request, 'flashcards/edit_flashcard.html', {
        'form': form,
        'flashcard': flashcard,
        'center': center,
    })

@login_required(login_url='login')
@user_passes_test(is_teacher, login_url='index')
def delete_flashcard(request, slug, pk):
    """
    Flashcardni o'chirish (Slug va pk orqali).
    Qo'shimcha tekshiruv: flashcard haqiqatan ham shu centerga tegishlimi?
    """
    # 1. Center obyektini topish (Tekshirish uchun shart)
    center = get_object_or_404(Center, slug=slug)
    
    # 2. Flashcardni topish va uning shu centerga tegishli ekanligini tekshirish
    flashcard = get_object_or_404(Flashcard, pk=pk, center=center) # ASOSIY TEKSHIRUV
    
    if request.method == 'POST':
        flashcard.delete()
        messages.success(request, "Flashcard muvaffaqiyatli o'chirildi.")
        return redirect('list_flashcards', slug=slug)
    
    # POST so'rovini kutish xavfsizroq bo'lgani uchun, agar GET kelsa, odatda List sahifasiga qaytariladi.
    messages.error(request, "Xatolik: O'chirish uchun POST so'rovi talab qilinadi.")
    return redirect('list_flashcards', slug=slug)


@login_required(login_url='login')
@user_passes_test(is_teacher, login_url='index')
def add_question(request, slug=None):
    """
    Yangi savol qo'shish. QuestionForm va AnswerOptionFormSet bilan ishlaydi.
    QuestionForm.clean() da tozalangan ma'lumotlar saqlashda qayta tozalanmaydi.
    """
    
    # 0. Center va ruxsat tekshiruvi (O'zgarmadi)
    if not is_teacher(request.user):
        messages.error(request, _("Faqat o'qituvchilar savol qo'shishi mumkin!"))
        return redirect('index')

    center = None
    if slug:
        center = get_object_or_404(Center, slug=slug)
        if request.user.role == 'center_admin' and request.user.center != center:
            raise PermissionDenied(_("Bu markazga kirish huquqingiz yo‘q"))
    else:
        center = request.user.center
        if not center:
            messages.error(request, _("Siz hech qanday markazga ulanmagansiz!"))
            return redirect('index')

    ANSWER_OPTIONS_PREFIX = 'answer_option'
    
    # POST So'rovi
    if request.method == 'POST':
        # user=request.user ni uzatish zarur
        form = QuestionForm(request.POST, request.FILES, user=request.user) 
        answer_option_formset = None 

        # 1. QuestionForm ni tekshirish
        if form.is_valid():
            
            # 2. Question obyektini xotirada yaratish (Formsetga instance uzatish uchun)
            question_instance = form.save(commit=False)
            question_instance.center = center # markazni o'rnatish
            question_instance.author = request.user
            
            # 3. Formsetni instance bilan yaratish
            answer_option_formset = AnswerOptionFormSet(
                request.POST,
                request.FILES,
                prefix=ANSWER_OPTIONS_PREFIX,
                instance=question_instance # 🛑 Instance bog'landi
            )
            
            # 4. Formsetni validatsiya qilish
            if answer_option_formset.is_valid():
                try:
                    with transaction.atomic():
                        # 4.1. Question ni DB ga saqlash
                        question_instance.save() 
                        form.save_m2m() # ManyToMany bog'lanishlarni saqlash
                        
                        cleaned_data = form.cleaned_data # Barcha tozalangan ma'lumotlarni olish
                        answer_format = cleaned_data['answer_format']

                        # 4.2. QuestionSolution ni saqlash (ASOSIY TUZATISH - qayta tozalash yo'q)
                        hint = cleaned_data.get('hint', '').strip()
                        detailed_solution = cleaned_data.get('detailed_solution', '').strip()
                        
                        # Faqat matn mavjud bo'lsa, saqlaymiz. Matn QuestionForm.clean() da tozalangan.
                        if hint or detailed_solution:
                            QuestionSolution.objects.update_or_create(
                                question=question_instance,
                                defaults={
                                    'hint': hint, # ✅ QuestionForm.clean() dan kelgan tozalangan matn
                                    'detailed_solution': detailed_solution # ✅ QuestionForm.clean() dan kelgan tozalangan matn
                                }
                            )
                        # Agar avval yechim bo'lib, endi o'chirilsa, yechim obyektini ham o'chirish kerak bo'lishi mumkin
                        elif hasattr(question_instance, 'solution'):
                            question_instance.solution.delete()


                        # 4.3. Javob formatiga qarab mantiq (O'zgarishsiz qoldi, chunki short_answer allaqachon tozalangan)
                        if answer_format in ['single', 'multiple']:
                            answer_option_formset.save() 
                            # Agar oldindan short_answer qiymati mavjud bo'lsa, uni o'chirish
                            if question_instance.correct_short_answer:
                                question_instance.correct_short_answer = None
                                question_instance.save(update_fields=['correct_short_answer'])
                                
                        elif answer_format == 'short_answer':
                            # correct_short_answer QuestionForm.clean() da allaqachon tozalangan/formatlangan
                            correct_short_answer = cleaned_data.get('correct_short_answer', '').strip()
                            question_instance.correct_short_answer = correct_short_answer
                            question_instance.save(update_fields=['correct_short_answer'])
                            # Variantlarni o'chirish
                            question_instance.options.all().delete()
                            
                        # Bu else holati odatda bo'lmasligi kerak
                        else:
                            question_instance.options.all().delete()
                            question_instance.correct_short_answer = None
                            question_instance.save(update_fields=['correct_short_answer'])


                        messages.success(request, _(f"Savol ID {question_instance.id} muvaffaqiyatli qo'shildi!"))
                        logger.info(f"Savol ID {question_instance.id} muvaffaqiyatli saqlandi. Format: {answer_format}")

                        # 4.4. MUVAFFDAQIYATLI SAQLASHDAN KEYIN YO'NALTIRISH
                        return redirect('subtopic_questions', slug=center.slug, subtopic_id=question_instance.subtopic.id)

                except Exception as e:
                    messages.error(request, _(f"Saqlashda kutilmagan xatolik yuz berdi: {str(e)}"))
                    logger.error(f"Savolni saqlash xatosi (Exception): {e}. Form errors: {form.errors}, Formset errors: {answer_option_formset.errors if answer_option_formset else 'Not created'}")
            
            # Formset validatsiyadan o'tmasa
            else:
                logger.error(f"AnswerOptionFormSet XATOLARI: {answer_option_formset.errors}")
                messages.error(request, _("Javob variantlarini saqlashda xatolik yuz berdi. Iltimos, tekshiring."))

        # QuestionForm validatsiyadan o'tmasa
        else:
            # AnswerOptionFormSet ni POST ma'lumotlari bilan yaratish (xatolarni ko'rsatish uchun)
            # Lekin instance bo'lmagani uchun FormSet.clean() ishlamaydi, bu OK.
            answer_option_formset = AnswerOptionFormSet(request.POST, request.FILES, prefix=ANSWER_OPTIONS_PREFIX)
            logger.error("FORM VALIDATSIYADAN O'TMADI (add_question).")
            logger.error(f"QuestionForm XATOLARI: {form.errors.as_json()}")
            messages.error(request, _("Savolni saqlashda xatolik yuz berdi. Iltimos, formadagi xabarlarni tekshiring."))
        
        # Xatolar bo'lsa, shablonni qayta ko'rsatish
        irt_fields = [
            form['difficulty'], form['discrimination'], form['guessing'],
            form['difficulty_level'], form['status']
        ]
        return render(request, 'questions/add_questions.html', {
            'form': form,
            'answer_option_formset': answer_option_formset,
            'irt_fields': irt_fields,
            'center': center,
            **get_base_context(request)
        })

    # GET So'rovi (o'zgarmadi)
    else: 
        # 6. GET so'rovi uchun formani va bo'sh formsetni yaratish
        initial_data = {'center': center}
        subtopic_id = request.GET.get('subtopic')
        if subtopic_id:
            try:
                # Subtopic mavjudligini tekshirish
                Subtopic.objects.get(pk=subtopic_id, center=center)
                initial_data['subtopic'] = subtopic_id
            except (Subtopic.DoesNotExist, ValueError):
                logger.warning(f"URLda noto'g'ri Subtopic ID kiritildi: {subtopic_id}")

        form = QuestionForm(initial=initial_data, user=request.user)
        # GET uchun bo'sh (yangi) formset
        answer_option_formset = AnswerOptionFormSet(
            prefix=ANSWER_OPTIONS_PREFIX,
            queryset=AnswerOption.objects.none()
        )
        irt_fields = [
            form['difficulty'],
            form['discrimination'],
            form['guessing'],
            form['difficulty_level'],
            form['status']
        ]
        return render(request, 'questions/add_questions.html', {
            'form': form,
            'answer_option_formset': answer_option_formset,
            'irt_fields': irt_fields,
            'center': center,
            **get_base_context(request)
        })
    
@login_required(login_url='login')
@user_passes_test(is_teacher, login_url='index')
def edit_question(request, slug, question_id):
    """
    Mavjud savolni tahrirlash. QuestionForm va AnswerOptionFormSet bilan ishlaydi.
    """
    
    # 0. Center va Question obyektini olish
    center = get_object_or_404(Center, slug=slug)
    question_instance = get_object_or_404(Question, id=question_id, center=center)

    if not is_teacher(request.user):
        messages.error(request, _("Faqat o'qituvchilar savolni tahrirlashi mumkin!"))
        return redirect('index')

    if request.user.role == 'center_admin' and request.user.center != center:
        raise PermissionDenied(_("Bu markazga kirish huquqingiz yo‘q"))

    ANSWER_OPTIONS_PREFIX = 'answer_option'

    # Savol yechimini yuklab olish
    solution_instance = None
    if hasattr(question_instance, 'solution'):
        solution_instance = question_instance.solution

    # POST So'rovi
    if request.method == 'POST':
        # Savol formasini mavjud ma'lumot (instance) va POST ma'lumotlari bilan yaratish
        form = QuestionForm(
            request.POST, 
            request.FILES, 
            user=request.user, 
            instance=question_instance,
            initial={'hint': solution_instance.hint if solution_instance else '', 
                     'detailed_solution': solution_instance.detailed_solution if solution_instance else ''}
        ) 
        
        # Formsetni mavjud ma'lumot (instance) va POST ma'lumotlari bilan yaratish
        answer_option_formset = AnswerOptionFormSet(
            request.POST,
            request.FILES,
            prefix=ANSWER_OPTIONS_PREFIX,
            instance=question_instance # 🛑 Instance bog'landi
        )

        # 1. QuestionForm ni tekshirish
        if form.is_valid():
            # 2. Question obyektini xotirada saqlash (commit=False)
            question_instance = form.save(commit=False)
            question_instance.center = center # markazni qayta o'rnatish
            question_instance.author = request.user # avtorni qayta o'rnatish
            
            # 3. Formsetni validatsiya qilish
            if answer_option_formset.is_valid():
                try:
                    with transaction.atomic():
                        # 4.1. Question ni DB ga saqlash
                        question_instance.save() 
                        form.save_m2m() # ManyToMany bog'lanishlarni saqlash
                        
                        cleaned_data = form.cleaned_data 
                        answer_format = cleaned_data['answer_format']

                        # 4.2. QuestionSolution ni saqlash/o'chirish
                        hint = cleaned_data.get('hint', '').strip()
                        detailed_solution = cleaned_data.get('detailed_solution', '').strip()
                        
                        if hint or detailed_solution:
                            QuestionSolution.objects.update_or_create(
                                question=question_instance,
                                defaults={
                                    'hint': hint,
                                    'detailed_solution': detailed_solution,
                                    'is_free': cleaned_data.get('is_solution_free', False) # is_free maydoni ham saqlanishi kerak
                                }
                            )
                        elif hasattr(question_instance, 'solution'):
                            question_instance.solution.delete()

                        # 4.3. Javob formatiga qarab mantiq
                        if answer_format in ['single', 'multiple']:
                            answer_option_formset.save() 
                            # Agar oldindan short_answer qiymati mavjud bo'lsa, uni o'chirish
                            if question_instance.correct_short_answer:
                                question_instance.correct_short_answer = None
                                question_instance.save(update_fields=['correct_short_answer'])
                                
                        elif answer_format == 'short_answer':
                            correct_short_answer = cleaned_data.get('correct_short_answer', '').strip()
                            question_instance.correct_short_answer = correct_short_answer
                            question_instance.save(update_fields=['correct_short_answer'])
                            # Variantlarni o'chirish
                            question_instance.options.all().delete()
                            
                        # Bu else holati odatda bo'lmasligi kerak
                        else:
                            question_instance.options.all().delete()
                            question_instance.correct_short_answer = None
                            question_instance.save(update_fields=['correct_short_answer'])


                        messages.success(request, _(f"Savol ID {question_instance.id} muvaffaqiyatli tahrirlandi!"))
                        logger.info(f"Savol ID {question_instance.id} muvaffaqiyatli tahrirlandi. Format: {answer_format}")

                        # 4.4. MUVAFFDAQIYATLI SAQLASHDAN KEYIN YO'NALTIRISH
                        return redirect('subtopic_questions', slug=center.slug, subtopic_id=question_instance.subtopic.id)

                except Exception as e:
                    messages.error(request, _(f"Saqlashda kutilmagan xatolik yuz berdi: {str(e)}"))
                    logger.error(f"Savolni saqlash xatosi (Exception): {e}. Form errors: {form.errors}, Formset errors: {answer_option_formset.errors if answer_option_formset else 'Not created'}")
            
            # Formset validatsiyadan o'tmasa
            else:
                logger.error(f"AnswerOptionFormSet XATOLARI: {answer_option_formset.errors}")
                messages.error(request, _("Javob variantlarini saqlashda xatolik yuz berdi. Iltimos, tekshiring."))

        # QuestionForm validatsiyadan o'tmasa
        else:
            # AnswerOptionFormSet ni POST ma'lumotlari bilan yaratish (xatolarni ko'rsatish uchun)
            answer_option_formset = AnswerOptionFormSet(
                request.POST, 
                request.FILES, 
                prefix=ANSWER_OPTIONS_PREFIX, 
                instance=question_instance
            )
            logger.error("FORM VALIDATSIYADAN O'TMADI (edit_question).")
            logger.error(f"QuestionForm XATOLARI: {form.errors.as_json()}")
            messages.error(request, _("Savolni saqlashda xatolik yuz berdi. Iltimos, formadagi xabarlarni tekshiring."))
    
    # GET So'rovi (Sahifani birinchi marta yuklash)
    else:
        # QuestionForm ni mavjud ma'lumot (instance) bilan yaratish
        form = QuestionForm(
            user=request.user, 
            instance=question_instance,
            initial={'hint': solution_instance.hint if solution_instance else '', 
                     'detailed_solution': solution_instance.detailed_solution if solution_instance else ''}
        )
        
        # Formsetni mavjud ma'lumot (instance) bilan yaratish
        answer_option_formset = AnswerOptionFormSet(
            instance=question_instance, 
            prefix=ANSWER_OPTIONS_PREFIX,
            queryset=question_instance.options.all().order_by('id') # Variantlarni ID bo'yicha tartiblab olish
        )

    # Shablonni render qilish
    irt_fields = [
        form['difficulty'], form['discrimination'], form['guessing'],
        form['difficulty_level'], form['status']
    ]
    
    # 💡 Formsetda yetishmayotgan minimal variantlarni qo'shish mantiqi (Agar MAX_NUM=5 bo'lsa)
    # Ushbu qismni AnswerOptionFormSet ichida bajarish maqsadga muvofiq,
    # lekin bu yerda shablonni to'g'ri ko'rsatish uchun uni o'zgartirmaymiz.

    return render(request, 'questions/edit_question.html', {
        'form': form,
        'answer_option_formset': answer_option_formset,
        'irt_fields': irt_fields,
        'center': center,
        'question': question_instance, # Shablon sarlavhasi uchun kerak
    })

def delete_images_from_html(html_content):
    """ HTML matnidagi img teglarini topadi va default storage'dan fayllarni o'chiradi. """
    if not html_content:
        return
        
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        images = soup.find_all('img')
        for img in images:
            src = img.get('src')
            if src and src.startswith(default_storage.base_url):
                # /media/uploads/... kabi manzilni topamiz
                file_path = src.replace(default_storage.base_url, '', 1) 
                
                # Agar saqlash joyi mahalliy (local storage) bo'lsa, o'chiramiz
                if default_storage.exists(file_path):
                    default_storage.delete(file_path)
                    logger.info(f"O'chirilgan fayl: {file_path}")

    except Exception as e:
        logger.error(f"HTMLdagi rasmlarni o'chirishda xatolik: {e}")

@login_required(login_url='login')
def delete_question(request, slug, question_id):
    """ Savolni o'chirish uchun tasdiqlash sahifasini ko'rsatadi va o'chiradi. """
    
    # 1. Center va Ruxsat tekshiruvi
    center = get_object_or_404(Center, slug=slug)
    user = request.user
    
    # Ruxsat tekshiruvi: Faqat shu markazning 'teacher' yoki 'center_admin'i bo'lishi kerak.
    # Muallif tekshiruvi keyinroq qo'shildi. Agar admin bo'lsa, muallif bo'lish shart emas.
    if user.center != center or user.role not in ['teacher', 'center_admin']:
        messages.error(request, _("Bu markazdagi savollarni o'chirish huquqingiz yo‘q."))
        return redirect('index')
    
    # Savolni yuklash:
    # Admin o'z markazidagi istalgan savolni o'chira oladi.
    # Teacher faqat o'zining savollarini o'chira oladi.
    if user.role == 'teacher':
        question_query = Question.objects.filter(id=question_id, center=center, author=user)
    else: # center_admin
        question_query = Question.objects.filter(id=question_id, center=center)
        
    question = get_object_or_404(question_query)
    
    # Qayerga qaytishni aniqlash
    redirect_url = redirect('subtopic_questions', slug=center.slug, subtopic_id=question.subtopic.id) if question.subtopic else redirect('my_questions', slug=center.slug)

    # POST so'rovi: Savolni o'chirish
    if request.method == 'POST':
        try:
            # Savol matnidagi, variantlaridagi va yechimlaridagi rasmlarni o'chirish
            
            # 1. Savol matni
            delete_images_from_html(question.text)
            
            # 2. Javob variantlari matni
            for option in question.options.all():
                delete_images_from_html(option.text)
                
            # 3. Yechim (Hint/Detailed Solution)
            if hasattr(question, 'solution'):
                delete_images_from_html(question.solution.hint)
                delete_images_from_html(question.solution.detailed_solution)

            # 4. Savolni o'chirish
            # Agar Question modelida on_delete=CASCADE bo'lsa, bog'liq AnswerOption va QuestionSolution 
            # avtomatik o'chadi.
            question.delete()
            
            messages.success(request, _("Savol muvaffaqiyatli o'chirildi!"))
            return redirect_url
            
        except Exception as e:
            logger.error(f"Savolni o'chirishda xatolik (ID: {question_id}): {e}")
            messages.error(request, _(f"Savolni o'chirishda kutilmagan xatolik yuz berdi: {str(e)}"))
            return redirect_url
    
    # GET so'rovi: Tasdiqlash sahifasini ko'rsatish
    return render(request, 'questions/delete_question_confirm.html', {
        'question': question,
        'center': center,
        'redirect_url': redirect_url.url, # orqaga qaytish uchun URL
    })

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
@csrf_exempt # 🛑 MUHIM: CKEditor yuklash mexanizmi uchun ko'pincha kerak bo'ladi
def ckeditor_upload_image(request):
    """
    CKEditor rasm yuklash talablariga mos View funksiyasi.
    U 'upload' nomli POST faylini kutadi va URL ni qaytaradi.
    """
    if request.method == 'POST' and request.FILES.get('upload'):
        file_obj = request.FILES['upload']
        
        # Fayl nomini o'zgartirish (to'qnashuvni oldini olish uchun)
        import os
        ext = os.path.splitext(file_obj.name)[1]
        file_name = default_storage.get_available_name(f'questions/ckeditor/{file_obj.name}')
        
        # Faylni saqlash
        saved_file_name = default_storage.save(file_name, file_obj)
        file_url = default_storage.url(saved_file_name)
        
        # CKEditor 4 (ko'p ishlatiladigan) talab qiladigan format:
        # success: {"uploaded": true, "url": "/media/questions/ckeditor/my_image.png"}
        return JsonResponse({
            'uploaded': 1, # CKEditor 4 uchun success holati
            'fileName': os.path.basename(saved_file_name),
            'url': file_url
        })
    
    # Yuklash xatosi yoki noto'g'ri so'rov
    return JsonResponse({'uploaded': 0, 'error': {'message': 'Rasm yuklashda xatolik yuz berdi.'}}, status=400)


@login_required(login_url='login')
@user_passes_test(is_teacher, login_url='index')
def passage_list(request, slug): # Center slug = 'slug'
    """Berilgan Center slug'ga tegishli BARCHA 'Passage'larni ko'rsatadi (Author filtrisiz)."""
    
    center = get_object_or_404(Center, slug=slug)
    
    # Faqat Center bo'yicha filtrlash.
    passages = Passage.objects.filter(
        center=center 
    ).order_by('-created_at')
    
    return render(request, 'passage/passage_list.html', {
        'passages': passages,
        'center': center,
    })

# ==============================================================================
# 2. ADD PASSAGE (Yaratish: Center slug = 'slug')
# ==============================================================================

@login_required(login_url='login')
@user_passes_test(is_teacher, login_url='index')
def add_passage(request, slug): # Center slug = 'slug'
    """Yangi 'passage'ni ma'lum bir markazga yaratish uchun funksiya."""
    
    center = get_object_or_404(Center, slug=slug)
    
    if request.method == 'POST':
        form = PassageForm(request.POST)
        if form.is_valid():
            passage = form.save(commit=False)
            passage.author = request.user # Yozuvchi saqlanadi
            passage.center = center 
            passage.save()
            messages.success(request, f"Yangi matn ({center.name} uchun) muvaffaqiyatli qo'shildi!")
            
            return redirect('passage_list', slug=center.slug) 
    else:
        form = PassageForm()
        
    return render(request, 'passage/add_passage.html', {'form': form, 'center': center})

# ==============================================================================
# 3. EDIT PASSAGE (Tahrirlash: Center slug = 'slug', Passage PK = 'pk')
# ==============================================================================

@login_required(login_url='login')
@user_passes_test(is_teacher, login_url='index')
# ✅ Argument 'p_slug' o'rniga 'pk' ishlatiladi
def edit_passage(request, slug, pk): 
    """Mavjud 'passage'ni Center slug va Passage PK orqali tahrirlash uchun funksiya."""
    
    # ✅ PK orqali topish (slug o'rniga)
    passage = get_object_or_404(
        Passage, 
        pk=pk,          
        center__slug=slug
    )
    center = passage.center 
    
    if request.method == 'POST':
        form = PassageForm(request.POST, instance=passage)
        if form.is_valid():
            form.save()
            messages.success(request, f"Matn '{passage.title[:20]}...' muvaffaqiyatli tahrirlandi!")
            
            return redirect('passage_list', slug=center.slug) 
    else:
        form = PassageForm(instance=passage)
        
    return render(request, 'passage/edit_passage.html', {'form': form, 'passage': passage, 'center': center})

# ==============================================================================
# 4. DELETE PASSAGE (O'chirish: Center slug = 'slug', Passage PK = 'pk')
# ==============================================================================

@login_required(login_url='login')
@user_passes_test(is_teacher, login_url='index')
# ✅ Argument 'p_slug' o'rniga 'pk' ishlatiladi
def delete_passage(request, slug, pk): 
    """'Passage'ni Center slug va Passage PK orqali o'chirish uchun funksiya."""
    
    # ✅ PK orqali topish (slug o'rniga)
    passage = get_object_or_404(
        Passage, 
        pk=pk, 
        center__slug=slug
    )
    center = passage.center
    
    if request.method == 'POST':
        passage.delete()
        messages.success(request, "Matn muvaffaqiyatli o'chirildi.")
        
        return redirect('passage_list', slug=center.slug) 
        
    return render(request, 'passage/delete_passage.html', {'passage': passage, 'center': center})



@login_required(login_url='login')
def process_purchase_view(request, slug, purchase_type, item_id):
    """
    Yangi xarid obyekti yaratadi va skrinshot yuklash sahifasiga yo‘naltiradi.
    Faqat o‘z markazidagi tariflar.
    """
    center = get_object_or_404(Center, slug=slug)
    if request.user.center != center:
        messages.error(request, "Ruxsat yo‘q.")
        return redirect('dashboard',slug=request.user.center.slug)

    user = request.user
    item = None

    if purchase_type == 'subscription':
        item = get_object_or_404(SubscriptionPlan, id=item_id, is_active=True)
    elif purchase_type == 'package':
        item = get_object_or_404(ExamPackage, id=item_id, is_active=True)
    else:
        messages.error(request, "Noto‘g‘ri xarid turi.")
        return redirect('price', slug=slug)

    # Xarid yaratish
    purchase = Purchase.objects.create(
        user=user,
        purchase_type=purchase_type,
        package=item if purchase_type == 'package' else None,
        subscription_plan=item if purchase_type == 'subscription' else None,
        amount=item.price,
        final_amount=item.price,
        status='pending'
    )

    messages.info(request, f"'{item.name}' uchun to‘lov kutilmoqda. Skrinshotni yuklang.")

    return redirect('upload_screenshot', slug=slug, purchase_id=purchase.id)

@login_required(login_url='login')
def upload_screenshot_view(request, slug, purchase_id):
    """
    Skrinshot yuklash – faqat o‘z xaridi uchun.
    """
    center = get_object_or_404(Center, slug=slug)
    if request.user.center != center:
        messages.error(request, "Ruxsat yo‘q.")
        return redirect('dashboard',slug=request.user.center.slug)

    purchase = get_object_or_404(
        Purchase, 
        id=purchase_id, 
        user=request.user,
        status='pending'  # faqat pending bo‘lsa
    )

    if request.method == 'POST':
        form = ScreenshotUploadForm(request.POST, request.FILES, instance=purchase)
        if form.is_valid():
            purchase = form.save(commit=False)
            purchase.status = 'moderation'
            purchase.save()
            messages.success(request, "Skrinshot qabul qilindi. Tez orada tasdiqlanadi!")
            return redirect('dashboard',slug=request.user.center.slug)
        else:
            messages.error(request, "Formada xatolik. Iltimos, tekshiring.")
    else:
        form = ScreenshotUploadForm(instance=purchase)

    site_settings = SiteSettings.objects.first()

    context = {
        'center': center,
        'form': form,
        'purchase': purchase,
        'item': purchase.subscription_plan or purchase.package,
        'site_settings': site_settings,
    }
    return render(request, 'student/upload_screenshot.html', context)

def get_section_questions(section, exam):
    """
    Bo‘lim uchun statik savollarni qaytaradi.
    Faqat o‘z markazidagi savollar.
    """
    if exam.center != section.exam.center:
        return []  # Xavfsizlik

    static_questions = section.static_questions.filter(
        question__exam__center=exam.center
    ).select_related('question')
    
    return [sq.question for sq in static_questions]

# ======================================================================
# 1. EXAM BOSHQARUVI
# ======================================================================

@login_required(login_url='login')
@user_passes_test(is_teacher, login_url='index')
def exam_list(request, slug): # 🎯 SLUG QO'SHILDI
    """
    Imtihonlar ro'yxatini ko'rish (Faqat user.center ichida).
    """
    center = get_object_or_404(Center, slug=slug)
    
    # Xavfsizlik: Foydalanuvchi markazga tegishli ekanligini tekshirish
    if request.user.center != center:
         messages.error(request, "Siz bu markaz imtihonlarini ko'rish huquqiga ega emassiz.")
         return redirect('dashboard',slug=request.user.center.slug)
    
    # 1. Prefetch obyekti: ExamSectionOrder orqali Section savollar sonini olish 
    prefetch_exam_sections = Prefetch(
        'examsectionorder',
        # ExamSectionOrder.exam_section.static_questions.count() N+1 muammosini keltirmaslik uchun
        # HTML da to'g'ridan-to'g'ri .exam_section.static_questions.count ni ishlatamiz.
        # Bu yerda faqat bog'lanishlarni optimallashtiramiz.
        queryset=ExamSectionOrder.objects.select_related('exam_section').order_by('order'),
        to_attr='ordered_sections'
    )

    # 2. Asosiy Exam so'rovi (Faqat shu markaz o'qituvchilari tomonidan yaratilgan imtihonlar)
    exams = Exam.objects.filter(
        teacher__center=center # 🎯 Filtrni o'zgartirdik: teacher=request.user O'RNIGA teacher__center=center
    ).annotate(
        section_count=Count('examsectionorder') 
    ).prefetch_related(
        prefetch_exam_sections,
        'teacher' # Teacher ma'lumotlarini yuklaymiz
    ).order_by('-created_at')
    
    context = {
        'exams': exams,
        'center': center, # Shablon uchun center obyekti
    }
    return render(request, 'management/exam_list.html', context)

@login_required(login_url='login')
@user_passes_test(is_teacher, login_url='index')
def exam_create(request, slug):
    """Yangi imtihon yaratish (Faqat user.center ichida)."""
    center = get_object_or_404(Center, slug=slug)
    if request.user.center != center:
         messages.error(request, "Boshqa markazda imtihon yaratishga ruxsat yo'q.")
         return redirect('dashboard',slug=request.user.center.slug)
         
    # Sectionlarni filtratsiya qilish: Faqat shu markazdagi o'qituvchilar yaratgan sectionlar
    available_sections = ExamSection.objects.filter(
        created_by__center=center 
    ).annotate(
        question_count=Count('static_questions')
    ).order_by('name') 
    
    selected_sections_ids = []
    
    if request.method == 'POST':
        form = ExamForm(request.POST)
        selected_sections_ids_str = request.POST.getlist('sections_select2') 
        
        try:
            selected_sections_ids = [int(id_str) for id_str in selected_sections_ids_str if id_str.isdigit()]
        except:
            messages.error(request, "Bo'lim ID'lari noto'g'ri formatda. Iltimos, faqat ro'yxatdan tanlang.")
            selected_sections_ids = []

        form_is_valid = form.is_valid()
        
        if not selected_sections_ids:
            messages.error(request, "Iltimos, kamida bitta bo'limni tanlang.")
            form_is_valid = False
        
        if form_is_valid and selected_sections_ids:
            try:
                with transaction.atomic():
                    exam = form.save(commit=False)
                    exam.teacher = request.user
                    exam.center = center # Markazni imtihonga biriktirish 
                    exam.save()
                    
                    selected_sections_map = {
                        section.id: section for section in ExamSection.objects.filter(
                            id__in=selected_sections_ids, 
                            created_by__center=center, # Yaratishda ham filtr
                        )
                    }

                    exam_section_orders = []
                    for index, section_id in enumerate(selected_sections_ids):
                        section = selected_sections_map.get(section_id)
                        if not section: continue 
                        exam_section_orders.append(
                            ExamSectionOrder(exam=exam, exam_section=section, order=index + 1)
                        )
                    
                    if exam_section_orders:
                        ExamSectionOrder.objects.bulk_create(exam_section_orders)
                        
                        # ==================================================
                        # ✅ FLASHCARD YARATISH MANTIG'INI TUZATISH
                        # ==================================================

                        # 1. Tanlangan ExamSectionlarga tegishli barcha Question ID'larini olish
                        question_ids = ExamSectionStaticQuestion.objects.filter(
                            exam_section__id__in=selected_sections_ids
                        ).values_list('question_id', flat=True).distinct()

                        # 2. Yuqoridagi Question ID'lariga bog'langan barcha Flashcard ID'larini olish
                        # (Flashcard modelidagi ManyToManyField nomi 'questions' deb faraz qilinadi)
                        flashcard_ids = Flashcard.objects.filter(
                            questions__id__in=question_ids
                        ).values_list('id', flat=True).distinct()

                        if flashcard_ids.exists():
                            # 3. FlashcardExam obyektini yaratish
                            flashcard_exam = FlashcardExam.objects.create(
                                source_exam=exam, 
                                title=f"{exam.title} bo'yicha Flashcard to'plami"
                            )
                            
                            # 4. Flashcardlarni biriktirish (MUHIM QISM: flashcards.set() orqali)
                            flashcard_exam.flashcards.set(flashcard_ids) 
                            
                            messages.info(request, f"Flashcard to'plami avtomatik yaratildi va {flashcard_ids.count()} ta kartochka biriktirildi.")
                        
                        # ==================================================
                        # ✅ TUZATISH YAKUNI
                        # ==================================================
                            
                        messages.success(request, f"Imtihon '{exam.title}' muvaffaqiyatli yaratildi va {len(exam_section_orders)} ta bo'lim biriktirildi!")
                        return redirect('exam_list', slug=center.slug) # SLUG Bilan REDIRECT
                    else:
                        messages.error(request, "Tanlangan bo'limlar ro'yxatida xato. Iltimos, boshqadan harakat qiling.")
                        raise Exception("Bo'limlar ro'yxati yaratilmadi.")
                
            except Exception as e:
                messages.error(request, f"Xato: Imtihonni yaratishda muammo yuz berdi. ({e})")
        
        selected_sections_ids = selected_sections_ids 

    else:
        form = ExamForm()
        selected_sections_ids = []

    context = {
        'form': form,
        'sections': available_sections,
        'selected_sections_ids': selected_sections_ids,
        'center': center, # Shablon uchun center obyekti
    }
    return render(request, 'management/exam_create.html', context)

@login_required(login_url='login')
@user_passes_test(is_teacher, login_url='index')
def exam_edit(request, slug, pk): # 🎯 SLUG QO'SHILDI
    """Imtihonni tahrirlash (Faqat user.center ichida)."""
    center = get_object_or_404(Center, slug=slug)
    if request.user.center != center:
         messages.error(request, "Boshqa markaz imtihonini tahrirlashga ruxsat yo'q.")
         return redirect('dashboard',slug=request.user.center.slug)
         
    # Examni o'zgartirdik: Faqat shu markazdagi o'qituvchilarning examlari
    exam = get_object_or_404(Exam, id=pk, teacher__center=center)
    
    # 🎯 Sectionlarni filtratsiya qilish: Faqat shu markazdagi o'qituvchilar yaratgan sectionlar
    available_sections = ExamSection.objects.filter(
        created_by__center=center 
    ).annotate(
        question_count=Count('static_questions') 
    ).order_by('name') 
    
    # ... Qolgan kod o'zgarishsiz, faqat REDIRECT ga slug qo'shiladi
    current_section_ids = list(
        ExamSectionOrder.objects.filter(exam=exam).order_by('order').values_list('exam_section_id', flat=True)
    )

    if request.method == 'POST':
        form = ExamForm(request.POST, instance=exam)
        selected_sections_ids_str = request.POST.getlist('sections_select2') 
        
        selected_sections_ids = []
        try:
            selected_sections_ids = [int(id_str) for id_str in selected_sections_ids_str if id_str.isdigit()]
        except:
            pass

        form_is_valid = form.is_valid()
        
        if not selected_sections_ids:
            messages.error(request, "Iltimos, kamida bitta bo'limni tanlang.")
            form_is_valid = False
        
        if form_is_valid and selected_sections_ids:
            try:
                with transaction.atomic():
                    exam = form.save()
                    
                    ExamSectionOrder.objects.filter(exam=exam).delete()
                    selected_sections_map = {
                        section.id: section for section in ExamSection.objects.filter(
                            id__in=selected_sections_ids, created_by__center=center
                        )
                    }

                    exam_section_orders = []
                    for index, section_id in enumerate(selected_sections_ids):
                        section = selected_sections_map.get(section_id)
                        if not section: continue
                        exam_section_orders.append(
                            ExamSectionOrder(exam=exam, exam_section=section, order=index + 1)
                        )
                    
                    if exam_section_orders:
                        ExamSectionOrder.objects.bulk_create(exam_section_orders)
                        
                        has_flashcards_in_sections = Question.objects.filter(
                            examsectionstaticquestion__exam_section__id__in=selected_sections_ids,
                            flashcards__isnull=False 
                        ).exists()

                        if has_flashcards_in_sections:
                            FlashcardExam.objects.get_or_create(
                                source_exam=exam,
                                defaults={'title': f"{exam.title} bo'yicha Flashcard to'plami"}
                            )
                            messages.info(request, "Flashcard to'plami yangilandi.")
                        else:
                            if hasattr(exam, 'flashcard_exam'):
                                exam.flashcard_exam.delete()
                                messages.info(request, "Flashcard to'plami so'zlar qolmagani uchun o'chirildi.")

                        messages.success(request, f"Imtihon '{exam.title}' muvaffaqiyatli tahrirlandi va {len(exam_section_orders)} ta bo'lim biriktirildi!")
                        return redirect('exam_list', slug=center.slug) # 🎯 SLUG Bilan REDIRECT
                    else:
                        messages.error(request, "Bo'limlar ro'yxati yaratilmadi. Iltimos, faqat o'zingiz yaratgan bo'limlarni tanlang.")
                        current_section_ids = selected_sections_ids
                        raise Exception("Bo'limlar to'liq yaratilmadi.")

            except Exception as e:
                error_message = f"Xato: Imtihonni tahrirlashda muammo yuz berdi. ({e})"
                messages.error(request, error_message)
                current_section_ids = selected_sections_ids 
        else:
            current_section_ids = selected_sections_ids if request.method == 'POST' else current_section_ids
            
    else:
        form = ExamForm(instance=exam)

    context = {
        'form': form,
        'exam': exam,
        'sections': available_sections,
        'current_section_ids': current_section_ids, 
        'center': center, # Shablon uchun center obyekti
    }
    return render(request, 'management/exam_edit.html', context)

@login_required(login_url='login')
@user_passes_test(is_teacher, login_url='index')
def exam_delete(request, slug, pk): # 🎯 SLUG QO'SHILDI
    """Imtihonni o'chirish (Faqat user.center ichida)."""
    center = get_object_or_404(Center, slug=slug)
    if request.user.center != center:
         messages.error(request, "Boshqa markaz imtihonini o'chirishga ruxsat yo'q.")
         return redirect('dashboard',slug=request.user.center.slug)
         
    # Examni o'zgartirdik: Faqat shu markazdagi o'qituvchilarning examlari
    exam = get_object_or_404(Exam, id=pk, teacher__center=center) 
    
    if request.method == 'POST':
        exam.delete() 
        messages.success(request, f"Imtihon '{exam.title}' muvaffaqiyatli o'chirildi!")
        return redirect('exam_list', slug=center.slug) # 🎯 SLUG Bilan REDIRECT
    
    return redirect('exam_list', slug=center.slug) # 🎯 SLUG Bilan REDIRECT


# ======================================================================
# 2. SECTION BOSHQARUVI (Center Ichida Umumiy)
# ======================================================================

@login_required(login_url='login')
@user_passes_test(is_teacher, login_url='index')
def section_list(request, slug): # 🎯 SLUG QO'SHILDI
    """Bo'limlar ro'yxatini ko'rish (Faqat user.center ichida umumiy)."""
    center = get_object_or_404(Center, slug=slug)
    if request.user.center != center:
         messages.error(request, "Boshqa markaz bo'limlarini ko'rishga ruxsat yo'q.")
         return redirect('dashboard',slug=request.user.center.slug)
         
    # 🎯 MUHIM O'ZGARTIRISH: Faqat shu markazdagi o'qituvchilar yaratgan bo'limlar
    sections = ExamSection.objects.filter(created_by__center=center).annotate(
        question_count=Count('static_questions')
    ).select_related('created_by') # Kim yaratganini yuklaymiz
    
    context = {'sections': sections, 'center': center}
    return render(request, 'management/section_list.html', context)

@login_required(login_url='login')
@user_passes_test(is_teacher, login_url='index')
def section_create(request, slug): # 🎯 SLUG QO'SHILDI
    """Yangi bo'lim yaratish (Faqat user.center ichida)."""
    center = get_object_or_404(Center, slug=slug)
    if request.user.center != center:
         messages.error(request, "Boshqa markazda bo'lim yaratishga ruxsat yo'q.")
         return redirect('dashboard',slug=request.user.center.slug)
         
    if request.method == 'POST':
        form = ExamSectionForm(request.POST) 

        if form.is_valid():
            try:
                with transaction.atomic():
                    section = form.save(commit=False)
                    if hasattr(section, 'created_by'):
                        section.created_by = request.user
                    section.save()
                    
                    messages.success(request, "Bo'lim ma'lumotlari muvaffaqiyatli saqlandi. Endi savollarni tanlang.")
                    # Savol tanlash sahifasiga yo'naltiramiz
                    return redirect('static_questions_add', slug=center.slug, section_id=section.pk) # 🎯 SLUG Bilan REDIRECT

            except Exception as e:
                messages.error(request, f"Bo‘limni saqlashda xato: {e}")
                print(f"Database error in section_create: {e}")
        else:
            messages.error(request, 'Xatolarni to‘g‘rilang.')
    else:
        form = ExamSectionForm()

    context = {
        'form': form,
        'center': center,
    }
    return render(request, 'management/section_create.html', context)

@login_required(login_url='login')
@user_passes_test(is_teacher, login_url='index')
def static_questions_add(request, slug, section_id): # 🎯 SLUG QO'SHILDI
    """Statik savollarni tanlash va yaratilgan bo'limga bog'lash sahifasi."""
    center = get_object_or_404(Center, slug=slug)
    if request.user.center != center:
         messages.error(request, "Boshqa markaz bo'limini boshqarishga ruxsat yo'q.")
         return redirect('dashboard',slug=request.user.center.slug)
         
    # 🎯 MUHIM: Faqat shu markazdagi o'qituvchilar yaratgan bo'limni tahrirlash
    section = get_object_or_404(ExamSection, pk=section_id, created_by__center=center)
    
    # ... Qolgan kod O'zgarishsiz, chunki savollar ro'yxati Centerga bog'liq emas (umumiy baza)
    # ... Faqat contextga center ni qo'shamiz
    
    initial_questions_ids = list(ExamSectionStaticQuestion.objects
                                 .filter(exam_section=section)
                                 .values_list('question_id', flat=True))
    
    topics = Topic.objects.all()
    questions = None
    
    if request.method == 'POST' or request.GET.get('subtopic_id'):
        subtopic_id = request.POST.get('subtopic') or request.GET.get('subtopic_id')
        if subtopic_id and subtopic_id.isdigit():
            questions = Question.objects.filter(subtopic_id=subtopic_id, status='published').select_related('subtopic')
    
    context = {
        'topics': topics,
        'section_id': section_id,
        'max_questions': section.max_questions,
        'section_name' : section.name,
        'section_type' : section.get_section_type_display(),
        'questions': questions,
        'initial_questions_ids': initial_questions_ids, 
        'center': center, # Shablon uchun center obyekti
    }
    return render(request, 'management/static_questions_add.html', context)


@login_required(login_url='login')
@user_passes_test(is_teacher, login_url='index')
def save_static_questions(request, slug, section_id):
    """Tanlangan savollarni ExamSectionStaticQuestion modeliga saqlash (AJAX orqali)."""
    
    # 1. Ob'ektlar va xavfsizlik tekshiruvi
    center = get_object_or_404(Center, slug=slug)
    
    if request.user.center != center:
        # Ruxsat yo'q
        return JsonResponse({'success': False, 'message': "Boshqa markaz bo'limini boshqarishga ruxsat yo'q"}, status=403)

    # 2. ✅ YO'NALTIRISH MANZILINI MARKAZ OBYEKTI OLINGANDAN SO'NG YARATISH
    # Ro'yxatga qaytarish uchun:
    redirect_url = reverse('section_list', kwargs={'slug': center.slug}) 
    
    # Agar tahrirlash sahifasiga qaytarish kerak bo'lsa, quyidagidan foydalaning:
    # redirect_url = reverse('section_edit', kwargs={'slug': center.slug, 'section_id': section_id}) 

    if request.method == 'POST':
        try:
            # Bo'limni olish (xavfsizlik tekshiruvi bilan)
            section = get_object_or_404(ExamSection, pk=section_id, created_by__center=center)
            selected_ids_str = request.POST.get('selected_questions_ids', '')
            
            question_ids = []
            if selected_ids_str:
                question_ids = [int(id_str) for id_str in selected_ids_str.split(',') if id_str.strip().isdigit()]
            
            # 3. Savollar sonini tekshirish
            if len(question_ids) > section.max_questions:
                 return JsonResponse({
                     'success': False, 
                     'message': f"Tanlangan savollar soni ({len(question_ids)}) maksimal son ({section.max_questions}) dan oshib ketdi."
                 }, status=400)

            # 4. Atomik saqlash logikasi
            with transaction.atomic():
                # Avvalgi savollarni o'chirish
                ExamSectionStaticQuestion.objects.filter(exam_section=section).delete()
                
                if question_ids:
                    # Yangi savollarni yaratish
                    new_questions = [
                        ExamSectionStaticQuestion(
                            exam_section=section, 
                            question_id=question_id, 
                            question_number=i + 1
                        ) for i, question_id in enumerate(question_ids)
                    ]
                    ExamSectionStaticQuestion.objects.bulk_create(new_questions)
                    
            # 5. Muvaffaqiyatli yakun (O'chirish ham, yangi qo'shish ham shu yerdan o'tadi)
            # Endi bu yerda yaratilgan redirect_url to'g'ri bo'ladi.
            return JsonResponse({
                'success': True, 
                'redirect_url': redirect_url,
                'message': "Savollar ro'yxati muvaffaqiyatli yangilandi."
            }) 
            
        except Exception as e:
            # Xatolikni qaytarish
            print(f"Error saving static questions: {e}")
            return JsonResponse({'success': False, 'message': f"Savollarni saqlashda xato yuz berdi: {str(e)}"}, status=500)
    
    # Faqat POST so'rov qabul qilinishini tasdiqlash
    return JsonResponse({'success': False, 'message': "Faqat POST so'rov qabul qilinadi"}, status=405)


@login_required(login_url='login')
@user_passes_test(is_teacher, login_url='index')
def section_edit(request, slug, section_id): # 🎯 SLUG QO'SHILDI
    """Bo'limni tahrirlash (Faqat user.center ichida umumiy)."""
    center = get_object_or_404(Center, slug=slug)
    if request.user.center != center:
         messages.error(request, "Boshqa markaz bo'limini tahrirlashga ruxsat yo'q.")
         return redirect('dashboard',slug=request.user.center.slug)
         
    # 🎯 MUHIM: Faqat shu markazdagi o'qituvchilar yaratgan bo'limni tahrirlash
    section = get_object_or_404(ExamSection, id=section_id, created_by__center=center)
    
    # ... Qolgan kod O'zgarishsiz, faqat REDIRECT ga slug qo'shiladi
    
    if request.method == 'POST':
        form = ExamSectionForm(request.POST, instance=section) 
        selected_ids_str = request.POST.get('selected_questions_ids', '')

        if form.is_valid():
            try:
                with transaction.atomic():
                    section = form.save()
                    
                    question_ids = []
                    if selected_ids_str:
                        question_ids = [int(id_str) for id_str in selected_ids_str.split(',') if id_str.strip().isdigit()]

                    ExamSectionStaticQuestion.objects.filter(exam_section=section).delete()

                    if question_ids:
                        if len(question_ids) > section.max_questions:
                            messages.error(request, f"Tanlangan savollar soni ({len(question_ids)}) maksimal son ({section.max_questions}) dan oshib ketdi.")
                            return render(request, 'management/section_edit.html', {'section': section, 'form': form})
                                
                        new_questions = [
                            ExamSectionStaticQuestion(
                                exam_section=section, 
                                question_id=question_id, 
                                question_number=i + 1
                            ) for i, question_id in enumerate(question_ids)
                        ]
                        ExamSectionStaticQuestion.objects.bulk_create(new_questions)

                messages.success(request, f"Bo'lim '{section.name}' muvaffaqiyatli tahrirlandi va savollar yangilandi!")
                return redirect('section_list', slug=center.slug) # 🎯 SLUG Bilan REDIRECT

            except Exception as e:
                messages.error(request, f"Bo‘limni saqlashda kutilmagan xato: {e}")
                print(f"Database error in section_edit: {e}")
        else:
            messages.error(request, "Xatolarni to'g'rilang. Forma maydonlarida muammo bor.")
            
    else:
        form = ExamSectionForm(instance=section)
        
    context = {
        'section': section,
        'form': form,
        'center': center, # Shablon uchun center obyekti
    }
    return render(request, 'management/section_edit.html', context)

@login_required(login_url='login')
@user_passes_test(is_teacher, login_url='index')
def section_delete(request, slug, section_id):
    """
    Bo'limni o'chirish (Faqat user.center ga tegishli bo'lgan markazda).
    URL: /center/<slug>/section/<int:section_id>/delete/
    """
    
    # 1. Markazni tekshirish (Slug orqali)
    try:
        center = get_object_or_404(Center, slug=slug)
    except Exception:
        messages.error(request, "Ko'rsatilgan markaz topilmadi.")
        return redirect('dashboard',slug=request.user.center.slug) # Markaz topilmasa boshqaruv paneliga

    # 2. Foydalanuvchi markazini tekshirish (Xavfsizlik)
    if request.user.center != center:
        messages.error(request, "Siz boshqa markaz bo'limini o'chirishga ruxsat ololmadingiz.")
        return redirect('dashboard',slug=request.user.center.slug)
        
    # 3. Bo'limni topish (Markazga va yaratuvchiga bog'lab)
    # Faqat shu markazdagi o'qituvchilar yaratgan bo'limni o'chirish
    try:
        # created_by__center=center tekshiruvi muhim xavfsizlik filtri
        section = get_object_or_404(
            ExamSection, 
            id=section_id, 
            created_by__center=center
        )
    except Exception:
        messages.error(request, "Bo'lim topilmadi yoki siz uni o'chirishga ruxsatga ega emassiz.")
        return redirect('section_list', slug=center.slug)

    # 4. O'chirish Mantiqi (POST so'rovi orqali)
    if request.method == 'POST':
        section.delete()
        messages.success(request, f"'{section.name}' bo'limi muvaffaqiyatli o'chirildi!")
        
        # 5. Qaytarish (Bo'limlar ro'yxatiga)
        return redirect('section_list', slug=center.slug) 
    
    # GET so'rovi (yoki POST bo'lmagan so'rov) kelganida, shunchaki ro'yxatga qaytarish.
    # Bu Modal ishlatilgani uchun to'g'ri, chunki tasdiqlash sahifasi yo'q.
    return redirect('section_list', slug=center.slug)

# ======================================================================
# 2. AJAX ENDPOINTLARI
# ======================================================================

@login_required(login_url='login')
@user_passes_test(is_teacher, login_url='index')
def get_subtopics(request, slug): # 🎯 SLUG QO'SHILDI
    """
    Topic bo'yicha Subtopic'larni olish. 
    Faqat joriy Center'ga tegishli o'qituvchilar yaratgan Subtopic'lar qaytadi.
    """
    user = request.user
    center = get_object_or_404(Center, slug=slug)
    
    # 1. Xavfsizlik tekshiruvi
    if user.center != center:
        return JsonResponse({'error': "Ruxsat yo'q. Boshqa markaz Subtopic'lari."}, status=403)
        
    topic_id = request.GET.get('topic_id')
    if not topic_id or not topic_id.isdigit():
        return JsonResponse({'error': 'Topic ID noto‘g‘ri yoki mavjud emas'}, status=400)
        
    try:
        # 2. Filtrlash: Berilgan topic_id bo'yicha VA shu markaz o'qituvchilari tomonidan yaratilgan subtopiclar
        subtopics = Subtopic.objects.filter(
            topic_id=topic_id,
            center = center,
        ).order_by('name')
        
        data = [{'id': sub.id, 'name': sub.name} for sub in subtopics]
        return JsonResponse(data, safe=False)
        
    except Exception as e:
        print(f"Error in get_subtopics: {e}")
        return JsonResponse({'error': f"Ma'lumot olishda xato: {str(e)}"}, status=500)

from django.template.loader import render_to_string

@login_required(login_url='login')
@user_passes_test(is_teacher, login_url='index')
def get_questions(request, slug): # 🎯 SLUG QO'SHILDI
    """
    Subtopic bo'yicha savollarni olish. 
    Faqat joriy Center'ga tegishli o'qituvchilar yaratgan savollar qaytadi.
    """
    user = request.user
    center = get_object_or_404(Center, slug=slug)
    
    # 1. Xavfsizlik tekshiruvi
    if user.center != center:
        return JsonResponse({'error': "Ruxsat yo'q. Boshqa markaz savollari."}, status=403)

    subtopic_id = request.GET.get('subtopic_id')
    if not subtopic_id or not subtopic_id.isdigit():
        return JsonResponse({'error': 'Subtopic ID noto‘g‘ri yoki mavjud emas'}, status=400)
        
    try:
        # 2. Filtrlash: Berilgan subtopic_id bo'yicha VA shu markaz o'qituvchilari tomonidan yaratilgan savollar
        questions = Question.objects.filter(
            subtopic_id=subtopic_id,
            #status='published',
            center=center  # 🎯 Markazga bog'lash
        ).select_related('subtopic').prefetch_related('options').order_by('id')
        
        if not questions.exists():
            html = render_to_string('partials/questions_list.html', {'questions': questions, 'center': center}, request=request)
            return JsonResponse({'html': html})

        html = render_to_string('partials/questions_list.html', {'questions': questions, 'center': center}, request=request)
        return JsonResponse({'html': html})
        
    except Exception as e:
        print(f"Error in get_questions: {e}")
        return JsonResponse({'error': f"Savollarni olishda xato: {str(e)}"}, status=500)

# =========================================================
# A. KURS MODULLARI BOSHQARUVI (module_list, module_create, ...)
# =========================================================
@login_required(login_url='login')
def module_list(request, course_id):
    """ Kursning barcha modullari ro'yxati va boshqaruvi. """
    # if not (is_teacher(request.user) or request.user.is_staff):
    #     messages.error(request, "Sizda bu bo'limga kirish huquqi yo'q.")
    #     return redirect('dashboard',slug=request.user.center.slug)
    
    course = get_object_or_404(Course, id=course_id)
    
    # Har bir modul ichidagi darslarni o'z ichiga olgan so'rov
    modules = CourseModule.objects.filter(course=course).order_by('order').prefetch_related(
        Prefetch('lessons', queryset=Lesson.objects.order_by('order'), to_attr='lessons_list')
    )
    
    context = {
        'course': course,
        'modules': modules,
        'page_title': f"'{course.title}' kursining modullari"
    }
    return render(request, 'management/module_list.html', context)

@login_required
def module_create(request, course_id):
    """
    Yangi modul yaratish funksiyasi.
    """
    course = get_object_or_404(Course, id=course_id)
    
    if request.method == 'POST':
        form = CourseModuleForm(request.POST)
        if form.is_valid():
            # 1. Ob'ektni bazaga saqlamay turib olish
            new_module = form.save(commit=False)
            new_module.course = course
            
            # 🔥 2. Eng katta order raqamini topish va 1 qo'shish
            # Module.objects o'rniga CourseModule.objects ishlatildi
            max_order = CourseModule.objects.filter(course=course).aggregate(Max('order'))['order__max']
            # Agar hali modul bo'lmasa, 1 dan boshlaymiz (yoki mavjud bo'lsa, keyingisini olamiz)
            new_module.order = (max_order or 0) + 1
            
            # 3. Yakuniy saqlash
            new_module.save()
            messages.success(request, f"'{new_module.title}' moduli muvaffaqiyatli yaratildi.")
            return redirect('module_list', course_id=course.id)
        else:
            messages.error(request, "Iltimos, formadagi xatolarni to'g'irlang.") # Xato xabari
    else:
        form = CourseModuleForm()

    context = {
        'form': form,
        'course': course,
    }
    
    return render(request, 'management/module_form.html', context)

@login_required 
def module_update(request, course_id, module_id):
    """
    Mavjud modulni tahrirlash funksiyasi.
    """
    # 1. Kursni topish
    course = get_object_or_404(Course, id=course_id)
    
    # 2. Tahrirlanadigan modulni topish (Kursga bog'langanligini tekshirish muhim)
    module = get_object_or_404(CourseModule, id=module_id, course=course) # CourseModule dan topildi

    if request.method == 'POST':
        # POST: Formani yuborilgan ma'lumotlar bilan va mavjud modul ob'ekti bilan yuklash
        form = CourseModuleForm(request.POST, instance=module)
        if form.is_valid():
            # Formani saqlash 
            module_instance = form.save()
            messages.success(request, f"'{module_instance.title}' moduli muvaffaqiyatli tahrirlandi.") # Muvaffaqiyat xabari
            
            # Muvaffaqiyatli saqlashdan keyin modullar ro'yxatiga qaytarish
            return redirect('module_list', course_id=course.id)
        else:
            messages.error(request, "Iltimos, formadagi xatolarni to'g'irlang.")
    else:
        # GET: Mavjud modul ma'lumotlari bilan formani yuklash
        form = CourseModuleForm(instance=module)

    context = {
        'form': form,
        'course': course,  # Shablon uchun kerak
        'module': module,  # Tahrirlash sarlavhasi uchun kerak
    }
    
    # module_form.html shablonini render qilish
    return render(request, 'management/module_form.html', context)

@login_required
def module_delete(request, course_id, module_id):
    """
    Modulni o'chirish funksiyasi.
    """
    # Kurs va modulni topamiz. Modulning ushbu kursga tegishli ekanligini tekshiramiz.
    course = get_object_or_404(Course, id=course_id)
    module = get_object_or_404(CourseModule, id=module_id, course=course) # CourseModule dan topildi

    # Agar POST so'rovi kelsa (o'chirishni tasdiqlash uchun)
    if request.method == 'POST':
        module_title = module.title # O'chirishdan oldin nomini saqlab olamiz
        module.delete()
        
        messages.success(request, f"'{module_title}' moduli muvaffaqiyatli o'chirildi.") # Muvaffaqiyat xabari
        # Muvaffaqiyatli o'chirishdan keyin modullar ro'yxatiga qaytarish
        return redirect('module_list', course_id=course.id)

    # GET so'rovini qabul qilmaslik kerak, lekin agar kelsa, ro'yxatga qaytaramiz
    return redirect('module_list', course_id=course.id)

# =========================================================
# B. DARS BOSHQARUVI (lesson_list, lesson_create, ...)
# =========================================================

@login_required(login_url='login')
def lesson_list(request, module_id):
    """ Modul ichidagi darslar va resurslar boshqaruvi. """
    module = get_object_or_404(CourseModule, id=module_id)
    
    # Har bir darsning resurslarini yuklash
    lessons = Lesson.objects.filter(module=module).order_by('order').prefetch_related(
        Prefetch('resources', queryset=LessonResource.objects.order_by('order'), to_attr='resources_list')
    ).select_related('related_exam') # Testni ham yuklaymiz
    
    context = {
        'module': module,
        'course': module.course,
        'lessons': lessons,
        'page_title': f"'{module.title}' modulining darslari"
    }
    return render(request, 'management/lesson_list.html', context)

@login_required(login_url='login')
def lesson_create(request, module_id):
    """ Yangi dars yaratish. """
    module = get_object_or_404(CourseModule, id=module_id)
    
    if request.method == 'POST':
        form = LessonForm(request.POST)
        if form.is_valid():
            lesson = form.save(commit=False)
            lesson.module = module
            lesson.save()
            messages.success(request, f"'{lesson.title}' darsi yaratildi. Endi resurslarni qo'shing.")
            return redirect('lesson_list', module_id=module.id)
    else:
        form = LessonForm()
        
    context = {
        'form': form,
        'module': module,
        'page_title': f"'{module.title}' moduliga dars qo'shish"
    }
    return render(request, 'management/lesson_form.html', context)

@login_required(login_url='login')
def lesson_update(request, lesson_id):
    """ Mavjud darsni tahrirlash (lesson_form ga ulanadi). """
    # Darsni olish. Agar ulanishda module_id ham talab qilinsa, u holda uni ham tekshirish kerak.
    # Lekin URL faqat lesson_id talab qiladi deb hisoblaymiz.
    lesson = get_object_or_404(Lesson, id=lesson_id)
    module = lesson.module
    
    if request.method == 'POST':
        form = LessonForm(request.POST, instance=lesson)
        if form.is_valid():
            form.save()
            messages.success(request, f"'{lesson.title}' darsi muvaffaqiyatli tahrirlandi.")
            return redirect('lesson_list', module_id=module.id)
    else:
        form = LessonForm(instance=lesson)
        
    context = {
        'form': form,
        'module': module,
        # lesson_form.html ishlatilgani uchun title o'zgaruvchisi o'rniga modul o'zgaruvchisi kerak
        'page_title': f"'{lesson.title}' darsini tahrirlash" 
    }
    # lesson_form.html shablonidan foydalaniladi
    return render(request, 'management/lesson_form.html', context)

@login_required(login_url='login')
def lesson_delete(request, lesson_id):
    """ Darsni o'chirish (lesson_list sahifasidagi modal orqali tasdiqlanadi). """
    lesson = get_object_or_404(Lesson, id=lesson_id)
    module_id = lesson.module.id

    # O'chirish faqat POST so'rovi orqali amalga oshiriladi
    if request.method == 'POST':
        lesson_title = lesson.title
        lesson.delete()
        messages.success(request, f"'{lesson_title}' darsi muvaffaqiyatli o'chirildi.")
    
    # Har doim ro'yxat sahifasiga qaytish
    return redirect('lesson_list', module_id=module_id)

# =========================================================
# C. RESURS BOSHQARUVI (Linklarni qo'shish)
# =========================================================

@login_required(login_url='login')
def resource_create(request, lesson_id):
    """ Darsga yangi resurs (link) qo'shish. """
    lesson = get_object_or_404(Lesson, id=lesson_id)
    
    if request.method == 'POST':
        form = LessonResourceForm(request.POST)
        if form.is_valid():
            resource = form.save(commit=False)
            resource.lesson = lesson
            resource.save()
            messages.success(request, f"Yangi '{resource.get_resource_type_display()}' resursi qo'shildi.")
            # Keyin resurslar ro'yxati sahifasiga qaytish kerak (lesson_detail yoki shunga o'xshash)
            return redirect('lesson_list', module_id=lesson.module.id)
    else:
        form = LessonResourceForm()
        
    context = {
        'form': form,
        'lesson': lesson,
        'page_title': f"'{lesson.title}' darsiga resurs qo'shish"
    }
    return render(request, 'management/resource_form.html', context)


# =========================================================
# D. JADVAL BOSHQARUVI (Offline/Muddatli kurslar uchun)
# =========================================================

@login_required(login_url='login')
def schedule_list(request, course_id):
    """ Kursning dars jadvallarini boshqarish. """
    course = get_object_or_404(Course, id=course_id)
    
    # Faqat Offline yoki Muddatli Online kurslar uchun ruxsat berish
    if course.is_online and not course.is_scheduled:
        messages.warning(request, "Bu kurs ixtiyoriy rejimda. Jadval belgilash shart emas.")
        return redirect('module_list', course_id=course.id)
        
    schedules = CourseSchedule.objects.filter(course=course).order_by('start_time').select_related('related_lesson')
    
    context = {
        'course': course,
        'schedules': schedules,
        'page_title': f"'{course.title}' kursining dars jadvallari"
    }
    return render(request, 'management/schedule_list.html', context)

@login_required(login_url='login')
def schedule_create(request, course_id):
    """ Yangi dars jadvalini yaratish. """
    course = get_object_or_404(Course, id=course_id)
    
    if request.method == 'POST':
        # Formaga faqat shu kursga tegishli darslarni uzatamiz
        form = CourseScheduleForm(request.POST, course_instance=course)
        if form.is_valid():
            schedule = form.save(commit=False)
            schedule.course = course
            schedule.save()
            messages.success(request, "Dars jadvali muvaffaqiyatli qo'shildi.")
            return redirect('schedule_list', course_id=course.id)
    else:
        form = CourseScheduleForm(course_instance=course)
        
    context = {
        'form': form,
        'course': course,
        'page_title': f"'{course.title}' uchun jadval yaratish"
    }
    return render(request, 'management/schedule_form.html', context)

@login_required(login_url='login')
def schedule_update(request, course_id, schedule_id):
    """ Mavjud CourseSchedule ni tahrirlash funksiyasi. 
        Bu funksiya siz so'ragan 'schedule_update' view'idir.
    """
    course = get_object_or_404(Course, id=course_id)
    # CourseSchedule modelidan foydalanamiz
    schedule = get_object_or_404(CourseSchedule, id=schedule_id, course=course)

    if request.method == 'POST':
        # Formaga POST ma'lumotlarini, instance ni (tahrirlash uchun) va course_instance ni (filtratsiya uchun) yuboramiz
        form = CourseScheduleForm(request.POST, instance=schedule, course_instance=course)
        if form.is_valid():
            form.save()
            messages.success(request, f"Jadval muvaffaqiyatli tahrirlandi.")
            return redirect('schedule_list', course_id=course.id)
    else:
        # GET so'rovi uchun instance ni (mavjud ma'lumotlarni to'ldirish uchun) va course_instance ni yuboramiz
        form = CourseScheduleForm(instance=schedule, course_instance=course)

    context = {
        'form': form,
        'course': course,
        'schedule': schedule,
        'page_title': "Jadvalni tahrirlash"
    }
    return render(request, 'management/schedule_form.html', context)


@login_required(login_url='login')
def schedule_delete(request, course_id, schedule_id):
    """ CourseSchedule ob'ektini o'chirish funksiyasi. """
    # Tasdiqlash sahifasi o'rniga, amaliyotni bevosita POST so'rov orqali amalga oshiramiz
    course = get_object_or_404(Course, id=course_id)
    schedule = get_object_or_404(CourseSchedule, id=schedule_id, course=course)
    
    schedule.delete()
    messages.warning(request, f"Jadval muvaffaqiyatli o'chirildi.")
    return redirect('schedule_list', course_id=course.id)


@login_required
def tag_list_view(request, slug):
    """
    Markazga (Center) tegishli taglar ro'yxatini ko'rsatish va ular bo'yicha statistikani hisoblash.
    """
    # 1. Center obyektini slug orqali olamiz
    center = get_object_or_404(Center, slug=slug)

    # 2. Taglarni Center bo'yicha filterlaymiz va statistikani hisoblaymiz
    tags = Tag.objects.filter(
        # Faqat joriy Centerga tegishli taglar
        center=center
    ).annotate(
        # 1. Tegga bog'langan savollar soni
        question_count=Count('question', distinct=True),
        
        # 2. Ushbu teg bo'yicha umumiy to'g'ri javoblar soni (UserTagPerformance dan)
        total_correct=Sum('user_performances__correct_answers'),
        
        # 3. Ushbu teg bo'yicha umumiy urinishlar soni
        total_attempts=Sum('user_performances__attempts_count'),
        
        # 4. Teg bo'yicha o'rtacha muvaffaqiyat darajasini hisoblash
        # Eslatma: Bu hisoblash barcha foydalanuvchilarning ushbu teg bo'yicha umumiy ko'rsatkichini oladi.
        avg_success_rate=Avg(
            F('user_performances__correct_answers') * 100.0 / 
            (F('user_performances__correct_answers') + F('user_performances__incorrect_answers')),
            # divide by zero xatosini oldini olish uchun
            # Agar sizda Django 4.0+ bo'lsa, bu yo'l to'g'ri
            default=0.0
        )
        
    ).order_by('name') # Tag nomiga ko'ra tartiblash

    context = {
        'tags': tags,
        'title': f"{center.name} Markazi uchun Teglar / Mavzular ro'yxati",
        'center': center, # Shablon uchun Center obyektini uzatamiz
    }
    return render(request, 'management/tag_list.html', context)

@login_required
def tag_create_or_update_view(request, slug, tag_id=None):
    """
    Centerga tegishli yangi teg yaratish yoki mavjudini tahrirlash sahifasi.
    """
    # Joriy Center obyektini olish
    center = get_object_or_404(Center, slug=slug)

    if tag_id:
        # Tahrirlash rejimi: Faqat joriy Centerga tegishli Tag'ni olish
        tag = get_object_or_404(Tag, id=tag_id, center=center)
        is_creating = False
        title = f"'{tag.name}' tegini tahrirlash"
    else:
        # Yaratish rejimi
        tag = None
        is_creating = True
        title = "Yangi Teg / Mavzu yaratish"

    if request.method == 'POST':
        # TagFormga qo'shimcha ravishda Center obyektini uzatish kerak bo'lishi mumkin
        form = TagForm(request.POST, instance=tag)
        if form.is_valid():
            new_tag = form.save(commit=False)
            
            # Agar yangi yaratilayotgan bo'lsa, Center'ni belgilash
            if is_creating:
                new_tag.center = center 
                
            new_tag.save()
            form.save_m2m() # Agar form.save(commit=False) ishlatilsa, M2M saqlash
            
            action = "yaratildi" if is_creating else "tahrirlandi"
            messages.success(request, f"Teg muvaffaqiyatli {action}: {new_tag.get_full_hierarchy()}")
            
            # Center slug bilan tag_list ga qaytarish
            return redirect('tag_list', slug=center.slug) 
        else:
            messages.error(request, "Xatolik: Ma'lumotlarni tekshiring.")
    else:
        form = TagForm(instance=tag)

    context = {
        'form': form,
        'tag': tag,
        'is_creating': is_creating,
        'title': title,
        'center': center, # Shablon uchun Center obyektini uzatish
    }
    return render(request, 'management/tag_create_or_update.html', context)

@login_required
def tag_delete_view(request, slug, tag_id):
    """
    Centerga tegishli Tegni o'chirish.
    """
    # 1. Joriy Center obyektini olish
    center = get_object_or_404(Center, slug=slug)
    
    # 2. Faqat joriy Centerga tegishli Tag'ni olish (Xavfsizlik)
    tag = get_object_or_404(Tag, id=tag_id, center=center)
    
    if request.method == 'POST':
        tag_name = tag.get_full_hierarchy()
        
        # Bog'langan barcha child taglarni ham o'chiradi
        tag.delete()
        
        messages.success(request, f"Teg muvaffaqiyatli o'chirildi: {tag_name}")
        # Center slug bilan tag_list ga qaytarish
        return redirect('tag_list', slug=center.slug)
        
    context = {
        'tag': tag,
        'title': f"'{tag.name}' tegini o'chirish",
        'center': center, # Shablon uchun Center obyektini uzatish
    }
    # Haqiqiy o'chirish uchun alohida tasdiqlash sahifasiga yuboriladi
    return render(request, 'management/tag_confirm_delete.html', context)


@user_passes_test(is_admin) 
def center_list_view(request):
    """
    Super Admin uchun barcha O'quv Markazlari ro'yxatini ko'rsatish.
    'Ega' ustuni o'rniga 'Xodimlar' ro'yxatini ko'rsatishga moslandi.
    """
    
    centers = Center.objects.all().order_by('-id').prefetch_related(
        'subscriptions', 
        'members',           # Markazga biriktirilgan xodimlar (teacher/center_admin)
        'groups__students'   # Guruhlar va ularning o'quvchilari
    ).annotate(
        # Barcha guruhlardagi noyob o'quvchilar sonini DB darajasida hisoblash
        student_count_db=Count('groups__students', distinct=True)
    )
    
    for center in centers:
        # 1. Obuna holati
        center.is_valid = center.is_subscription_valid 
        
        # 2. Eng so'nggi aktiv obuna 
        center.active_subscription = next(
            (sub for sub in center.subscriptions.all() if sub.is_active and sub.end_date >= date.today()), 
            None
        )
        
        # 3. Markazga biriktirilgan xodimlar (Superuserlar bu ro'yxatga kirmaydi)
        center.teachers = [user for user in center.members.all() if not user.is_superuser]

        # 4. Guruhlar ro'yxati (AJAX uchun ma'lumotni tayyorlash)
        center.all_groups = list(center.groups.all())
        
        # 5. O'quvchilar sonini Annotate orqali olish
        center.student_count = center.student_count_db 
        
    # TeacherAssignmentForm() mavjudligini faraz qilamiz
    # Agar bu formani view ichida yaratish muammo bo'lsa, uni yubormasdan ham ishlataverish mumkin.
    try:
         assignment_form = TeacherAssignmentForm()
    except NameError:
         assignment_form = None

    context = {
        'centers': centers,
        'title': "O'quv Markazlari Boshqaruvi",
        'TeacherAssignmentForm': assignment_form, 
    }
    return render(request, 'admin_panel/center_list.html', context)

@user_passes_test(is_admin)
def center_edit_view(request, center_id=None):
    """
    Markazni yaratish/tahrirlash logikasi.
    """
    is_create = center_id is None
    center = None
    
    if not is_create:
        center = get_object_or_404(Center, id=center_id)

    if request.method == 'POST':
        form = CenterForm(request.POST, instance=center)
        
        if form.is_valid():
            try:
                with transaction.atomic():
                    center_instance = form.save(commit=False)
                    
                    if is_create:
                        # --- YARATISH MANTIQI ---
                        # Bu yerda Markaz egasi avtomatik tayinlanmaydi (keyinchalik Assign modal orqali qilinadi)
                        center_instance.save() 
                        
                        months = form.cleaned_data.get('subscription_months')
                        
                        if months and months > 0:
                            end_date = date.today() + timedelta(days=months * 30)
                            
                            Subscription.objects.create(
                                center=center_instance,
                                end_date=end_date,
                                price=0.00, 
                                is_active=True
                            )
                        
                        messages.success(request, f"'{center_instance.name}' markazi muvaffaqiyatli yaratildi. Obuna: {months} oy.")
                    else:
                        # --- TAHRIRLASH MANTIQI ---
                        center_instance.save()
                        messages.success(request, f"'{center_instance.name}' markazi ma'lumotlari muvaffaqiyatli yangilandi.")

                    return redirect('center_list')
            except Exception as e:
                messages.error(request, f"Saqlashda kutilmagan xatolik yuz berdi. Iltimos, admin bilan bog'laning.")
                # Xato loglarini yozish tavsiya etiladi
                # print(f"DEBUG ERROR: {e}") 
        else:
            messages.error(request, "Shaklda xatoliklar mavjud. Iltimos, ma'lumotlarni tekshiring.")
    else:
        # GET so'rovi (sahifani yuklash)
        form = CenterForm(instance=center)
    
    context = {
        'form': form,
        'center': center,
        'is_create': is_create,
        'title': "Yangi O'quv Markazi Yaratish" if is_create else f"'{center.name}' markazini tahrirlash",
    }
    # 💥 Shablon nomini to'g'ri chaqirish
    return render(request, 'admin_panel/center_edit.html', context)

@user_passes_test(is_admin)
def center_delete_view(request, center_id):
    center = get_object_or_404(Center, id=center_id)
    if request.method == 'POST':
        center_name = center.name
        center.delete()
        messages.success(request, f"'{center_name}' markazi muvaffaqiyatli o'chirildi.")
        return redirect('center_list')
    return redirect('center_list') 

@user_passes_test(is_admin)
def remove_teacher_view(request, center_id, user_id):
    """Xodimni (o'qituvchini) markazdan ajratish (o'chirmasdan)."""
    center = get_object_or_404(Center, id=center_id)
    # Faqat shu markazga tegishli userni topish
    user_to_remove = get_object_or_404(CustomUser, id=user_id, center=center) 
    
    if request.method == 'POST':
        try:
            # Markaz egasini o'chirishni cheklash
            if user_to_remove.id == center.owner_id:
                 messages.error(request, f"Markaz egasini ({user_to_remove.username}) chiqarish mumkin emas. Avval Owner'ni o'zgartiring.")
                 return redirect('center_list')
                 
            user_to_remove.center = None # CustomUser'dan markazni ajratish
            # is_staff = False qatori o'chirildi
            user_to_remove.save()
            messages.warning(request, f"'{user_to_remove.username}' foydalanuvchisi '{center.name}' markazidan chiqarildi.")
        except Exception as e:
             messages.error(request, f"O'chirishda xatolik: {e}")
             
    return redirect('center_list')

@user_passes_test(is_admin)
@require_POST
def assign_teacher_to_center(request, center_id):
    """
    Tanlangan foydalanuvchini markazga biriktiradi, 
    agar u o'qituvchi bo'lmasa, rolini 'teacher' ga o'zgartiradi.
    """
    
    # HTML dan kelgan field nomi: name="user_to_assign"
    teacher_id = request.POST.get('user_to_assign') 
    
    if not teacher_id:
        messages.error(request, "Iltimos, biriktirish uchun foydalanuvchini tanlang.")
        return redirect('center_list')
        
    try:
        center = get_object_or_404(Center, id=center_id)
        teacher = get_object_or_404(CustomUser, id=teacher_id)
        
        # O'qituvchi allaqachon boshqa markazga biriktirilgan bo'lsa, xatolik
        if teacher.center is not None and teacher.center != center:
             messages.error(request, f"'{teacher.full_name or teacher.username}' allaqachon '{teacher.center.name}' markaziga biriktirilgan.")
             return redirect('center_list')

        with transaction.atomic():
            # 1. Rolini 'teacher' ga o'zgartirish (agar student yoki boshqa rol bo'lsa)
            if teacher.role != 'teacher':
                 teacher.role = 'teacher'
                 # Agar rol o'zgarsa, unga staff huquqini berish kerakmi?
                 # teacher.is_staff = True # Kerak bo'lsa yoqib qo'ying
            
            # 2. O'qituvchini markazga biriktirish
            teacher.center = center
            teacher.save()
            
            messages.success(request, f"'{teacher.full_name or teacher.username}' muvaffaqiyatli ravishda '{center.name}' markaziga biriktirildi va ROLI O'QITUVCHIGA o'zgartirildi.")
            
    except Exception as e:
        messages.error(request, f"Xodimni biriktirishda xatolik yuz berdi: {e}")
        
    return redirect('center_list')

@user_passes_test(is_admin)
def search_unassigned_teachers_ajax(request):
    """
    Markazga biriktirilmagan (center__isnull=True) va admin/owner bo'lmagan 
    aktiv foydalanuvchilarni qidiradi. Rolidan qat'iy nazar qidiriladi.
    """
    q = request.GET.get('q', '')
    
    users_qs = CustomUser.objects.filter(
        center__isnull=True,  
        is_active=True
    ).exclude(
        Q(role='admin') | Q(is_superuser=True)
    )
    
    if q:
        users_qs = users_qs.filter(
            Q(full_name__icontains=q) |
            Q(username__icontains=q) |
            Q(phone_number__icontains=q)
        ).distinct()
        
    users = users_qs[:10] 

    results = []
    for user in users:
        role_display = user.get_role_display() if hasattr(user, 'get_role_display') else user.role
        display_text = f"{user.full_name or user.username} (Rol: {role_display})"
        
        results.append({
            'id': user.id,
            'text': display_text, 
        })

    return JsonResponse({
        'items': results,
        'total_count': users_qs.count()
    })

@user_passes_test(is_admin) 
def center_groups_ajax(request, center_id):
    """Berilgan markazdagi guruhlar ro'yxatini AJAX orqali qaytaradi."""
    center = get_object_or_404(Center, id=center_id)
    
    groups_data = []
    
    # Guruhlar ro'yxatini yuklash, o'qituvchi ma'lumotini yuklash va o'quvchilar sonini hisoblash
    groups = center.groups.select_related('teacher').annotate(
        student_count=Count('students')
    ).all().order_by('-created_at')
    
    for group in groups:
        groups_data.append({
            'id': group.pk,
            'name': group.name,
            'is_active': group.is_active,
            'teacher_username': group.teacher.username,
            'student_count': group.student_count, 
            # Guruhni boshqarish sahifasi URL manzilini to'g'ri o'rnating
            'manage_url': f'/groups/{group.pk}/manage/', 
        })
        
    return JsonResponse({'groups': groups_data, 'total_count': groups.count()})


@login_required(login_url='login')
@user_passes_test(is_teacher, login_url='index')
def group_list_view(request, slug):
    """
    Berilgan slug'ga mos Center'dagi guruhlar ro'yxatini ko'rsatadi.
    Center Admin barcha guruhlarni, Teacher faqat o'z guruhlarini ko'radi.
    """
    user = request.user
    
    # 1. Center obyektini slug orqali topish
    center = get_object_or_404(Center, slug=slug)
    
    # Xavfsizlik: Foydalanuvchi shu markazga tegishli ekanligini tekshirish
    if user.center != center:
         messages.error(request, _("Siz bu markaz guruhlarini ko'rish huquqiga ega emassiz."))
         return redirect('dashboard',slug=request.user.center.slug)
    
    # 2. Guruhlarni filtrlash
    if user.role == 'center_admin':
        # Center Admin: Markazdagi barcha guruhlar
        groups = Group.objects.filter(center=center).order_by('-created_at')
    else: # user.role == 'teacher'
        # Teacher: Faqat o'zi yaratgan guruhlar
        groups = Group.objects.filter(teacher=user, center=center).order_by('-created_at')
        
    context = {
        'groups': groups,
        'title': _("Guruhlar Ro'yxati"),
        'center': center, # Shablon uchun center obyekti
        'is_center_admin': user.role == 'center_admin',
    }
    return render(request, 'management/group_list.html', context)

@login_required(login_url='login')
@user_passes_test(is_teacher, login_url='index')
def group_create_view(request, slug):
    """
    Berilgan slug'ga mos Center'da yangi guruh yaratish.
    """
    user = request.user
    
    # 1. Center obyektini slug orqali topish
    center = get_object_or_404(Center, slug=slug)
    
    if user.center != center:
         messages.error(request, _("Guruhni boshqa markazda yaratishga ruxsat yo'q."))
         return redirect('dashboard',slug=request.user.center.slug)

    if request.method == 'POST':
        # Formaga markaz ma'lumotlarini uzatamiz
        form = GroupForm(request.POST, request=request, teacher=user, center=center)
        
        if form.is_valid():
            group = form.save(commit=False)
            group.teacher = user
            group.center = center # Guruhni topilgan markazga bog'laymiz
            group.save()
            
            students_to_add = form.cleaned_data.get('students')
            
            if students_to_add:
                student_ids = [student.pk for student in students_to_add]
                
                # Center ID si NULL bo'lgan o'quvchilarni shu markazga biriktirish
                students_to_update = CustomUser.objects.filter(
                    pk__in=student_ids, 
                    center__isnull=True 
                )
                updated_count = students_to_update.update(center=center)
                
                if updated_count > 0:
                    messages.warning(request, _(f"Guruhga qo'shilgan {updated_count} ta o'quvchi avtomatik ravishda '{center.name}' markaziga biriktirildi."))
                
                group.students.set(students_to_add) 
                
            messages.success(request, _(f"'{group.name}' nomli yangi guruh muvaffaqiyatli yaratildi!"))
            return redirect('group_list', slug=center.slug) 
            
    else:
        form = GroupForm(request=request, teacher=user, center=center)

    context = {
        'form': form,
        'title': _("Yangi Guruh Yaratish"),
        'center': center, # Shablon uchun center obyekti
        'is_create': True,
    }
    return render(request, 'management/group_form.html', context)

@login_required(login_url='login')
@user_passes_test(is_teacher, login_url='index')
def group_update_view(request, slug, pk):
    """
    Berilgan slug'ga mos Center'da guruhni tahrirlash.
    Ruxsat: Center Admin yoki Guruhning yaratuvchisi.
    """
    user = request.user
    
    # 1. Center obyektini slug orqali topish
    center = get_object_or_404(Center, slug=slug)
        
    if user.center != center:
         messages.error(request, _("Boshqa markaz guruhini tahrirlashga ruxsat yo'q."))
         return redirect('dashboard',slug=request.user.center.slug)
        
    # 2. Guruhni topish (pk va center bo'yicha cheklash)
    group = get_object_or_404(Group, pk=pk, center=center)

    # 3. Ruxsat tekshiruvi: Agar oddiy o'qituvchi bo'lsa, faqat o'zining guruhini tahrirlasin
    if user.role == 'teacher' and group.teacher != user:
        messages.error(request, _("Siz bu guruhni tahrirlash huquqiga ega emassiz."))
        return redirect('group_list', slug=center.slug) 

    if request.method == 'POST':
        form = GroupForm(request.POST, instance=group, request=request, teacher=user, center=center)
        
        if form.is_valid():
            group = form.save()
            students_to_add = form.cleaned_data.get('students')
            
            if students_to_add is not None:
                student_ids = [student.pk for student in students_to_add]
                
                # Center ID si NULL bo'lgan o'quvchilarni shu markazga biriktirish
                students_to_update = CustomUser.objects.filter(
                    pk__in=student_ids, 
                    center__isnull=True 
                )
                updated_count = students_to_update.update(center=center)
                
                if updated_count > 0:
                    messages.warning(request, _(f"Guruhga qo'shilgan {updated_count} ta o'quvchi avtomatik ravishda '{center.name}' markaziga biriktirildi."))
                
                group.students.set(students_to_add)
                
            messages.success(request, _(f"'{group.name}' guruhidagi o'zgarishlar saqlandi."))
            return redirect('group_list', slug=center.slug) 
            
    else:
        form = GroupForm(instance=group, request=request, teacher=user, center=center)

    context = {
        'form': form,
        'title': _(f"Guruhni Tahrirlash: {group.name}"),
        'center': center, # Shablon uchun center obyekti
        'is_create': False,
    }
    return render(request, 'management/group_form.html', context)

@login_required(login_url='login')
@user_passes_test(is_teacher, login_url='index')
def group_manage_students_view(request, slug, pk):
    """
    Berilgan slug'ga mos Center'dagi guruhga o'quvchilarni qo'shish/olib tashlash.
    """
    user = request.user
    
    # 1. Center obyektini slug orqali topish
    center = get_object_or_404(Center, slug=slug)
        
    if user.center != center:
         messages.error(request, _("Boshqa markaz guruhini boshqarishga ruxsat yo'q."))
         return redirect('dashboard',slug=request.user.center.slug)
        
    # 2. Guruhni topish
    group = get_object_or_404(Group, pk=pk, center=center)
    
    # Ruxsat tekshiruvi
    if user.role == 'teacher' and group.teacher != user:
        messages.error(request, _("Siz bu guruh o'quvchilarini boshqarish huquqiga ega emassiz."))
        return redirect('group_list', slug=center.slug) 

    # 1. O'CHIRISH MANTIQI (Jadvaldan O'chirish tugmasi)
    remove_student_id = request.GET.get('remove_student')
    if remove_student_id:
        try:
            student_to_remove = CustomUser.objects.get(pk=remove_student_id, role='student')
            if student_to_remove in group.students.all():
                group.students.remove(student_to_remove)
                messages.success(request, _(f"O'quvchi {student_to_remove.full_name} guruhdan olib tashlandi."))
            else:
                messages.error(request, _("O'quvchi guruhda mavjud emas."))
        except CustomUser.DoesNotExist:
            messages.error(request, _("O'quvchi topilmadi."))
            
        return redirect('group_manage_students', slug=group.center.slug, pk=group.pk)


    # 2. QO'SHISH MANTIQI (Yuqoridagi formadan)
    if request.method == 'POST':
        # AddStudentToGroupForm ni o'zingizning markaz filtriga moslab ishlatishingiz kerak
        add_form = AddStudentToGroupForm(request.POST) 
        
        if add_form.is_valid(): 
            students_to_add = add_form.cleaned_data.get('student_ids') 
            newly_added_count = 0
            
            for student in students_to_add:
                # Markazga biriktirish mantig'i (avvalgi koddagi kabi saqlanadi)
                if not student.center:
                    student.center = center
                    student.save(update_fields=['center'])
                    messages.warning(request, _(f"O'quvchi {student.full_name} avtomatik '{center.name}' markaziga biriktirildi."))
                
                # Guruhga qo'shish
                if student not in group.students.all():
                    group.students.add(student)
                    newly_added_count += 1
            
            if newly_added_count > 0:
                messages.success(request, _(f"{newly_added_count} ta o'quvchi '{group.name}' guruhiga qo'shildi."))
            else:
                messages.info(request, _("Tanlangan o'quvchilar allaqachon guruhda mavjud."))
                
            return redirect('group_manage_students', slug=group.center.slug, pk=group.pk)
            
    else:
        add_form = AddStudentToGroupForm()

    context = {
        'group': group,
        'center': center, # Shablon uchun center obyekti
        'students': group.students.all().order_by('full_name'),
        'title': _(f"Guruh O'quvchilari: {group.name}"),
        'add_form': add_form, 
    }
    return render(request, 'management/group_student_list.html', context)

@login_required(login_url='login')
@user_passes_test(is_teacher, login_url='index')
@require_POST 
def group_delete_view(request, slug, pk):
    """
    Berilgan slug'ga mos Center'dagi guruhni o'chirish.
    Ruxsat: Center Admin yoki Guruhning yaratuvchisi.
    """
    user = request.user
    
    # 1. Center obyektini slug orqali topish
    center = get_object_or_404(Center, slug=slug)
        
    if user.center != center:
         messages.error(request, _("Boshqa markaz guruhini o'chirishga ruxsat yo'q."))
         return redirect('dashboard',slug=request.user.center.slug)
        
    # 2. Guruhni topish
    group = get_object_or_404(Group, pk=pk, center=center)
    
    # Ruxsat tekshiruvi
    if user.role == 'teacher' and group.teacher != user:
        messages.error(request, _("Siz bu guruhni o'chirish huquqiga ega emassiz."))
        return redirect('group_list', slug=center.slug)
        
    group_name = group.name
    group.delete()
    messages.success(request, _(f"Guruh '{group_name}' muvaffaqiyatli o'chirildi."))
    return redirect('group_list', slug=center.slug)

@user_passes_test(is_teacher)
def search_students_ajax(request):
    """
    Bu view uchun slug kerak emas, chunki u faqat o'qituvchining joriy markazida (yoki markazsiz) studentlarni qidiradi.
    """
    user = request.user
    user_center = user.center # O'qituvchining joriy markazi

    if user.role not in ['teacher', 'center_admin']:
        return JsonResponse({'items': []}, status=403)
        
    query = request.GET.get('q', '')
    
    q_objects = Q(role='student') & Q(is_active=True)
    search_fields = Q(full_name__icontains=query) | Q(username__icontains=query) | Q(phone_number__icontains=query)

    # Filtr: Faqat joriy Center studentlari yoki hali biror markazga biriktirilmagan studentlar
    if user_center:
         q_objects &= (Q(center=user_center) | Q(center__isnull=True))
    
    # Agar user_center bo'lmasa, u holda faqat center__isnull=True bo'lganlarni ko'radi
    # Lekin yuqorida user_passes_test(is_teacher) ishlatilgani uchun, teacher markazsiz bo'lmasligi kerak (yoki is_teacher logikasi boshqacha)

    students = CustomUser.objects.filter(q_objects & search_fields).order_by('full_name')[:20]

    results = []
    for student in students:
        center_info = f"({student.center.name})" if student.center else " (Markazsiz)"
        
        results.append({
            'id': student.pk,
            'text': f"{student.full_name} ({student.username}){center_info}" 
        })

    return JsonResponse({'items': results, 'total_count': students.count()})