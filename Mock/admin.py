from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin
from django.utils.translation import gettext_lazy as _
from django.utils.safestring import mark_safe
from django.utils import timezone
from bleach import clean
from django.contrib.contenttypes.admin import GenericTabularInline

# Siz yuborgan barcha modellarni import qilish
from .models import (
    SystemConfiguration, SiteSettings, CustomUser, PromoCode, ExamPackage, SubscriptionPlan, UserBalance,
    UserSubscription, Purchase, Tag, Topic, Subtopic, Passage, RaschDifficultyLevel,
    Question, QuestionTranslation, QuestionSolution, AnswerOption, AnswerOptionTranslation,
    QuestionReview, Exam, ExamSection, ExamSectionStaticQuestion, ExamSectionTopicRule,
    ExamSectionSubtopicRule, ExamSectionTagRule, UserAttempt, UserAttemptSection, UserAnswer,
    UserSolutionView, Flashcard, UserFlashcardStatus, UserFlashcardDeck, FlashcardExam, 
    Notification, Badge, UserBadge, UserAnswerArchive, UserTagPerformance,
    LiveExam, LiveExamRegistration, LeaderboardEntry, UserMissionProgress,
    FlashcardReviewLog
)

# =================================================================
# 1. TIZIM VA FOYDALANUVCHI BOSHQARUVI
# =================================================================

@admin.register(SystemConfiguration)
class SystemConfigurationAdmin(admin.ModelAdmin):
    list_display = ('question_calibration_threshold', 'solutions_enabled', 'default_solutions_are_free')
    fieldsets = (
        (None, {'fields': ('question_calibration_threshold', 'solutions_enabled', 'default_solutions_are_free')}),
    )

    def has_add_permission(self, request):
        return False if self.model.objects.count() > 0 else super().has_add_permission(request)

    def has_delete_permission(self, request, obj=None):
        return False

@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    list_display = ('payment_card_holder', 'payment_card_number', 'manager_phone_number')

    def has_add_permission(self, request):
        return not self.model.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    # Endi 'ability' va 'teacher' maydonlarini yana qaytarib qo'shamiz
    list_display = ('username', 'email', 'first_name', 'last_name', 'role', 'ability', 'teacher', 'is_staff')
    
    fieldsets = UserAdmin.fieldsets + (
        ('Qo\'shimcha ma\'lumotlar', {'fields': ('role', 'phone_number', 'ability', 'teacher', 'profile_picture', 'bio', 'is_banned')}),
    )
    
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Qo\'shimcha ma\'lumotlar', {'fields': ('first_name', 'last_name', 'role', 'phone_number', 'teacher')}),
    )
    
    # teacher maydoni uchun qulay qidiruvni yoqamiz
    raw_id_fields = ('teacher',)

# =================================================================
# 2. TIJORAT MODELLARI
# =================================================================

@admin.register(PromoCode)
class PromoCodeAdmin(admin.ModelAdmin):
    list_display = ('code', 'discount_type', 'discount_percent', 'discount_amount', 'is_active', 'valid_until', 'used_count', 'max_uses')
    list_filter = ('discount_type', 'is_active')
    search_fields = ('code',)
    date_hierarchy = 'valid_until'
    readonly_fields = ('used_count',)

@admin.register(ExamPackage)
class ExamPackageAdmin(admin.ModelAdmin):
    list_display = ('name', 'price', 'exam_credits', 'solution_view_credits_on_purchase', 'includes_flashcards', 'is_active')
    list_filter = ('is_active', 'includes_flashcards')
    search_fields = ('name', 'description')
    filter_horizontal = ('exams',)

@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = ('name', 'price', 'duration_days', 'includes_solution_access', 'includes_flashcards', 'is_active')
    list_filter = ('is_active', 'includes_solution_access', 'includes_flashcards')
    search_fields = ('name', 'description')

@admin.register(UserBalance)
class UserBalanceAdmin(admin.ModelAdmin):
    list_display = ('user', 'exam_credits', 'solution_view_credits', 'updated_at')
    search_fields = ('user__username', 'user__email')
    list_filter = ('updated_at',)
    readonly_fields = ('updated_at',)
    raw_id_fields = ('user',)

@admin.register(UserSubscription)
class UserSubscriptionAdmin(admin.ModelAdmin):
    list_display = ('user', 'plan', 'start_date', 'end_date', 'is_active', 'auto_renewal')
    list_filter = ('auto_renewal', 'plan')
    search_fields = ('user__username', 'plan__name')
    date_hierarchy = 'end_date'
    raw_id_fields = ('user', 'plan')


