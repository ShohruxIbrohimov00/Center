from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse
from django.db.models import Sum, Count
from django.db import transaction
from django.utils import timezone
from django.template.loader import render_to_string
from django.contrib.contenttypes.models import ContentType
from django.core.files.storage import default_storage
from .models import CustomUser, Exam, ExamSection, ExamSectionStaticQuestion, ExamSectionTopicRule, ExamSectionSubtopicRule
from .models import UserAttempt, UserAttemptSection, UserAnswer, Subtopic, Topic, AnswerOption, Question, QuestionTranslation
from .models import AnswerOptionTranslation, QuestionSolution, Passage, Tag, Flashcard,ExamPackage ,SubscriptionPlan
from .forms import ExamForm, QuestionForm, TopicForm, SubtopicForm, ExamSectionForm, ExamSectionTopicRuleForm, ExamSectionSubtopicRuleForm
from .forms import PassageForm, FlashcardForm, AnswerOptionFormSet,PurchaseForm
from .utils import calculate_attempt_ability, get_adaptive_question
from bleach import clean
from django.urls import reverse
from django.db.models import Prefetch
from django.db.models import Q
import json
import logging
import hashlib
import hmac
import time

logger = logging.getLogger(__name__)

def is_teacher(user):
    return user.is_authenticated and user.role == 'teacher'

def is_student(user):
    return user.is_authenticated and user.role == 'student'

def verify_telegram_auth(data):
    """Telegram Login Widget dan kelgan ma'lumotlarni tasdiqlash."""
    received_hash = data.get('hash')
    auth_data = {k: v for k, v in data.items() if k != 'hash'}
    sorted_data = sorted(auth_data.items(), key=lambda x: x[0])
    data_check_string = '\n'.join(f'{k}={v}' for k, v in sorted_data)
    
    secret_key = hashlib.sha256(settings.TELEGRAM_BOT_TOKEN.encode()).digest()
    computed_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    
    if computed_hash != received_hash:
        return False, None
    
    auth_date = int(data.get('auth_date', 0))
    if time.time() - auth_date > 86400:
        return False, None
    
    return True, data

def create_or_update_user_from_telegram(telegram_data):
    """Telegram ma'lumotlari asosida foydalanuvchi yaratish yoki yangilash."""
    telegram_id = telegram_data.get('id')
    username = telegram_data.get('username', f"user_{telegram_id}")
    first_name = telegram_data.get('first_name', '')
    last_name = telegram_data.get('last_name', '')
    role = telegram_data.get('role', 'student')

    try:
        user = CustomUser.objects.get(telegram_id=telegram_id)
        user.username = username
        user.first_name = first_name
        user.last_name = last_name
        user.role = role
        user.is_approved = True if role == 'student' else False
        user.save()
    except CustomUser.DoesNotExist:
        user = CustomUser.objects.create_user(
            username=username,
            email=f"{telegram_id}@telegram.com",
            password=None,
            first_name=first_name,
            last_name=last_name,
            role=role,
            telegram_id=telegram_id,
            is_approved=True if role == 'student' else False
        )
    return user

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

def index(request):
    """Bosh sahifani ko'rsatadi."""
    if request.user.is_authenticated:
        if is_student(request.user):
            return redirect('tests')
        elif is_teacher(request.user):
            return redirect('my_exams')
    return render(request, 'index.html')

def telegram_login(request):
    """Telegram orqali tizimga kirish va ro'yxatdan o'tish."""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            is_valid, telegram_data = verify_telegram_auth(data)
            
            if not is_valid:
                return JsonResponse({'status': 'error', 'message': 'Telegram autentifikatsiyasi xato.'}, status=400)
            
            user = create_or_update_user_from_telegram(telegram_data)
            if user.is_approved:
                login(request, user, backend='django.contrib.auth.backends.ModelBackend')
                return JsonResponse({'status': 'success', 'redirect_url': '/tests/'})
            else:
                return JsonResponse({'status': 'error', 'message': 'Akkauntingiz hali tasdiqlanmagan.'}, status=403)
        except json.JSONDecodeError:
            return JsonResponse({'status': 'error', 'message': "Noto'g'ri ma'lumot formati."}, status=400)
        except Exception as e:
            logger.error(f"Telegram login xatosi: {e}")
            return JsonResponse({'status': 'error', 'message': f'Server xatosi: {str(e)}'}, status=500)
    
    return render(request, 'telegram_login.html')

def logout_view(request):
    """Tizimdan chiqish."""
    logout(request)
    messages.success(request, "Tizimdan muvaffaqiyatli chiqdingiz.")
    return redirect('telegram_login')

@login_required
def profile_view(request):
    if request.method == 'POST':
        user = request.user
        # ... (bu qism o'zgarishsiz qoladi)
        messages.success(request, "Profil muvaffaqiyatli yangilandi.")
        return redirect('profile')

    subscription = None
    if request.user.role == 'student':
        try:
            subscription = request.user.subscription
        except UserSubscription.DoesNotExist:
            subscription = None
    
    user_balance = None
    if request.user.role == 'student':
        try:
            user_balance = request.user.balance
        except UserBalance.DoesNotExist:
            user_balance = None

    context = {
        'subscription': subscription,
        'user_balance': user_balance,
    }
    return render(request, 'profile.html', context)

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
    return render(request, 'price.html', context)

# =================================================================
# YANGI VIEW: Xarid mantiqi
# =================================================================
@login_required
def process_purchase_view(request, purchase_type, item_id):
    if request.method == 'POST':
        form = PurchaseForm(request.POST)
        if form.is_valid():
            promo_code_str = form.cleaned_data.get('promo_code')
            
            # Tarif yoki paketni topish
            if purchase_type == 'package':
                item = get_object_or_404(ExamPackage, id=item_id)
                final_amount = item.price
            elif purchase_type == 'subscription':
                item = get_object_or_404(SubscriptionPlan, id=item_id)
                final_amount = item.price
            else:
                messages.error(request, "Noto'g'ri xarid turi.")
                return redirect('price')

            # Promo kodni qo'llash
            promo_code = None
            if promo_code_str:
                try:
                    promo_code = PromoCode.objects.get(code=promo_code_str, is_active=True)
                    if not promo_code.is_valid():
                        messages.error(request, "Ushbu promo kod amal qilmaydi yoki ishlatib bo'lingan.")
                        return redirect('price')
                    
                    if promo_code.discount_type == 'percentage':
                        discount = final_amount * (promo_code.discount_percent / 100)
                        final_amount -= discount
                    else: # 'fixed'
                        final_amount -= promo_code.discount_amount
                    
                    final_amount = max(0, final_amount) # Summa manfiy bo'lmasligi uchun

                except PromoCode.DoesNotExist:
                    messages.error(request, "Noto'g'ri promo kod.")
                    return redirect('price')

            # To'lov jarayonini boshlash (bu yerga to'lov tizimini integratsiya qilish kerak)
            # Hozircha bu shunchaki mantiqiy model
            
            purchase = Purchase.objects.create(
                user=request.user,
                purchase_type=purchase_type,
                package=item if purchase_type == 'package' else None,
                subscription_plan=item if purchase_type == 'subscription' else None,
                amount=item.price,
                promo_code=promo_code,
                final_amount=final_amount,
                status='pending' # To'lov kutilmoqda
            )
            
            # To'lov muvaffaqiyatli bo'lsa (bu qism keyinroq to'ldiriladi)
            # statusni 'completed'ga o'zgartiramiz
            purchase.status = 'completed'
            purchase.save()

            if promo_code:
                promo_code.used_count += 1
                promo_code.save()

            # Foydalanuvchi balansini yangilash
            if purchase_type == 'package':
                balance, created = UserBalance.objects.get_or_create(user=request.user)
                balance.exam_credits += item.exam_credits
                balance.solution_view_credits += item.solution_view_credits_on_purchase
                balance.save()
            
            elif purchase_type == 'subscription':
                # Avvalgi obunani tugatish
                try:
                    old_sub = UserSubscription.objects.get(user=request.user)
                    old_sub.delete()
                except UserSubscription.DoesNotExist:
                    pass

                # Yangi obunani yaratish
                UserSubscription.objects.create(
                    user=request.user,
                    plan=item,
                    start_date=timezone.now(),
                    end_date=timezone.now() + timezone.timedelta(days=item.duration_days)
                )

            messages.success(request, "Xaridingiz muvaffaqiyatli amalga oshirildi!")
            return redirect('profile')

    messages.error(request, "Xaridni amalga oshirishda xato yuz berdi.")
    return redirect('price')

