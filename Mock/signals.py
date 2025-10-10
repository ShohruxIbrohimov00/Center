import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from django.db import transaction # transaction.atomic() uchun qo'shildi
from .models import (
    UserAttempt, ExamScoring, UserMissionProgress, Badge, UserBadge,
    Notification, LeaderboardEntry, UserAnswer, Purchase, UserSubscription,
    UserBalance, CustomUser # FlashcardExamAttempt olib tashlandi
)
from utils.irt import ThreeParameterLogisticModel

logger = logging.getLogger(__name__)

@receiver(post_save, sender=UserAttempt)
def score_attempt(sender, instance, **kwargs):
    """
    UserAttempt yakunlangandan so'ng (is_completed=True) uning ballarini hisoblaydi
    va ExamScoring ob'ektini yaratadi.
    """
    if instance.is_completed and not hasattr(instance, 'scoring'):
        sections = instance.section_attempts.all()
        
        # Ba'zi hollarda sections 1 dan kam bo'lishi mumkin, shuning uchun tekshirish kerak
        if len(sections) < 2:
            logger.error(f"UserAttempt #{instance.id} da yetarli bo'limlar (sections) topilmadi. Ball hisoblanmadi.")
            return

        module1_answers = UserAnswer.objects.filter(attempt_section=sections[0])
        module2_answers = UserAnswer.objects.filter(attempt_section=sections[1])
        
        # Modul qiyinliklarini hisoblash
        module1_difficulty = sum(q.question.difficulty for q in module1_answers) / module1_answers.count() if module1_answers else 0.0
        module2_difficulty = sum(q.question.difficulty for q in module2_answers) / module2_answers.count() if module2_answers else 0.0
        
        # ExamScoring yaratish
        scoring = ExamScoring.objects.create(
            attempt=instance,
            math_ability=0.0,  # Dastlab 0, keyin calculate_scores() orqali hisoblanadi
            ebrw_ability=0.0,
            module1_difficulty=module1_difficulty,
            module2_difficulty=module2_difficulty
        )
        # ExamScoring modelidagi maxsus method orqali ballar hisoblanadi
        scoring.calculate_scores()

# Signal: UserAttempt yakunlanganda progress va leaderboardni yangilash (exam mode)
@receiver(post_save, sender=UserAttempt)
def update_exam_progress_and_leaderboard(sender, instance, **kwargs):
    """
    UserAttempt yakunlanganda foydalanuvchining umumiy progressini va
    haftalik Leaderboard reytinglarini yangilaydi.
    """
    if instance.is_completed:
        progress, created = UserMissionProgress.objects.get_or_create(user=instance.user)
        progress.exam_attempts_completed += 1
        
        # Eng yuqori ballni yangilash
        if instance.final_total_score > progress.highest_score:
            progress.highest_score = instance.final_total_score
        progress.save()
        
        # Leaderboard yangilash (effort - urinishlar soni)
        current_week = timezone.now().isocalendar()[1]
        effort_entry, _ = LeaderboardEntry.objects.get_or_create(
            user=instance.user,
            leaderboard_type='effort',
            week_number=current_week,
            defaults={'score': 0}
        )
        effort_entry.score += 1  # Har bir exam attempt uchun +1
        effort_entry.save()
        
        # Leaderboard yangilash (performance - ball)
        if instance.final_total_score >= 600:
            perf_entry, _ = LeaderboardEntry.objects.get_or_create(
                user=instance.user,
                leaderboard_type='performance',
                week_number=current_week,
                defaults={'score': 0}
            )
            if instance.final_total_score > perf_entry.score:
                perf_entry.score = instance.final_total_score
            perf_entry.save()
        
        # Nishonlarni tekshirish va berish
        check_and_award_attempt_badges(instance.user, progress)
        check_and_award_score_badges(instance.user, instance.final_total_score)