@admin.register(Purchase)
class PurchaseAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'purchase_type', 'item_name', 'final_amount', 'status', 'created_at', 'view_screenshot')
    list_filter = ('status', 'purchase_type', 'created_at')
    search_fields = ('user__username', 'id')
    list_editable = ('status',)
    list_per_page = 20
    date_hierarchy = 'created_at'
    ordering = ('-created_at',)
    
    # O'ZGARISH BU YERDA: 'item_name' readonly_fields ro'yxatiga qo'shildi
    readonly_fields = (
        'user', 'purchase_type', 'package', 'subscription_plan', 'amount', 
        'promo_code', 'final_amount', 'created_at', 'updated_at', 
        'view_screenshot_in_form', 'item_name'
    )
    
    actions = ['approve_selected_purchases', 'reject_selected_purchases']
    
    fieldsets = (
        ('Umumiy Ma\'lumot', {'fields': ('user', 'status', 'purchase_type', 'item_name', 'final_amount')}),
        ('Skrinshot va Izoh', {'fields': ('view_screenshot_in_form', 'payment_comment')}),
        ('Vaqt Belgilari', {'fields': ('created_at', 'updated_at')}),
    )

    def item_name(self, obj):
        if obj.package: return obj.package.name
        if obj.subscription_plan: return obj.subscription_plan.name
        return "Noma'lum"
    item_name.short_description = "Mahsulot"

    def view_screenshot(self, obj):
        if obj.payment_screenshot:
            return mark_safe(f'<a href="{obj.payment_screenshot.url}" target="_blank">Ko\'rish</a>')
        return "Yuklanmagan"
    view_screenshot.short_description = "Skrinshot"

    def view_screenshot_in_form(self, obj):
        if obj.payment_screenshot:
            return mark_safe(f'<a href="{obj.payment_screenshot.url}" target="_blank"><img src="{obj.payment_screenshot.url}" width="300" /></a>')
        return "Yuklanmagan"
    view_screenshot_in_form.short_description = "Yuklangan Skrinshot"

    @admin.action(description="Tanlangan to'lovlarni TASDIQLASH")
    def approve_selected_purchases(self, request, queryset):
        approved_count = 0
        for purchase in queryset.filter(status='moderation'):
            try:
                purchase.fulfill()
                approved_count += 1
            except Exception as e:
                self.message_user(request, f"Xarid #{purchase.id} ni tasdiqlashda xato: {e}", messages.ERROR)
        if approved_count > 0:
            self.message_user(request, f"{approved_count} ta to'lov muvaffaqiyatli tasdiqlandi.", messages.SUCCESS)

    @admin.action(description="Tanlangan to'lovlarni RAD ETISH")
    def reject_selected_purchases(self, request, queryset):
        queryset.update(status='rejected')
        self.message_user(request, f"{queryset.count()} ta to'lov rad etildi.", messages.WARNING)


# =================================================================
# 3. KONTENT MODELLARI (TAG, TOPIC, QUESTION)
# =================================================================

@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ('name', 'parent', 'get_full_hierarchy', 'created_at')
    search_fields = ('name', 'description')
    list_filter = ('parent',)
    list_select_related = ('parent',)

@admin.register(UserTagPerformance)
class UserTagPerformanceAdmin(admin.ModelAdmin):
    list_display = ('user', 'tag', 'success_rate', 'correct_answers', 'incorrect_answers', 'get_average_time_per_question', 'last_attempted_at')
    list_filter = ('tag', 'last_attempted_at')
    search_fields = ('user__username', 'tag__name')
    readonly_fields = ('success_rate', 'last_attempted_at', 'total_time_spent', 'attempts_count')
    raw_id_fields = ('user', 'tag')

    def get_average_time_per_question(self, obj):
        return obj.total_time_spent / obj.attempts_count if obj.attempts_count > 0 else 0
    get_average_time_per_question.short_description = "O'rtacha vaqt/savol (soniya)"

@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    list_display = ('name', 'teacher', 'order')
    list_filter = ('teacher',)
    search_fields = ('name',)
    list_editable = ('order',)
    raw_id_fields = ('teacher',)

@admin.register(Subtopic)
class SubtopicAdmin(admin.ModelAdmin):
    list_display = ('name', 'topic', 'order')
    list_filter = ('topic', 'topic__teacher')
    search_fields = ('name', 'topic__name')
    list_editable = ('order',)
    raw_id_fields = ('topic',)