@login_required(login_url='telegram_login')
def change_password(request):
    """Parolni o'zgartirish kerak emas, chunki Telegram autentifikatsiyasi ishlatiladi."""
    messages.info(request, "Telegram autentifikatsiyasi ishlatilmoqda, parol o'zgartirish kerak emas.")
    return redirect('profile')

@login_required(login_url='telegram_login')
def test_page(request, exam_id, attempt_id):
    """Test sahifasining asosiy shablonini yuklaydi."""
    exam = get_object_or_404(Exam, id=exam_id)
    attempt = get_object_or_404(UserAttempt, id=attempt_id, user=request.user, exam=exam)

    if attempt.is_completed:
        return redirect('view_result_detail', attempt_id=attempt.id)

    total_questions = 0
    sections = exam.sections.all().order_by('order')
    for section in sections:
        section_questions = get_section_questions(section, exam)
        total_questions += len(section_questions)

    if total_questions == 0:
        return redirect('view_result_detail', attempt_id=attempt.id)

    total_duration_seconds = sum(section.duration_minutes * 60 for section in sections if section.duration_minutes)
    time_remaining_seconds = 0
    if attempt.started_at:
        elapsed_seconds = (timezone.now() - attempt.started_at).total_seconds()
        time_remaining_seconds = max(0, int(total_duration_seconds - elapsed_seconds))
    else:
        attempt.started_at = timezone.now()
        attempt.save()
        time_remaining_seconds = total_duration_seconds

    section_attempts = attempt.section_attempts.all().order_by('section__order')
    first_section_attempt = section_attempts.first()
    answered_question_ids = set(UserAnswer.objects.filter(attempt_section=first_section_attempt).values_list('question_id', flat=True))
    first_question = get_adaptive_question(request.user, first_section_attempt, answered_question_ids)
    question_ids = [first_question.id] if first_question else []

    context = {
        'exam': exam,
        'attempt': attempt,
        'section_attempts': section_attempts,
        'total_questions': total_questions,
        'time_remaining_seconds': time_remaining_seconds,
        'question_ids': question_ids,
    }

    return render(request, 'test_page.html', context)

@login_required(login_url='telegram_login')
def handle_test_ajax(request):
    """AJAX so'rovlarini qayta ishlash: savol yuklash, javob saqlash, imtihon yakunlash."""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Noto‘g‘ri so‘rov usuli.'}, status=405)

    try:
        data = json.loads(request.body)
        action = data.get('action')
        attempt_id = data.get('attempt_id')
        section_attempt_id = data.get('section_attempt_id')
        attempt = get_object_or_404(UserAttempt, id=attempt_id, user=request.user)
        section_attempt = get_object_or_404(UserAttemptSection, id=section_attempt_id, attempt=attempt)
        exam = attempt.exam

        if action == 'get_initial_data':
            answered_question_ids = set(UserAnswer.objects.filter(attempt_section=section_attempt).values_list('question_id', flat=True))
            question = get_adaptive_question(request.user, section_attempt, answered_question_ids)
            if not question:
                return JsonResponse({
                    'status': 'success',
                    'question_ids': [],
                    'answered_question_ids': list(answered_question_ids),
                    'initial_question_data': None,
                })

            question_ids = [question.id]
            question_text = question.translations.filter(language='uz').first().text if question.translations.filter(language='uz').exists() else ""
            passage_text = question.passage.text if question.passage else None

            answered_option_ids = []
            answered_text = None
            try:
                user_answer = UserAnswer.objects.get(attempt_section=section_attempt, question=question)
                if question.answer_format in ['single', 'multiple']:
                    answered_option_ids = list(user_answer.selected_options.values_list('id', flat=True))
                elif question.answer_format == 'short_answer':
                    answered_text = user_answer.short_answer_text
            except UserAnswer.DoesNotExist:
                pass

            options_html = render_to_string(
                'question_options.html',
                {
                    'question': question,
                    'answered_option_ids': answered_option_ids,
                    'answered_text': answered_text,
                    'passage_text': passage_text,
                },
                request=request
            )

            return JsonResponse({
                'status': 'success',
                'question_ids': question_ids,
                'answered_question_ids': list(answered_question_ids),
                'initial_question_data': {
                    'id': question.id,
                    'question_text': question_text,
                    'passage_text': passage_text,
                    'question_image_url': question.image.url if question.image else None,
                    'question_format': question.answer_format,
                    'options_html': options_html,
                }
            })

        elif action == 'get_question':
            answered_question_ids = set(UserAnswer.objects.filter(attempt_section=section_attempt).values_list('question_id', flat=True))
            question = get_adaptive_question(request.user, section_attempt, answered_question_ids)
            if not question:
                return JsonResponse({'status': 'error', 'message': 'Mos savol topilmadi.'})

            question_text = question.translations.filter(language='uz').first().text if question.translations.filter(language='uz').exists() else ""
            passage_text = question.passage.text if question.passage else None

            answered_option_ids = []
            answered_text = None
            try:
                user_answer = UserAnswer.objects.get(attempt_section=section_attempt, question=question)
                if question.answer_format in ['single', 'multiple']:
                    answered_option_ids = list(user_answer.selected_options.values_list('id', flat=True))
                elif question.answer_format == 'short_answer':
                    answered_text = user_answer.short_answer_text
            except UserAnswer.DoesNotExist:
                pass

            options_html = render_to_string(
                'question_options.html',
                {
                    'question': question,
                    'answered_option_ids': answered_option_ids,
                    'answered_text': answered_text,
                    'passage_text': passage_text,
                },
                request=request
            )

            return JsonResponse({
                'status': 'success',
                'question_text': question_text,
                'passage_text': passage_text,
                'question_image_url': question.image.url if question.image else None,
                'question_id': question.id,
                'question_format': question.answer_format,
                'options_html': options_html,
                'answered_question_ids': list(answered_question_ids),
            })

        elif action == 'save_answer':
            question_id = data.get('question_id')
            question = get_object_or_404(Question, id=question_id)
            user_answer, created = UserAnswer.objects.get_or_create(
                attempt_section=section_attempt,
                question=question
            )

            correct_options = set(question.options.filter(is_correct=True).values_list('id', flat=True))
            user_answer.is_correct = None

            if question.answer_format == 'single':
                selected_option_id = data.get('selected_option')
                selected_option = AnswerOption.objects.filter(id=selected_option_id).first()
                user_answer.selected_options.set([selected_option] if selected_option else [])
                user_answer.short_answer_text = None
                user_answer.is_correct = selected_option_id in correct_options if selected_option else False
            elif question.answer_format == 'multiple':
                selected_option_ids = data.get('selected_options', [])
                selected_options = AnswerOption.objects.filter(id__in=selected_option_ids)
                user_answer.selected_options.set(selected_options)
                user_answer.short_answer_text = None
                user_answer.is_correct = set(selected_option_ids) == correct_options
            elif question.answer_format == 'short_answer':
                short_answer_text = data.get('short_answer_text')
                user_answer.short_answer_text = short_answer_text
                user_answer.selected_options.clear()
                user_answer.is_correct = None

            user_answer.time_taken_seconds = data.get('time_taken_seconds')
            user_answer.answered_at = timezone.now()
            user_answer.save()

            answered_question_ids = set(UserAnswer.objects.filter(attempt_section=section_attempt).values_list('question_id', flat=True))

            return JsonResponse({
                'status': 'success',
                'message': 'Javob saqlandi',
                'answered_question_ids': list(answered_question_ids),
            })

        elif action == 'finish_exam':
            with transaction.atomic():
                total_questions = 0
                correct_answers_count = 0
                total_score = 0

                for section_attempt in attempt.section_attempts.all():
                    section = section_attempt.section
                    section_questions = get_section_questions(section, exam)
                    section_total_questions = len(section_questions)
                    total_questions += section_total_questions

                    section_correct = sum(1 for answer in section_attempt.user_answers.all() if answer.is_correct)
                    section_score = (section_correct / section_total_questions * 800) if section_total_questions > 0 else 0
                    section_attempt.score = section_score
                    section_attempt.correct_answers_count = section_correct
                    section_attempt.incorrect_answers_count = section_total_questions - section_correct
                    section_attempt.completed_at = timezone.now()
                    section_attempt.ability_estimate = calculate_attempt_ability(attempt.id, section_attempt.id)
                    section_attempt.save()

                    correct_answers_count += section_correct
                    total_score += section_score

                attempt.final_total_score = total_score
                attempt.final_ebrw_score = sum(sa.score for sa in attempt.section_attempts.filter(section__section_type__in=['reading', 'writing']))
                attempt.final_math_score = sum(sa.score for sa in attempt.section_attempts.filter(section__section_type__in=['math_no_calc', 'math_calc']))
                attempt.is_completed = True
                attempt.completed_at = timezone.now()
                attempt.save()

            return JsonResponse({
                'status': 'finished',
                'redirect_url': redirect('view_result_detail', attempt_id=attempt.id).url
            })

        else:
            return JsonResponse({'status': 'error', 'message': 'Noma‘lum harakat.'}, status=400)

    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': "Noto'g'ri JSON formati."}, status=400)
    except Exception as e:
        logger.error(f"handle_test_ajax xatosi: {e}")
        return JsonResponse({'status': 'error', 'message': f'Server xatosi: {str(e)}'}, status=500)