# Yordamchi funksiya: Attempt-based nishonlarni tekshirish va berish
def check_and_award_attempt_badges(user, progress):
    """
    Exam va Study urinishlar soniga asoslangan nishonlarni (badge) tekshiradi va beradi.
    """
    # Exam + study urinishlar soniga asoslangan darajalar (kamida 10 ta holat)
    levels = [
        (1, 'Starter', '1 ta exam mode va 1 ta study mode yakunlangan!'),
        (3, 'Explorer', '3 ta exam mode va 3 ta study mode yakunlangan!'),
        (5, 'Achiever', '5 ta exam mode va 5 ta study mode yakunlangan!'),
        (10, 'Master', '10 ta exam mode va 10 ta study mode yakunlangan!'),
        (20, 'Expert', '20 ta exam mode va 20 ta study mode yakunlangan!'),
        (50, 'Legend', '50 ta exam mode va 50 ta study mode yakunlangan!'),
        (100, 'Titan', '100 ta exam mode va 100 ta study mode yakunlangan!'),
        (200, 'Immortal', '150 ta exam mode va 150 ta study mode yakunlangan!'),
        (500, 'Ultimate', '200 ta exam mode va 200 ta study mode yakunlangan!'),
    ]
    
    for min_count, title, desc in levels:
        # Eslatma: 'study_attempts_completed' hali ham progress ob'ektida mavjud deb taxmin qilindi.
        # Agar bu progress ham o'chirilgan bo'lsa, faqat exam_attempts_completed qoladi.
        if progress.exam_attempts_completed >= min_count and progress.study_attempts_completed >= min_count:
            # Badge mavjudligini tekshirish (Badge modelida trigger_type='exam_completed' deb taxmin qilamiz)
            badge = Badge.objects.filter(title=title, trigger_type='exam_completed').first()
            if badge and not UserBadge.objects.filter(user=user, badge=badge).exists():
                UserBadge.objects.create(user=user, badge=badge)
                # Xabarnoma yuborish
                send_notification(
                    user,
                    f"Tabriklayman, siz {title} unvonini oldingiz!",
                    f"{desc} Bu hali boshlanishi, sizni hali yanada mukammal rag'batlar yutuqlar kutib turibdi. Yutuqlar sahifasiga o'ting: /achievements/"
                )

# Yordamchi funksiya: Ball-based nishonlarni tekshirish va berish
def check_and_award_score_badges(user, score):
    """
    Eng yuqori erishilgan ballga asoslangan nishonlarni (badge) tekshiradi va beradi.
    """
    # Ball darajalar (600+ va undan yuqori)
    score_levels = [
        (600, '600+'),
        (650, '650+'),
        (700, '700+'),
        (710, '710+'),
        (720, '720+'),
        (730, '730+'),
        (740, '740+'),
        (750, '750+'),
        (760, '760+'),
        (770, '770+'),
        (780, '780+'),
        (790, '790+'),
        (800, '800'),
    ]
    
    for min_score, title in score_levels:
        if score >= min_score:
            # Badge mavjudligini tekshirish (Badge modelida trigger_type='score_achieved' va min_score mos bo'lsa)
            badge = Badge.objects.filter(title=title, trigger_type='score_achieved', min_score=min_score).first()
            if badge and not UserBadge.objects.filter(user=user, badge=badge).exists():
                UserBadge.objects.create(user=user, badge=badge)
                # Xabarnoma yuborish
                send_notification(
                    user,
                    f"Tabriklayman, siz {title} dovonidan o'tdingiz!",
                    "Bu ajoyib natija! Yutuqlar sahifasiga o'ting: /achievements/"
                )

# Yordamchi funksiya: Xabarnoma yuborish
def send_notification(user, title, message):
    """Notification ob'ektini yaratadi."""
    Notification.objects.create(
        user=user,
        title=title,
        message=message,
        is_read=False
    )