@admin.register(Passage)
class PassageAdmin(admin.ModelAdmin):
    list_display = ('title', 'author', 'created_at')
    search_fields = ('title', 'content')
    list_filter = ('author',)
    date_hierarchy = 'created_at'
    raw_id_fields = ('author',)

@admin.register(RaschDifficultyLevel)
class RaschDifficultyLevelAdmin(admin.ModelAdmin):
    list_display = ('name', 'min_difficulty', 'max_difficulty')
    search_fields = ('name',)
    ordering = ['min_difficulty']

class QuestionTranslationInline(admin.TabularInline):
    model = QuestionTranslation
    extra = 1
    fields = ('language', 'text')

class AnswerOptionInline(admin.TabularInline):
    model = AnswerOption
    extra = 4
    fields = ('text', 'is_correct')

class QuestionSolutionInline(admin.TabularInline):
    model = QuestionSolution
    extra = 1
    fields = ('hint', 'detailed_solution')

class AnswerOptionTranslationInline(admin.TabularInline):
    model = AnswerOptionTranslation
    extra = 1
    fields = ('language', 'text')

@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('id', 'get_text_preview', 'subtopic', 'author', 'answer_format', 'difficulty', 'is_calibrated', 'status', 'is_solution_free', 'created_at')
    list_filter = ('answer_format', 'status', 'is_calibrated', 'is_solution_free', 'subtopic__topic', 'difficulty_level')
    search_fields = ('text', 'tags__name', 'correct_short_answer')
    inlines = [QuestionTranslationInline, AnswerOptionInline, QuestionSolutionInline]
    date_hierarchy = 'created_at'
    filter_horizontal = ('tags', 'flashcards')
    raw_id_fields = ('passage', 'subtopic', 'author', 'parent_question')
    fieldsets = (
        (None, {'fields': ('text', 'image', 'passage', 'subtopic', 'tags', 'flashcards', 'answer_format', 'correct_short_answer', 'author')}),
        (_('Difficulty Parameters'), {'fields': ('difficulty', 'discrimination', 'guessing', 'difficulty_level', 'is_calibrated', 'response_count')}),
        (_('Status'), {'fields': ('status', 'is_solution_free', 'parent_question', 'version')}),
        (_('Dates'), {'fields': ('created_at', 'updated_at'), 'classes': ('collapse',)}),
    )
    readonly_fields = ('response_count', 'version', 'created_at', 'updated_at')

    def get_text_preview(self, obj):
        cleaned_text = clean(str(obj.text), tags=[], strip=True)
        return mark_safe(cleaned_text[:100] + '...' if len(cleaned_text) > 100 else cleaned_text)
    get_text_preview.short_description = 'Savol matni (preview)'

@admin.register(QuestionSolution)
class QuestionSolutionAdmin(admin.ModelAdmin):
    list_display = ('question', 'get_hint_preview', 'get_detailed_solution_preview')
    search_fields = ('question__text', 'hint', 'detailed_solution')
    raw_id_fields = ('question',)

    def get_hint_preview(self, obj):
        cleaned_hint = clean(str(obj.hint or ''), tags=[], strip=True)
        return cleaned_hint[:50] + '...' if cleaned_hint and len(cleaned_hint) > 50 else cleaned_hint
    get_hint_preview.short_description = 'Hint (preview)'

    def get_detailed_solution_preview(self, obj):
        cleaned_solution = clean(str(obj.detailed_solution or ''), tags=[], strip=True)
        return cleaned_solution[:50] + '...' if cleaned_solution and len(cleaned_solution) > 50 else cleaned_solution
    get_detailed_solution_preview.short_description = 'Detailed Solution (preview)'

@admin.register(AnswerOption)
class AnswerOptionAdmin(admin.ModelAdmin):
    list_display = ('get_text_preview', 'question', 'is_correct')
    list_filter = ('is_correct', 'question__answer_format')
    search_fields = ('text', 'question__text')
    inlines = [AnswerOptionTranslationInline]
    raw_id_fields = ('question',)

    def get_text_preview(self, obj):
        cleaned_text = clean(str(obj.text), tags=[], strip=True)
        return cleaned_text[:70] + '...' if len(cleaned_text) > 70 else cleaned_text
    get_text_preview.short_description = 'Variant matni (preview)'