@login_required(login_url='telegram_login')
def get_question(request):
    """AJAX orqali adaptiv savolni qaytaradi."""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Noto‘g‘ri so‘rov usuli.'}, status=405)

    try:
        data = json.loads(request.body)
        section_attempt_id = data.get('section_attempt_id')
        attempt_id = data.get('attempt_id')
        attempt = get_object_or_404(UserAttempt, id=attempt_id, user=request.user)
        section_attempt = get_object_or_404(UserAttemptSection, id=section_attempt_id, attempt=attempt)

        answered_question_ids = set(UserAnswer.objects.filter(attempt_section=section_attempt).values_list('question_id', flat=True))
        question = get_adaptive_question(request.user, section_attempt, answered_question_ids)
        if not question:
            return JsonResponse({'status': 'error', 'message': 'Mos savol topilmadi.'})

        question_text = question.translations.filter(language='uz').first().text if question.translations.filter(language='uz').exists() else ""
        passage_text = question.passage.text if question.passage else None

        answered_option_ids = []
        answered_text = None
        try:
            user_answer = UserAnswer.objects.get(attempt_section=section_attempt, question=question)
            if question.answer_format in ['single', 'multiple']:
                answered_option_ids = list(user_answer.selected_options.values_list('id', flat=True))
            elif question.answer_format == 'short_answer':
                answered_text = user_answer.short_answer_text
        except UserAnswer.DoesNotExist:
            pass

        options_html = render_to_string(
            'question_options.html',
            {
                'question': question,
                'answered_option_ids': answered_option_ids,
                'answered_text': answered_text,
                'passage_text': passage_text,
            },
            request=request
        )

        return JsonResponse({
            'status': 'success',
            'question_text': question_text,
            'passage_text': passage_text,
            'question_image_url': question.image.url if question.image else None,
            'question_id': question.id,
            'question_format': question.answer_format,
            'options_html': options_html,
            'answered_question_ids': list(answered_question_ids),
        })
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': "Noto'g'ri JSON formati."}, status=400)
    except Exception as e:
        logger.error(f"get_question AJAX xatosi: {e}")
        return JsonResponse({'status': 'error', 'message': f'Server xatosi: {str(e)}'}, status=500)

@login_required(login_url='telegram_login')
def start_exam(request, exam_id):
    """Imtihonni boshlash va UserAttemptSection larni yaratish."""
    exam = get_object_or_404(Exam, id=exam_id, is_active=True)
    if not is_student(request.user):
        messages.error(request, "Sizda bu imtihonni boshlash huquqi yo'q.")
        return redirect('index')

    if exam.is_premium and not request.user.has_active_subscription():
        messages.error(request, "Bu imtihon pullik. Iltimos, obuna sotib oling.")
        return redirect('tests')

    attempt, created = UserAttempt.objects.get_or_create(
        user=request.user,
        exam=exam,
        is_completed=False,
        defaults={'started_at': timezone.now()}
    )

    for section in exam.sections.all():
        UserAttemptSection.objects.get_or_create(
            attempt=attempt,
            section=section,
            defaults={'started_at': timezone.now()}
        )

    return redirect('test_page', exam_id=exam.id, attempt_id=attempt.id)

@login_required(login_url='telegram_login')
def student_results(request):
    """Talabaning imtihon natijalarini ko'rish."""
    if not is_student(request.user):
        messages.error(request, "Sizda bu sahifaga kirish huquqi yo'q.")
        return redirect('index')

    results = UserAttempt.objects.filter(user=request.user, is_completed=True).order_by('-completed_at')
    for result in results:
        total_questions = 0
        for section in result.exam.sections.all():
            section_questions = get_section_questions(section, result.exam)
            total_questions += len(section_questions)
        result.total_questions = total_questions
        result.percentage = (result.correct_answers_count / total_questions * 100) if total_questions > 0 else 0
        result.ability_estimate = calculate_attempt_ability(result.id)
    context = {'results': results}
    return render(request, 'student_result.html', context)