@receiver(post_save, sender=Purchase)
def update_user_balance_and_subscription(sender, instance, created, **kwargs):
    """
    Purchase modeli saqlanganda, foydalanuvchi balansi yoki obunasini yangilaydi.
    """
    if instance.status == 'completed':
        # Bir vaqtda bir nechta yozuvlarni yangilash uchun transaction ishlatildi
        with transaction.atomic():
            # UserBalance ni olish yoki yaratish
            user_balance, _ = UserBalance.objects.get_or_create(user=instance.user)

            if instance.purchase_type == 'package' and instance.package:
                # ExamPackage sotib olinganda kreditlar qo'shish
                user_balance.exam_credits += instance.package.exam_credits
                user_balance.solution_view_credits += instance.package.solution_view_credits
                user_balance.save()
                logger.info(
                    f"User {instance.user.username} purchased package {instance.package.name}. "
                    f"Added {instance.package.exam_credits} exam credits and "
                    f"{instance.package.solution_view_credits} solution credits."
                )

            elif instance.purchase_type == 'subscription' and instance.subscription_plan:
                # SubscriptionPlan sotib olinganda obunani yangilash
                end_date = timezone.now() + timezone.timedelta(days=instance.subscription_plan.duration_days)
                user_subscription, created = UserSubscription.objects.get_or_create(
                    user=instance.user,
                    defaults={
                        'plan': instance.subscription_plan,
                        'start_date': timezone.now(),
                        'end_date': end_date,
                        'auto_renewal': False
                    }
                )
                if not created:
                    # Agar obuna mavjud bo'lsa, muddatni uzaytirish
                    user_subscription.plan = instance.subscription_plan
                    # Muddat tugash sanasiga qo'shish
                    if user_subscription.end_date > timezone.now():
                        user_subscription.end_date += timezone.timedelta(days=instance.subscription_plan.duration_days)
                    else:
                         user_subscription.end_date = end_date
                    user_subscription.auto_renewal = False
                    user_subscription.save()
                logger.info(
                    f"User {instance.user.username} purchased subscription {instance.subscription_plan.name}. "
                    f"Subscription active until {user_subscription.end_date}."
                )

            # PromoCode ishlatilgan bo'lsa, used_count ni yangilash
            if instance.promo_code and instance.promo_code.is_valid():
                instance.promo_code.used_count += 1
                if instance.promo_code.used_count >= instance.promo_code.max_uses:
                    instance.promo_code.is_active = False
                instance.promo_code.save()
                logger.info(
                    f"Promo code {instance.promo_code.code} used by {instance.user.username}. "
                    f"Current uses: {instance.promo_code.used_count}/{instance.promo_code.max_uses}"
                )

@receiver(post_save, sender=UserAnswer)
def update_question_calibration(sender, instance, created, **kwargs):
    """
    Har javobdan keyin savolning response_count'ini yangilaydi.
    30 javobdan keyin IRT orqali kalibrlaydi.
    """
    if created:
        question = instance.question
        question.response_count += 1
        question.save()

        if question.response_count >= 30 and not question.is_calibrated:
            user_answers = UserAnswer.objects.filter(question=question)
            
            # Kalibrlash uchun zarur bo'lgan ma'lumotlarni tayyorlash
            # (Bu qism ThreeParameterLogisticModel modeliga bog'liq, uni o'zgartirmadim)
            
            try:
                irt_model = ThreeParameterLogisticModel()
                # Eslatma: ThreeParameterLogisticModel() ning estimate_difficulty() metodi
                # user_answers querysetidan to'g'ri ishlashi uchun u model ichida 
                # (masalan, to'g'ri/noto'g'ri javoblarni yig'ish orqali) 
                # moslashtirilgan bo'lishi kerak.
                
                new_difficulty = irt_model.estimate_difficulty(user_answers)
                
                question.difficulty = new_difficulty
                question.is_calibrated = True
                question.save()
                logger.info(f"Savol #{question.id} kalibrlandi: difficulty={new_difficulty}")
            except Exception as e:
                # Agar IRT hisobida xato bo'lsa, logga yozish
                logger.error(f"Savol #{question.id} kalibrlashda xato: {str(e)}")