@admin.register(QuestionReview)
class QuestionReviewAdmin(admin.ModelAdmin):
    list_display = ('question', 'user', 'status', 'created_at', 'get_comment_preview')
    list_filter = ('status', 'question__subtopic__topic')
    search_fields = ('comment', 'question__text', 'user__username')
    date_hierarchy = 'created_at'
    raw_id_fields = ('question', 'user')

    def get_comment_preview(self, obj):
        return obj.comment[:50] + '...' if len(obj.comment) > 50 else obj.comment
    get_comment_preview.short_description = 'Izoh (preview)'

# =================================================================
# 4. IMTIHON MODELLARI
# =================================================================

class ExamSectionTopicRuleInline(admin.TabularInline):
    model = ExamSectionTopicRule
    extra = 1
    fields = ('topic', 'questions_count')
    raw_id_fields = ('topic',)

class ExamSectionSubtopicRuleInline(admin.TabularInline):
    model = ExamSectionSubtopicRule
    extra = 1
    fields = ('subtopic', 'questions_count')
    raw_id_fields = ('subtopic',)

class ExamSectionTagRuleInline(admin.TabularInline):
    model = ExamSectionTagRule
    extra = 1
    fields = ('tag', 'questions_count')
    raw_id_fields = ('tag',)

class ExamSectionStaticQuestionInline(admin.TabularInline):
    model = ExamSectionStaticQuestion
    extra = 1
    fields = ('question', 'question_number')
    raw_id_fields = ('question',)

class ExamSectionInline(admin.TabularInline):
    model = ExamSection
    extra = 2
    fields = ('section_type', 'duration_minutes', 'max_questions', 'module_number', 'order', 'min_difficulty', 'max_difficulty')

@admin.register(Exam)
class ExamAdmin(admin.ModelAdmin):
    list_display = ('title', 'teacher', 'exam_type', 'is_premium', 'is_active', 'created_at')
    list_filter = ('exam_type', 'is_premium', 'is_active')
    search_fields = ('title', 'description')
    inlines = [ExamSectionInline]
    date_hierarchy = 'created_at'
    raw_id_fields = ('teacher',)
    fieldsets = (
        (None, {'fields': ('teacher', 'title', 'description', 'exam_type')}),
        (_('Settings'), {'fields': ('is_premium', 'is_active')}),
        (_('Dates'), {'fields': ('created_at',), 'classes': ('collapse',)}),
    )
    readonly_fields = ('created_at',)

@admin.register(ExamSection)
class ExamSectionAdmin(admin.ModelAdmin):
    list_display = ('exam', 'section_type', 'module_number', 'duration_minutes', 'max_questions', 'order', 'min_difficulty', 'max_difficulty')
    list_filter = ('section_type', 'exam__exam_type', 'module_number')
    search_fields = ('exam__title', 'section_type')
    inlines = [ExamSectionTopicRuleInline, ExamSectionTagRuleInline, ExamSectionStaticQuestionInline]
    raw_id_fields = ('exam',)

@admin.register(ExamSectionStaticQuestion)
class ExamSectionStaticQuestionAdmin(admin.ModelAdmin):
    list_display = ('exam_section', 'question', 'question_number')
    list_filter = ('exam_section__exam', 'exam_section__section_type')
    search_fields = ('question__text',)
    list_editable = ('question_number',)
    raw_id_fields = ('exam_section', 'question')

@admin.register(ExamSectionTopicRule)
class ExamSectionTopicRuleAdmin(admin.ModelAdmin):
    list_display = ('exam_section', 'topic', 'questions_count')
    list_filter = ('exam_section__exam', 'topic')
    search_fields = ('topic__name',)
    inlines = [ExamSectionSubtopicRuleInline]
    raw_id_fields = ('exam_section', 'topic')

@admin.register(ExamSectionSubtopicRule)
class ExamSectionSubtopicRuleAdmin(admin.ModelAdmin):
    list_display = ('topic_rule', 'subtopic', 'questions_count')
    list_filter = ('topic_rule__exam_section__exam', 'subtopic')
    search_fields = ('subtopic__name',)
    raw_id_fields = ('topic_rule', 'subtopic')

@admin.register(ExamSectionTagRule)
class ExamSectionTagRuleAdmin(admin.ModelAdmin):
    list_display = ('exam_section', 'tag', 'questions_count')
    list_filter = ('exam_section__exam', 'tag')
    search_fields = ('tag__name',)
    raw_id_fields = ('exam_section', 'tag')

# =================================================================
# 5. LIVE IMTIHON MODELLARI
# =================================================================