@login_required(login_url='telegram_login')
def view_result_detail(request, attempt_id):
    """Imtihon natijalarining batafsil ko'rinishi."""
    attempt = get_object_or_404(UserAttempt, id=attempt_id, user=request.user)
    total_correct_answers = 0
    total_questions = 0

    for section_attempt in attempt.section_attempts.all():
        section = section_attempt.section
        section_questions = get_section_questions(section, attempt.exam)
        total_questions += len(section_questions)
        total_correct_answers += section_attempt.correct_answers_count

    user_answers = UserAnswer.objects.filter(attempt_section__attempt=attempt).order_by('question__id')

    for user_answer in user_answers:
        options_with_status = []
        correct_options = set(user_answer.question.options.filter(is_correct=True).values_list('id', flat=True))
        selected_option_ids = set(user_answer.selected_options.values_list('id', flat=True))
        for option in user_answer.question.options.all():
            options_with_status.append({
                'option': option,
                'is_user_selected': option.id in selected_option_ids,
                'is_correct': option.id in correct_options,
            })
        user_answer.options_with_status = options_with_status
        user_answer.passage_text = user_answer.question.passage.text if user_answer.question.passage else None
        user_answer.is_solution_free = user_answer.question.is_solution_free

    context = {
        'attempt': attempt,
        'user_answers': user_answers,
        'total_correct_answers': total_correct_answers,
        'total_incorrect_answers': total_questions - total_correct_answers,
        'ability_estimate': attempt.ability_estimate,
    }
    return render(request, 'result_detail.html', context)

@login_required(login_url='telegram_login')
@user_passes_test(is_teacher, login_url='index')
def teacher_view_result_detail(request, attempt_id):
    """O'qituvchi uchun talaba natijasining batafsil ko'rinishi."""
    attempt = get_object_or_404(UserAttempt, id=attempt_id)
    if attempt.exam.teacher != request.user:
        return render(request, '403.html', {'message': "Siz bu natijani ko'rish huquqiga ega emassiz."})

    total_questions = 0
    total_correct_answers = 0
    for section_attempt in attempt.section_attempts.all():
        section = section_attempt.section
        section_questions = get_section_questions(section, attempt.exam)
        total_questions += len(section_questions)
        total_correct_answers += section_attempt.correct_answers_count

    user_answers = UserAnswer.objects.filter(attempt_section__attempt=attempt).order_by('question__id').select_related('question').prefetch_related('selected_options', 'question__options')

    for user_answer in user_answers:
        options_with_status = []
        correct_options = set(user_answer.question.options.filter(is_correct=True).values_list('id', flat=True))
        selected_option_ids = set(user_answer.selected_options.values_list('id', flat=True))
        for option in user_answer.question.options.all():
            options_with_status.append({
                'option': option,
                'is_user_selected': option.id in selected_option_ids,
                'is_correct': option.id in correct_options,
            })
        user_answer.options_with_status = options_with_status
        user_answer.passage_text = user_answer.question.passage.text if user_answer.question.passage else None
        user_answer.is_solution_free = user_answer.question.is_solution_free

    context = {
        'attempt': attempt,
        'user_answers': user_answers,
        'total_correct_answers': total_correct_answers,
        'total_incorrect_answers': total_questions - total_correct_answers,
        'ability_estimate': attempt.ability_estimate,
    }
    return render(request, 'teacher_test_result_detail.html', context)

@login_required(login_url='telegram_login')
def tests(request):
    """Talaba uchun mavjud imtihonlar ro'yxati."""
    if not is_student(request.user):
        messages.error(request, "Sizda bu sahifaga kirish huquqi yo'q.")
        return redirect('index')

    exams = Exam.objects.filter(is_active=True).annotate(
        total_questions=Sum('sections__max_questions'),
        total_duration=Sum('sections__duration_minutes')
    ).order_by('-created_at')
    context = {'exams': exams}
    return render(request, 'tests.html', context)

@login_required(login_url='telegram_login')
@user_passes_test(is_teacher, login_url='index')
def my_exams(request):
    """Ustozning o'z yaratgan imtihonlarini ko'rish va boshqarish."""
    # Har bir imtihon uchun bo'limlar sonini hisoblash
    my_exams = Exam.objects.filter(teacher=request.user).annotate(
        section_count=Count('sections')
    ).order_by('-created_at')
    
    context = {'my_exams': my_exams}
    return render(request, 'exam/my_exams.html', context) 

@login_required(login_url='telegram_login')
@user_passes_test(is_teacher, login_url='index')
def create_static_exam_step1(request):
    """Statik imtihon yaratishning 1-bosqichi: asosiy ma'lumotlarni kiritish."""
    if request.method == 'POST':
        form = ExamForm(request.POST)
        if form.is_valid():
            exam_data = form.cleaned_data
            
            # Imtihon obyektini bazaga saqlash
            new_exam = Exam.objects.create(
                teacher=request.user,
                title=exam_data['title'],
                description=exam_data.get('description'),
                is_premium=exam_data['is_premium'],
                exam_type='static' # Statik deb belgilaymiz
            )
            
            messages.success(request, "Imtihon ma'lumotlari saqlandi. Endi bo'limlarni yaratishingiz mumkin.")
            
            # Yangi yaratilgan exam_id bilan 2-bosqichga yo'naltirish
            return redirect(reverse('create_static_exam_step2', args=[new_exam.id]))
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{form.fields[field].label}: {error}")
    else:
        # GET so'rovida sessiyadan ma'lumot olib, formaga o'tiramiz
        initial_data = request.session.get('exam_data', {})
        form = ExamForm(initial=initial_data)

    context = {
        'form': form,
    }
    return render(request, 'exam/static_exam_create_step1.html', context)