@admin.register(LiveExam)
class LiveExamAdmin(admin.ModelAdmin):
    list_display = ('title', 'exam', 'start_time', 'registration_deadline', 'price', 'is_active', 'created_at')
    list_filter = ('is_active', 'start_time')
    search_fields = ('title', 'exam__title')
    date_hierarchy = 'start_time'
    raw_id_fields = ('exam',)
    readonly_fields = ('created_at', 'updated_at')

@admin.register(LiveExamRegistration)
class LiveExamRegistrationAdmin(admin.ModelAdmin):
    list_display = ('user', 'live_exam', 'payment_status', 'payment_amount', 'registered_at')
    list_filter = ('payment_status', 'live_exam')
    search_fields = ('user__username', 'live_exam__title')
    date_hierarchy = 'registered_at'
    raw_id_fields = ('user', 'live_exam', 'purchase')
    readonly_fields = ('registered_at',)

# =================================================================
# 6. FOYDALANUVCHI FAOLIYATI MODELLARI
# =================================================================

@admin.register(UserAttempt)
class UserAttemptAdmin(admin.ModelAdmin):
    list_display = ('user', 'exam', 'mode', 'is_completed', 'final_total_score', 'get_duration', 'started_at', 'completed_at')
    list_filter = ('is_completed', 'exam__exam_type', 'mode')
    search_fields = ('user__username', 'exam__title')
    date_hierarchy = 'started_at'
    raw_id_fields = ('user', 'exam')
    readonly_fields = ('started_at', 'completed_at', 'get_duration')

    def get_duration(self, obj):
        if obj.completed_at and obj.started_at:
            duration = obj.completed_at - obj.started_at
            return str(duration).split('.')[0]
        return "Tugallanmagan"
    get_duration.short_description = "Davomiyligi"

@admin.register(UserAttemptSection)
class UserAttemptSectionAdmin(admin.ModelAdmin):
    list_display = ('attempt', 'section', 'score', 'ability_estimate', 'correct_answers_count', 'incorrect_answers_count', 'is_completed', 'started_at', 'completed_at')
    list_filter = ('section__section_type', 'is_completed')
    search_fields = ('attempt__user__username', 'section__exam__title')
    filter_horizontal = ('questions',)
    raw_id_fields = ('attempt', 'section')
    readonly_fields = ('started_at', 'completed_at')

@admin.register(UserAnswer)
class UserAnswerAdmin(admin.ModelAdmin):
    list_display = ('attempt_section', 'question', 'is_correct', 'answered_at', 'time_taken_seconds')
    list_filter = ('is_correct', 'attempt_section__section__section_type')
    search_fields = ('question__text', 'attempt_section__attempt__user__username')
    date_hierarchy = 'answered_at'
    raw_id_fields = ('attempt_section', 'question')
    filter_horizontal = ('selected_options',)
    readonly_fields = ('answered_at',)

@admin.register(UserSolutionView)
class UserSolutionViewAdmin(admin.ModelAdmin):
    list_display = ('user', 'question', 'credit_spent', 'viewed_at')
    list_filter = ('credit_spent',)
    search_fields = ('user__username', 'question__text')
    date_hierarchy = 'viewed_at'
    raw_id_fields = ('user', 'question')
    readonly_fields = ('viewed_at',)

# =================================================================
# 7. FLASHCARD MODELLARI
# =================================================================

@admin.register(Flashcard)
class FlashcardAdmin(admin.ModelAdmin):
    list_display = ('get_english_preview', 'get_uzbek_preview', 'content_type', 'source_question', 'author', 'created_at')
    list_filter = ('content_type', 'author')
    search_fields = ('english_content', 'uzbek_meaning', 'context_sentence')
    date_hierarchy = 'created_at'
    raw_id_fields = ('source_question', 'author')

    def get_english_preview(self, obj):
        cleaned_content = clean(str(obj.english_content), tags=[], strip=True)
        return cleaned_content[:50] + '...' if len(cleaned_content) > 50 else cleaned_content
    get_english_preview.short_description = 'English Content (preview)'

    def get_uzbek_preview(self, obj):
        cleaned_meaning = clean(str(obj.uzbek_meaning), tags=[], strip=True)
        return cleaned_meaning[:50] + '...' if len(cleaned_meaning) > 50 else cleaned_meaning
    get_uzbek_preview.short_description = 'Uzbek Meaning (preview)'

@admin.register(UserFlashcardStatus)
class UserFlashcardStatusAdmin(admin.ModelAdmin):
    list_display = ('user', 'flashcard', 'status', 'next_review_at', 'ease_factor', 'review_interval', 'repetition_count')
    list_filter = ('status', 'repetition_count')
    search_fields = ('user__username', 'flashcard__english_content')
    date_hierarchy = 'next_review_at'
    raw_id_fields = ('user', 'flashcard')
    readonly_fields = ('last_reviewed_at', 'next_review_at')

@admin.register(FlashcardReviewLog)
class FlashcardReviewLogAdmin(admin.ModelAdmin):
    list_display = ('user', 'flashcard_content', 'quality_rating', 'reviewed_at')
    list_filter = ('quality_rating', 'reviewed_at')
    search_fields = ('user__username', 'flashcard__english_content')
    raw_id_fields = ('user', 'flashcard')

    def flashcard_content(self, obj):
        if obj.flashcard:
            return clean(obj.flashcard.english_content, tags=[], strip=True)[:50]
        return "Noma'lum"
    flashcard_content.short_description = "Flashcard Content"

@admin.register(UserFlashcardDeck)
class UserFlashcardDeckAdmin(admin.ModelAdmin):
    list_display = ('user', 'title', 'created_at')
    search_fields = ('user__username', 'title', 'description')
    date_hierarchy = 'created_at'
    filter_horizontal = ('flashcards',)
    raw_id_fields = ('user',)
    readonly_fields = ('created_at',)

@admin.register(FlashcardExam)
class FlashcardExamAdmin(admin.ModelAdmin):
    list_display = ('title', 'source_exam', 'get_flashcard_count', 'created_at')
    search_fields = ('title', 'source_exam__title')
    date_hierarchy = 'created_at'
    filter_horizontal = ('flashcards',)
    raw_id_fields = ('source_exam',)
    readonly_fields = ('created_at',)

    def get_flashcard_count(self, obj):
        return obj.flashcards.count()
    get_flashcard_count.short_description = "Kartochkalar soni"

# =================================================================
# 8. XABARNOMALAR VA GAMIFIKATSIYA MODELLARI
# =================================================================

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('user', 'title', 'is_read', 'created_at', 'get_message_preview')
    list_filter = ('is_read',)
    search_fields = ('title', 'message', 'user__username')
    date_hierarchy = 'created_at'
    raw_id_fields = ('user',)
    readonly_fields = ('created_at',)

    def get_message_preview(self, obj):
        return obj.message[:50] + '...' if len(obj.message) > 50 else obj.message
    get_message_preview.short_description = 'Xabar (preview)'

@admin.register(Badge)
class BadgeAdmin(admin.ModelAdmin):
    list_display = ('title', 'trigger_type', 'exam_count', 'min_score', 'streak_days', 'daily_min_score', 'referral_count')
    search_fields = ('title', 'description')
    list_filter = ('trigger_type',)

@admin.register(UserBadge)
class UserBadgeAdmin(admin.ModelAdmin):
    list_display = ('user', 'badge', 'awarded_at')
    search_fields = ('user__username', 'badge__title')
    date_hierarchy = 'awarded_at'
    raw_id_fields = ('user', 'badge')
    readonly_fields = ('awarded_at',)

@admin.register(LeaderboardEntry)
class LeaderboardEntryAdmin(admin.ModelAdmin):
    list_display = ('user', 'leaderboard_type', 'week_number', 'score', 'updated_at')
    list_filter = ('leaderboard_type', 'week_number')
    search_fields = ('user__username',)
    date_hierarchy = 'updated_at'
    raw_id_fields = ('user',)
    readonly_fields = ('updated_at',)
    ordering = ('leaderboard_type', 'week_number', '-score')

@admin.register(UserMissionProgress)
class UserMissionProgressAdmin(admin.ModelAdmin):
    list_display = ('user', 'exam_attempts_completed', 'study_attempts_completed', 'highest_score', 'updated_at')
    search_fields = ('user__username',)
    list_filter = ('updated_at',)
    raw_id_fields = ('user',)
    readonly_fields = ('updated_at',)

# =================================================================
# 9. ARXIV MODELLARI
# =================================================================

@admin.register(UserAnswerArchive)
class UserAnswerArchiveAdmin(admin.ModelAdmin):
    list_display = ('attempt_section', 'question', 'is_correct', 'answered_at', 'time_taken_seconds')
    list_filter = ('is_correct',)
    search_fields = ('question__text', 'attempt_section__attempt__user__username')
    date_hierarchy = 'answered_at'
    raw_id_fields = ('attempt_section', 'question')
    readonly_fields = ('answered_at',)