@login_required
@user_passes_test(is_teacher, login_url='index')
def create_static_exam_step2(request, exam_id):
    exam = get_object_or_404(Exam, id=exam_id, teacher=request.user)

    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            action = data.get('action')
            
            # Bo'limlarni saqlash
            if action == 'save_sections':
                sections_data = data.get('sections', [])
                if not sections_data:
                    return JsonResponse({'status': 'error', 'message': "Hech bo'lmaganda bitta bo'lim qo'shing."}, status=400)
                request.session[f'exam_{exam_id}_sections'] = sections_data
                request.session.modified = True
                return JsonResponse({'status': 'success', 'message': "Bo'limlar muvaffaqiyatli saqlandi."})

            # Bo'limni o'chirish
            elif action == 'remove_section':
                index_to_remove = data.get('index')
                sections_data = request.session.get(f'exam_{exam_id}_sections', [])
                
                if not isinstance(index_to_remove, int) or index_to_remove < 0 or index_to_remove >= len(sections_data):
                    return JsonResponse({'status': 'error', 'message': "Noto'g'ri bo'lim indeksi."}, status=400)
                
                del sections_data[index_to_remove]
                request.session[f'exam_{exam_id}_sections'] = sections_data
                request.session.modified = True
                return JsonResponse({'status': 'success', 'message': "Bo'lim muvaffaqiyatli o'chirildi."})

            # Jami savollar sonini olish
            elif action == 'get_total_questions':
                sections_data = request.session.get(f'exam_{exam_id}_sections', [])
                total_questions = sum(len(s.get('static_questions', {})) for s in sections_data)
                return JsonResponse({'status': 'success', 'count': total_questions})

            # Imtihonni yakunlash
            elif action == 'finalize_exam':
                sections_data = request.session.get(f'exam_{exam_id}_sections', [])
                if not sections_data:
                    return JsonResponse({'status': 'error', 'message': "Imtihonni yakunlash uchun hech bo'lmaganda bitta bo'lim bo'lishi kerak."}, status=400)
                
                total_questions = sum(len(s.get('static_questions', {})) for s in sections_data)
                if total_questions == 0:
                    return JsonResponse({'status': 'error', 'message': "Imtihonni yakunlash uchun hech bo'lmaganda bitta savol bo'lishi kerak."}, status=400)
                
                with transaction.atomic():
                    exam.sections.all().delete()
                    
                    for section_data in sections_data:
                        section_questions = section_data.get('static_questions', {})
                        if not section_questions:
                            messages.error(request, "Bo'sh bo'limni saqlab bo'lmaydi.")
                            return JsonResponse({'status': 'error', 'message': "Bo'sh bo'limni saqlab bo'lmaydi."}, status=400)

                        section_form = ExamSectionForm(data={
                            'section_type': section_data.get('section_type'),
                            'duration_minutes': section_data.get('duration_minutes'),
                            'max_questions': section_data.get('max_questions'),
                            'module_number': section_data.get('module_number', 1),
                            'order': section_data.get('order')
                        }, exam_type='static')
                        
                        if not section_form.is_valid():
                            return JsonResponse({'status': 'error', 'message': section_form.errors.as_json()}, status=400)

                        new_section = ExamSection.objects.create(
                            exam=exam,
                            section_type=section_form.cleaned_data['section_type'],
                            duration_minutes=section_form.cleaned_data['duration_minutes'],
                            max_questions=section_form.cleaned_data['max_questions'],
                            module_number=section_form.cleaned_data['module_number'],
                            order=section_form.cleaned_data['order']
                        )

                        for question_id, order in section_questions.items():
                            try:
                                question = Question.objects.get(id=question_id)
                                ExamSectionStaticQuestion.objects.create(
                                    exam_section=new_section,
                                    question=question,
                                    question_number=order
                                )
                            except Question.DoesNotExist:
                                return JsonResponse({'status': 'error', 'message': f"Savol ID {question_id} topilmadi."}, status=404)
                    
                    if f'exam_{exam_id}_sections' in request.session:
                        del request.session[f'exam_{exam_id}_sections']
                    
                    messages.success(request, "Imtihon muvaffaqiyatli yaratildi!")
                    return JsonResponse({'status': 'success', 'redirect_url': reverse('exam_detail', args=[exam.id])})
            
            # Savolni bo'limga qo'shish
            elif action == 'add_question':
                section_index_str = data.get('section_index')
                question_id = data.get('question_id')
                
                if section_index_str is None or question_id is None:
                    return JsonResponse({'status': 'error', 'message': "Bo'lim indeksi yoki savol ID topilmadi."}, status=400)
                
                try:
                    section_index = int(section_index_str)
                except (ValueError, TypeError):
                    return JsonResponse({'status': 'error', 'message': "Yaroqsiz bo'lim indeksi."}, status=400)

                sections_data = request.session.get(f'exam_{exam_id}_sections', [])
                if 0 <= section_index < len(sections_data):
                    section = sections_data[section_index]
                    static_questions = section.get('static_questions', {})
                    
                    if str(question_id) in static_questions:
                        return JsonResponse({'status': 'error', 'message': "Bu savol allaqachon qo'shilgan."}, status=400)
                    
                    question_count = len(static_questions) + 1
                    static_questions[str(question_id)] = question_count
                    section['static_questions'] = static_questions
                    request.session[f'exam_{exam_id}_sections'] = sections_data
                    request.session.modified = True
                    
                    return JsonResponse({'status': 'success', 'message': "Savol muvaffaqiyatli qo'shildi."})
                
                return JsonResponse({'status': 'error', 'message': "Bo'lim topilmadi."}, status=404)

            return JsonResponse({'status': 'error', 'message': "Noto'g'ri so'rov aksiyasi."}, status=400)
        
        except json.JSONDecodeError:
            return HttpResponseBadRequest("Yaroqsiz JSON ma'lumoti")
    
    sections_data = request.session.get(f'exam_{exam_id}_sections', [])
    
    for section in sections_data:
        section['static_questions_json'] = json.dumps(section.get('static_questions', {}))
    
    total_questions = sum(len(s.get('static_questions', {})) for s in sections_data)
    
    context = {
        'exam_title': exam.title,
        'sections_data': sections_data,
        'total_questions': total_questions,
        'exam_id': exam.id
    }
    
    return render(request, 'exam/static_exam_create_step2.html', context)

@login_required
@user_passes_test(is_teacher, login_url='index')
def exam_detail(request, pk):
    """
    Imtihon tafsilotlari, bo'limlari va har bir bo'limdagi savollar sonini ko'rsatadi.
    """
    exam = get_object_or_404(Exam, pk=pk, teacher=request.user)
    sections = ExamSection.objects.filter(exam=exam).order_by('order')
    sections_with_question_count = [
        {
            'section': section,
            'question_count': ExamSectionStaticQuestion.objects.filter(exam_section=section).count()
        }
        for section in sections
    ]

    context = {
        'exam': exam,
        'sections_with_question_count': sections_with_question_count
    }
    return render(request, 'exam/exam_detail.html', context)

@login_required
@user_passes_test(is_teacher, login_url='index')
def delete_section(request, section_id):
    """
    Imtihon bo'limini o'chirish.
    """
    section = get_object_or_404(ExamSection, pk=section_id, exam__teacher=request.user)
    exam_id = section.exam.id

    if request.method == 'POST':
        try:
            data = None
            if request.body:
                data = json.loads(request.body)
            
            if data and data.get('action') == 'delete_section':
                with transaction.atomic():
                    section.delete()
                    # Bo'limlar tartibini qayta hisoblash
                    remaining_sections = ExamSection.objects.filter(exam_id=exam_id).order_by('order')
                    for index, sec in enumerate(remaining_sections, 1):
                        sec.order = index
                        sec.save()
                return JsonResponse({
                    'status': 'success',
                    'message': "Bo'lim muvaffaqiyatli o'chirildi!",
                    'redirect_url': reverse('exam_detail', kwargs={'pk': exam_id})
                })

            # Standart POST so'rovi
            with transaction.atomic():
                section.delete()
                # Bo'limlar tartibini qayta hisoblash
                remaining_sections = ExamSection.objects.filter(exam_id=exam_id).order_by('order')
                for index, sec in enumerate(remaining_sections, 1):
                    sec.order = index
                    sec.save()
            messages.success(request, "Bo'lim muvaffaqiyatli o'chirildi!")
            return redirect('exam_detail', pk=exam_id)

        except json.JSONDecodeError:
            messages.error(request, "Yaroqsiz JSON ma'lumoti.")
            return HttpResponseBadRequest("Yaroqsiz JSON ma'lumoti")
        except Exception as e:
            messages.error(request, f"Bo'limni o'chirishda xato yuz berdi: {str(e)}")
            return JsonResponse({'status': 'error', 'message': f"Bo'limni o'chirishda xato: {str(e)}"}, status=500)

    # GET so'rovi
    context = {
        'section': section,
        'exam': section.exam
    }
    return render(request, 'exam/delete_section.html', context)

@login_required
@user_passes_test(is_teacher, login_url='index')
def edit_section(request, section_id):
    section = get_object_or_404(ExamSection, pk=section_id, exam__teacher=request.user)
    exam_type = section.exam.exam_type

    if request.method == 'POST':
        try:
            data = json.loads(request.body) if request.body else None
            if data:
                action = data.get('action')

                # Bo'lim ma'lumotlarini saqlash
                if action == 'save_section_data':
                    section_data = data.get('section_data', {})
                    form = ExamSectionForm({
                        'section_type': section_data.get('section_type'),
                        'duration_minutes': section_data.get('duration_minutes'),
                        'max_questions': section_data.get('max_questions'),
                        'module_number': section_data.get('module_number'),
                        'order': section.order
                    }, instance=section, exam_type=exam_type)

                    if not form.is_valid():
                        return JsonResponse({'status': 'error', 'message': form.errors.as_json()}, status=400)

                    with transaction.atomic():
                        form.save()
                        section.static_questions.clear()  # ManyToManyField uchun clear() ishlatiladi
                        for question_id, order in section_data.get('static_questions', {}).items():
                            try:
                                question = Question.objects.get(id=question_id)
                                ExamSectionStaticQuestion.objects.create(
                                    exam_section=section,
                                    question=question,
                                    question_number=order
                                )
                            except Question.DoesNotExist:
                                return JsonResponse({'status': 'error', 'message': f"Savol ID {question_id} topilmadi."}, status=404)
                    
                    return JsonResponse({'status': 'success', 'message': "Bo'lim muvaffaqiyatli saqlandi."})

                # Savolni o'chirish
                elif action == 'remove_question':
                    question_id = data.get('question_id')
                    try:
                        question = Question.objects.get(id=question_id)
                        ExamSectionStaticQuestion.objects.filter(exam_section=section, question=question).delete()
                        remaining_questions = ExamSectionStaticQuestion.objects.filter(exam_section=section).order_by('question_number')
                        with transaction.atomic():
                            for index, q in enumerate(remaining_questions, 1):
                                q.question_number = index
                                q.save()
                        return JsonResponse({'status': 'success', 'message': "Savol muvaffaqiyatli o'chirildi."})
                    except Question.DoesNotExist:
                        return JsonResponse({'status': 'error', 'message': f"Savol ID {question_id} topilmadi."}, status=404)

                return JsonResponse({'status': 'error', 'message': "Noto'g'ri so'rov aksiyasi."}, status=400)

            # Formani saqlash (standart POST so'rovi)
            form = ExamSectionForm(request.POST, instance=section, exam_type=exam_type)
            if form.is_valid():
                form.save()
                messages.success(request, "Bo'lim muvaffaqiyatli tahrirlandi!")
                return redirect('exam_detail', section.exam.id)
            else:
                return JsonResponse({'status': 'error', 'message': form.errors.as_json()}, status=400)

        except json.JSONDecodeError:
            return HttpResponseBadRequest("Yaroqsiz JSON ma'lumoti")

    # GET so'rovi
    form = ExamSectionForm(instance=section, exam_type=exam_type)
    static_questions = {str(q.question.id): q.question_number for q in ExamSectionStaticQuestion.objects.filter(exam_section=section)}
    section.static_questions_dict = static_questions
    section.static_questions_json = json.dumps(static_questions)

    context = {
        'form': form,
        'section': section,
        'section_index': section.order - 1,
        'exam': section.exam,
        'section_type_choices': ExamSection.SECTION_TYPES
    }
    return render(request, 'exam/edit_section.html', context)

def select_topic_for_exam(request):
    section_index = request.GET.get('section_index', 'new')
    topics = Topic.objects.filter(teacher=request.user).annotate(questions_count=Count('subtopics__questions'))
    uncategorized_count = Question.objects.filter(author=request.user, subtopic__isnull=True).count()
    
    context = {
        'topics': topics,
        'uncategorized_count': uncategorized_count,
        'section_index': section_index,
    }
    return render(request, 'exam/select_topic_for_exam.html', context)

@login_required(login_url='telegram_login')
@user_passes_test(is_teacher, login_url='index')
def questions_by_topic_for_exam(request, topic_id):
    """Mavzu bo'yicha savollarni tanlash view'i."""
    section_index = request.GET.get('section_index')
    
    topic = get_object_or_404(Topic, id=topic_id)
    questions = Question.objects.filter(author=request.user, subtopic__topic=topic).prefetch_related('translations')
    topic_name = topic.name
    
    sections_data = request.session.get('exam_sections', [])
    selected_questions = {}
    if section_index is not None:
        try:
            index = int(section_index)
            if 0 <= index < len(sections_data):
                selected_questions = sections_data[index].get('static_questions', {})
        except (ValueError, IndexError):
            pass

    context = {
        'questions': questions,
        'topic_name': topic_name,
        'selected_questions': selected_questions,
        'section_index': section_index,
    }
    return render(request, 'exam/questions_by_topic_for_exam.html', context)

@login_required(login_url='telegram_login')
@user_passes_test(is_teacher, login_url='index')
def create_adaptive_exam_step1(request):
    """Adaptiv imtihon yaratishning 1-bosqichi: asosiy ma'lumotlarni kiritish."""
    if request.method == 'POST':
        form = ExamForm(request.POST)
        if form.is_valid():
            request.session['exam_data'] = form.cleaned_data
            request.session['exam_type'] = 'adaptive'
            messages.success(request, "Imtihon ma'lumotlari saqlandi. Endi bo'lim va mavzu qoidalarini belgilashingiz mumkin.")
            return redirect('create_adaptive_exam_step2')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{form.fields[field].label}: {error}")
    else:
        initial_data = request.session.get('exam_data', {})
        form = ExamForm(initial=initial_data)

    context = {
        'form': form,
    }
    return render(request, 'exam/adaptive_exam_create_step1.html', context)

@login_required(login_url='telegram_login')
@user_passes_test(is_teacher, login_url='index')
def create_adaptive_exam_step2(request):
    """Adaptiv imtihon yaratishning 2-bosqichi: bo'limlar va qoidalarni belgilash."""
    if not request.session.get('exam_data') or request.session.get('exam_type') != 'adaptive':
        messages.error(request, "Iltimos, avval imtihon ma'lumotlarini kiriting.")
        return redirect('create_adaptive_exam_step1')

    exam_title = request.session.get('exam_data').get('title', 'Nomsiz imtihon')
    
    # AJAX POST so'rovlarini qabul qilish
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            action = data.get('action')

            # Bo'lim qoidalarini saqlash
            if action == 'save_rules':
                request.session['adaptive_sections_rules'] = data.get('sections', [])
                request.session.modified = True
                return JsonResponse({'status': 'success', 'message': "Qoidalar saqlandi."})
            
            # Imtihonni yakunlash
            elif action == 'finalize_exam':
                # ... (bu yerda sizning avvalgi finalize_exam kodingiz)
                try:
                    with transaction.atomic():
                        exam = Exam.objects.create(
                            teacher=request.user,
                            exam_type='adaptive',
                            **request.session['exam_data']
                        )
                        sections_data = request.session.get('adaptive_sections_rules', [])
                        for section_data in sections_data:
                            section = ExamSection.objects.create(
                                exam=exam,
                                section_type=section_data['section_type'],
                                duration_minutes=section_data['duration_minutes'],
                                max_questions=section_data['max_questions'],
                                module_number=section_data['module_number'],
                                order=section_data['order'],
                                min_difficulty=section_data.get('min_difficulty'),
                                max_difficulty=section_data.get('max_difficulty'),
                            )
                            for topic_data in section_data.get('topic_rules', []):
                                topic_rule = ExamSectionTopicRule.objects.create(
                                    exam_section=section,
                                    topic_id=topic_data['topic_id'],
                                    questions_count=topic_data['questions_count']
                                )
                                for subtopic_data in topic_data.get('subtopic_rules', []):
                                    ExamSectionSubtopicRule.objects.create(
                                        topic_rule=topic_rule,
                                        subtopic_id=subtopic_data['subtopic_id'],
                                        questions_count=subtopic_data['questions_count']
                                    )
                    request.session.pop('exam_data', None)
                    request.session.pop('exam_type', None)
                    request.session.pop('adaptive_sections_rules', None)
                    messages.success(request, "Adaptiv imtihon muvaffaqiyatli yaratildi! ✅")
                    return JsonResponse({'status': 'success', 'redirect_url': '/teacher/my_exams/'})
                
                except (KeyError, json.JSONDecodeError) as e:
                    return JsonResponse({'status': 'error', 'message': f"Ma'lumotlar yetarli emas: {e}"}, status=400)
            
            return JsonResponse({'status': 'error', 'message': 'Noto\'g\'ri so\'rov turi.'}, status=400)

        except json.JSONDecodeError:
            return JsonResponse({'status': 'error', 'message': "Noto'g'ri ma'lumot formati."}, status=400)
    
    # GET so'rovi uchun kontekst
    sections_rules = request.session.get('adaptive_sections_rules', [])
    topics = Topic.objects.filter(teacher=request.user).annotate(subtopics_count=Count('subtopics'))

    context = {
        'exam_title': exam_title,
        'sections_rules': sections_rules,
        'topics': topics
    }
    return render(request, 'exam/adaptive_exam_create_step2.html', context)

@login_required(login_url='telegram_login')
@user_passes_test(is_teacher, login_url='index')
def questions_by_topic_for_exam(request, topic_id):
    """Mavzu bo'yicha savollarni imtihon uchun tanlash."""
    section_index = request.GET.get('section_index')
    
    # Faqat mavzuga tegishli savollarni qidirish
    topic = get_object_or_404(Topic, id=topic_id, teacher=request.user)
    questions = Question.objects.filter(author=request.user, subtopic__topic=topic).prefetch_related('translations', 'passage', 'tags')
    topic_name = topic.name
    
    sections_data = request.session.get('exam_sections', [])
    selected_questions = {}
    if section_index is not None:
        try:
            index = int(section_index)
            if 0 <= index < len(sections_data):
                selected_questions = sections_data[index].get('static_questions', {})
        except (ValueError, IndexError):
            pass
    
    context = {
        'questions': questions,
        'topic_name': topic_name,
        'selected_questions': selected_questions,
        'section_index': section_index,
    }
    return render(request, 'exam/questions_by_topic_for_exam.html', context)

@login_required(login_url='telegram_login')
@user_passes_test(is_teacher, login_url='index')
def delete_section(request, section_id):
    """Bo'limni o'chirish."""
    section = get_object_or_404(ExamSection, id=section_id, exam__teacher=request.user)
    if request.method == 'POST':
        section.delete()
        return JsonResponse({'status': 'success', 'message': 'Bo\'lim o\'chirildi.'})
    return JsonResponse({'status': 'error', 'message': 'Faqat POST so\'rovlari qabul qilinadi.'}, status=400)

@login_required(login_url='telegram_login')
@user_passes_test(is_teacher, login_url='index')
def remove_question_from_section(request, section_id, question_id):
    """Bo'limdan savolni o'chirish."""
    section = get_object_or_404(ExamSection, id=section_id, exam__teacher=request.user)
    static_question = get_object_or_404(ExamSectionStaticQuestion, exam_section=section, question_id=question_id)
    if request.method == 'POST':
        static_question.delete()
        return JsonResponse({'status': 'success', 'message': 'Savol o\'chirildi.'})
    return JsonResponse({'status': 'error', 'message': 'Faqat POST so\'rovlari qabul qilinadi.'}, status=400)

@login_required(login_url='telegram_login')
@user_passes_test(is_teacher, login_url='index')
def exam_topics_list(request,exam_id):
    """
    Imtihon uchun savol tanlashda barcha mavzular ro'yxatini ko'rsatadi.
    """
    exam = get_object_or_404(Exam, id=exam_id, teacher=request.user)
    topics = Topic.objects.filter(teacher=request.user).annotate(subtopic_count=Count('subtopics'))
    uncategorized_questions_count = Question.objects.filter(author=request.user, subtopic__isnull=True).count()
    
    context = {
        'topics': topics,
        'uncategorized_questions_count': uncategorized_questions_count,
        'section_index': request.GET.get('section_index'), 
        'exam_id': exam_id,
    }
    return render(request, 'exam/exam_topics_list.html', context)

@login_required(login_url='telegram_login')
@user_passes_test(is_teacher, login_url='index')
def exam_subtopic_list(request, exam_id, topic_id):
    """
    Berilgan mavzu (topic) ichidagi ichki mavzular (subtopics) ro'yxatini ko'rsatadi.
    """
    topic = get_object_or_404(Topic, id=topic_id, teacher=request.user)
    subtopics = Subtopic.objects.filter(topic=topic).annotate(question_count=Count('questions'))
    
    context = {
        'topic': topic,
        'subtopics': subtopics,
        'section_index': request.GET.get('section_index'),
        'exam_id': exam_id,  # <--- exam_id ni kontekstga qo'shamiz
    }
    return render(request, 'exam/exam_subtopic_list.html', context)

@login_required(login_url='telegram_login')
@user_passes_test(is_teacher, login_url='index')
def exam_subtopic_questions(request, exam_id, subtopic_id):
    """
    Berilgan ichki mavzuga (subtopic) tegishli savollar ro'yxatini to'liq formatda ko'rsatadi.
    """
    subtopic = get_object_or_404(Subtopic, id=subtopic_id, topic__teacher=request.user)
    
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
        'section_index': request.GET.get('section_index'),
        'exam_id': exam_id, 
    }
    return render(request, 'exam/exam_subtopic_questions.html', context)

@login_required(login_url='telegram_login')
@user_passes_test(is_teacher, login_url='index')
def exam_uncategorized_questions(request, exam_id):
    """
    Mavzulanmagan savollar ro'yxatini ko'rsatadi.
    """
    questions = Question.objects.filter(subtopic__isnull=True, author=request.user)
    
    context = {
        'questions': questions,
        'uncategorized_view': True,
        'section_index': request.GET.get('section_index'),
        'exam_id': exam_id, # <--- exam_id ni bu yerda ham kontekstga qo'shamiz
    }
    return render(request, 'exam/exam_uncategorized_questions.html', context)

@login_required(login_url='telegram_login')
@user_passes_test(is_teacher, login_url='index')
def edit_exam(request, exam_id):
    """Mavjud imtihonni tahrirlash."""
    exam = get_object_or_404(Exam, id=exam_id, teacher=request.user)
    if request.method == 'POST':
        exam_form = ExamForm(request.POST, instance=exam)
        if exam_form.is_valid():
            exam_form.save()
            messages.success(request, "Imtihon ma'lumotlari muvaffaqiyatli tahrirlandi! ✅")
            return redirect('my_exams')
        else:
            for field, errors in exam_form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
    else:
        exam_form = ExamForm(instance=exam)
    
    sections = ExamSection.objects.filter(exam=exam).order_by('order')
    topics = Topic.objects.filter(teacher=request.user).annotate(questions_count=Count('subtopics__questions'))
    uncategorized_count = Question.objects.filter(author=request.user, subtopic__isnull=True).count()
    
    context = {
        'exam_form': exam_form,
        'exam': exam,
        'sections': sections,
        'topics': topics,
        'uncategorized_count': uncategorized_count,
    }
    return render(request, 'edit_exam.html', context)

@login_required(login_url='telegram_login')
@user_passes_test(is_teacher, login_url='index')
def delete_exam(request, exam_id):
    """Imtihonni o'chirish."""
    exam = get_object_or_404(Exam, id=exam_id, teacher=request.user)
    if request.method == 'POST':
        exam.delete()
        messages.success(request, f"'{exam.title}' imtihoni o'chirildi! ✅")
        return redirect('my_exams')
    return redirect('my_exams')

@login_required(login_url='telegram_login')
@user_passes_test(is_teacher, login_url='index')
def teacher_results(request):
    """Ustozning imtihonlari va talabalar natijalarini ko'rish."""
    my_exams = Exam.objects.filter(teacher=request.user).order_by('-created_at')
    exam_results = []
    
    for exam in my_exams:
        attempts = UserAttempt.objects.filter(exam=exam).order_by('-completed_at')
        attempt_details = []
        
        for attempt in attempts:
            total_questions = sum(len(get_section_questions(section, exam)) for section in exam.sections.all())
            correct_answers = sum(section.correct_answers_count for section in attempt.section_attempts.all())
            incorrect_answers = total_questions - correct_answers
            
            percentage = (correct_answers / total_questions * 100) if total_questions > 0 else 0
            
            attempt_details.append({
                'attempt_id': attempt.id,
                'user_username': attempt.user.username,
                'correct_answers': correct_answers,
                'incorrect_answers': incorrect_answers,
                'score': attempt.final_total_score,
                'percentage': round(percentage, 2),
                'completed_at': attempt.completed_at,
            })
        
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

@login_required(login_url='telegram_login')
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

@login_required(login_url='telegram_login')
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

@login_required(login_url='telegram_login')
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

@login_required(login_url='telegram_login')
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

# --- Mavzu o'chirish view'i (alohida sahifa) ---
@login_required(login_url='telegram_login')
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

# --- Ichki mavzuni o'chirish view'i (alohida sahifa) ---
@login_required(login_url='telegram_login')
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

@login_required(login_url='telegram_login')
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

@login_required(login_url='telegram_login')
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

@login_required(login_url='telegram_login')
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

@login_required(login_url='telegram_login')
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

@login_required(login_url='telegram_login')
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

@login_required(login_url='telegram_login')
@user_passes_test(is_teacher, login_url='index')
def list_flashcards(request):
    """Barcha flashcardlarni ko'rsatish. Foydalanuvchi tomonidan filterlash shart emas."""
    flashcards = Flashcard.objects.all().order_by('-created_at')
    return render(request, 'flashcards/list_flashcards.html', {'flashcards': flashcards})

@login_required(login_url='telegram_login')
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

@login_required(login_url='telegram_login')
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

@login_required(login_url='telegram_login')
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

@login_required(login_url='telegram_login')
@user_passes_test(is_teacher, login_url='index')
def add_question(request):
    # Sizning avvalgi add_question funksiyangiz joyida qoladi
    # ... (bu qism o'zgarishsiz) ...
    if request.method == 'POST':
        form = QuestionForm(request.POST, request.FILES)
        answer_format = request.POST.get('answer_format')

        if form.is_valid():
            with transaction.atomic():
                question = form.save(commit=False)
                question.author = request.user
                
                if answer_format == 'short_answer':
                    question.correct_short_answer = request.POST.get('correct_short_answer')
                else:
                    question.correct_short_answer = None
                
                question.save()
                form.save_m2m() # Tags va Flashcards uchun
                
                if answer_format in ['single', 'multiple']:
                    option_texts = request.POST.getlist('option_text')
                    correct_indices = request.POST.getlist('is_correct')
                    
                    for i, option_text in enumerate(option_texts):
                        is_correct = str(i + 1) in correct_indices
                        if option_text.strip():
                            AnswerOption.objects.create(
                                question=question,
                                text=option_text,
                                is_correct=is_correct
                            )

                hint = request.POST.get('hint')
                detailed_solution = request.POST.get('detailed_solution')
                
                if hint or detailed_solution:
                    QuestionSolution.objects.create(
                        question=question,
                        hint=hint,
                        detailed_solution=detailed_solution
                    )

            messages.success(request, "Savol muvaffaqiyatli qo'shildi!")
            if 'save_and_add_another' in request.POST:
                return redirect('add_question')
            else:
                return redirect('my_questions')
        else:
            messages.error(request, "Savolni qo'shishda xatolik yuz berdi. Iltimos, formadagi xatolarni tekshiring.")
            
    else:
        form = QuestionForm()

    context = {
        'form': form,
    }
    return render(request, 'questions/add_questions.html', context)

@login_required(login_url='telegram_login')
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
                
                if answer_format == 'short_answer':
                    question.correct_short_answer = request.POST.get('correct_short_answer')
                else:
                    question.correct_short_answer = None
                    
                question.save()
                form.save_m2m()

                # Javob variantlarini o'chirish va qayta yaratish
                if answer_format in ['single', 'multiple']:
                    # Bu qatorni o'zgartiring: answer_options -> options
                    question.options.all().delete() 
                    
                    option_texts = request.POST.getlist('option_text')
                    correct_indices = request.POST.getlist('is_correct')
                    
                    for i, option_text in enumerate(option_texts):
                        is_correct = str(i + 1) in correct_indices
                        if option_text.strip():
                            AnswerOption.objects.create(
                                question=question,
                                text=option_text,
                                is_correct=is_correct
                            )
                
                # Yechimni yangilash yoki yaratish
                hint = request.POST.get('hint')
                detailed_solution = request.POST.get('detailed_solution')
                
                solution, created = QuestionSolution.objects.get_or_create(question=question)
                solution.hint = hint
                solution.detailed_solution = detailed_solution
                solution.save()

            messages.success(request, "Savol muvaffaqiyatli yangilandi!")
            return redirect('my_questions')
        else:
            messages.error(request, "Savolni yangilashda xatolik yuz berdi. Iltimos, formadagi xatolarni tekshiring.")
    else:
        form = QuestionForm(instance=question, initial=initial_data)
    
    context = {
        'form': form,
        'question': question
    }
    return render(request, 'questions/edit_question.html', context)

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

@login_required(login_url='telegram_login')
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

@login_required(login_url='telegram_login')
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

