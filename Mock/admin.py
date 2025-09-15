from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.translation import gettext_lazy as _
from .models import (
    SystemConfiguration, CustomUser, PromoCode, ExamPackage, SubscriptionPlan, UserBalance,
    UserSubscription, Purchase, Tag, Topic, Subtopic, Passage, RaschDifficultyLevel,
    Question, QuestionTranslation, QuestionSolution, AnswerOption, AnswerOptionTranslation,
    QuestionReview, Exam, ExamSection, ExamSectionStaticQuestion, ExamSectionTopicRule,
    ExamSectionSubtopicRule, UserAttempt, UserAttemptSection, UserAnswer, UserSolutionView,
    Flashcard, UserFlashcardStatus, UserFlashcardDeck, FlashcardExam, FlashcardExamAttempt,
    Notification, Badge, UserBadge, UserAnswerArchive
)

# Singleton model for SystemConfiguration
@admin.register(SystemConfiguration)
class SystemConfigurationAdmin(admin.ModelAdmin):
    list_display = ('question_calibration_threshold', 'solutions_enabled', 'default_solutions_are_free')
    def has_add_permission(self, request):
        return False if self.model.objects.count() > 0 else super().has_add_permission(request)
    def has_delete_permission(self, request, obj=None):
        return False

# Custom User Admin
@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'role', 'is_approved', 'is_banned', 'ability', 'teacher')
    list_filter = ('role', 'is_approved', 'is_banned')
    search_fields = ('username', 'email', 'first_name', 'last_name')
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        (_('Personal info'), {'fields': ('first_name', 'last_name', 'email', 'profile_picture', 'bio')}),
        (_('Permissions'), {'fields': ('is_active', 'is_approved', 'is_banned', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        (_('Role info'), {'fields': ('role', 'teacher', 'ability')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'password1', 'password2', 'role', 'is_approved', 'teacher', 'profile_picture', 'bio'),
        }),
    )
    list_editable = ('is_approved', 'is_banned')

# Commercial Models
@admin.register(PromoCode)
class PromoCodeAdmin(admin.ModelAdmin):
    list_display = ('code', 'discount_type', 'discount_percent', 'discount_amount', 'is_active', 'valid_until', 'used_count', 'max_uses')
    list_filter = ('discount_type', 'is_active')
    search_fields = ('code',)
    date_hierarchy = 'valid_until'

@admin.register(ExamPackage)
class ExamPackageAdmin(admin.ModelAdmin):
    list_display = ('name', 'price', 'exam_credits', 'solution_view_credits_on_purchase', 'includes_flashcards', 'is_active')
    list_filter = ('is_active', 'includes_flashcards')
    search_fields = ('name', 'description')
    
    # 'fieldsets'ni qo'shamiz, bu ma'lumotlarni guruhlash uchun qulay
    fieldsets = (
        (None, {'fields': ('name', 'description', 'price', 'is_active')}),
        ('Imtiyozlar', {'fields': ('exam_credits', 'solution_view_credits_on_purchase', 'includes_flashcards')}),
        ('Paketdagi Imtihonlar', {'fields': ('exams',), 'classes': ('collapse',)})
    )
    filter_horizontal = ('exams',)

@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = ('name', 'price', 'duration_days', 'includes_solution_access', 'includes_flashcards', 'is_active')
    list_filter = ('is_active', 'includes_solution_access', 'includes_flashcards')
    search_fields = ('name', 'description')
    fieldsets = (
        (None, {'fields': ('name', 'description', 'price', 'duration_days', 'is_active')}),
        ('Imtiyozlar', {'fields': ('includes_solution_access', 'includes_flashcards')}),
    )
    
@admin.register(UserBalance)
class UserBalanceAdmin(admin.ModelAdmin):
    list_display = ('user', 'exam_credits', 'solution_view_credits', 'updated_at')
    search_fields = ('user__username', 'user__email')
    readonly_fields = ('updated_at',)

@admin.register(UserSubscription)
class UserSubscriptionAdmin(admin.ModelAdmin):
    list_display = ('user', 'plan', 'start_date', 'end_date', 'is_active', 'auto_renewal')
    list_filter = ('auto_renewal',)
    search_fields = ('user__username', 'plan__name')
    date_hierarchy = 'end_date'

@admin.register(Purchase)
class PurchaseAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'purchase_type', 'final_amount', 'status', 'created_at')
    list_filter = ('purchase_type', 'status')
    search_fields = ('user__username', 'payment_gateway_id')
    date_hierarchy = 'created_at'
    readonly_fields = ('created_at',)

# Content Models
@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)

@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    list_display = ('name', 'teacher', 'order')
    list_filter = ('teacher',)
    search_fields = ('name',)
    list_editable = ('order',)

@admin.register(Subtopic)
class SubtopicAdmin(admin.ModelAdmin):
    list_display = ('name', 'topic', 'order')
    list_filter = ('topic',)
    search_fields = ('name',)
    list_editable = ('order',)

@admin.register(Passage)
class PassageAdmin(admin.ModelAdmin):
    list_display = ('title', 'author', 'created_at')
    search_fields = ('title', 'content')
    list_filter = ('author',)
    date_hierarchy = 'created_at'

@admin.register(RaschDifficultyLevel)
class RaschDifficultyLevelAdmin(admin.ModelAdmin):
    list_display = ('name', 'min_difficulty', 'max_difficulty')
    search_fields = ('name',)

# Question and Related Models
class QuestionTranslationInline(admin.TabularInline):
    model = QuestionTranslation
    extra = 1
    fields = ('language', 'text')

class AnswerOptionInline(admin.TabularInline):
    model = AnswerOption
    extra = 2
    fields = ('is_correct',)

class AnswerOptionTranslationInline(admin.TabularInline):
    model = AnswerOptionTranslation
    extra = 1
    fields = ('language', 'text')

@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('id', 'subtopic', 'author', 'answer_format', 'difficulty', 'is_calibrated', 'status', 'is_solution_free')
    list_filter = ('answer_format', 'status', 'is_calibrated', 'is_solution_free', 'subtopic__topic')
    search_fields = ('text',)
    inlines = [QuestionTranslationInline, AnswerOptionInline]
    list_select_related = ('subtopic', 'author')
    date_hierarchy = 'created_at'

class QuestionSolutionAdmin(admin.ModelAdmin):
    # 'solution_generation_status' maydoni mavjud emas, shuning uchun uni olib tashlaymiz.
    # Endi faqat mavjud maydonlarni ko'rsatamiz.
    list_display = ('question', 'hint', 'detailed_solution')
    search_fields = ('question__text', 'hint', 'detailed_solution')
    # 'solution_generation_status' maydoni mavjud emas, shuning uchun uni olib tashlaymiz.
    list_filter = ('question') 


@admin.register(AnswerOption)
class AnswerOptionAdmin(admin.ModelAdmin):
    list_display = ('question', 'is_correct')
    list_filter = ('is_correct',)
    search_fields = ('text',)
    inlines = [AnswerOptionTranslationInline]

@admin.register(QuestionReview)
class QuestionReviewAdmin(admin.ModelAdmin):
    list_display = ('question', 'user', 'status', 'created_at')
    list_filter = ('status',)
    search_fields = ('comment', 'question__text')
    date_hierarchy = 'created_at'

# Exam Models
class ExamSectionInline(admin.TabularInline):
    model = ExamSection
    extra = 1
    fields = ('section_type', 'duration_minutes', 'max_questions', 'module_number', 'order')

@admin.register(Exam)
class ExamAdmin(admin.ModelAdmin):
    list_display = ('title', 'teacher', 'exam_type', 'is_premium', 'is_active', 'created_at')
    list_filter = ('exam_type', 'is_premium', 'is_active')
    search_fields = ('title', 'description')
    inlines = [ExamSectionInline]
    date_hierarchy = 'created_at'

@admin.register(ExamSection)
class ExamSectionAdmin(admin.ModelAdmin):
    list_display = ('exam', 'section_type', 'module_number', 'duration_minutes', 'max_questions')
    list_filter = ('section_type', 'exam')
    search_fields = ('exam__title',)

@admin.register(ExamSectionStaticQuestion)
class ExamSectionStaticQuestionAdmin(admin.ModelAdmin):
    list_display = ('exam_section', 'question', 'question_number')
    list_filter = ('exam_section__exam',)
    search_fields = ('question__text',)
    list_editable = ('question_number',)

@admin.register(ExamSectionTopicRule)
class ExamSectionTopicRuleAdmin(admin.ModelAdmin):
    list_display = ('exam_section', 'topic', 'questions_count')
    list_filter = ('exam_section__exam', 'topic')
    search_fields = ('topic__name',)

@admin.register(ExamSectionSubtopicRule)
class ExamSectionSubtopicRuleAdmin(admin.ModelAdmin):
    list_display = ('topic_rule', 'subtopic', 'questions_count')
    list_filter = ('topic_rule__exam_section__exam', 'subtopic')
    search_fields = ('subtopic__name',)

# User Activity Models
@admin.register(UserAttempt)
class UserAttemptAdmin(admin.ModelAdmin):
    list_display = ('user', 'exam', 'is_completed', 'final_total_score', 'started_at')
    list_filter = ('is_completed', 'exam')
    search_fields = ('user__username', 'exam__title')
    date_hierarchy = 'started_at'

@admin.register(UserAttemptSection)
class UserAttemptSectionAdmin(admin.ModelAdmin):
    list_display = ('attempt', 'section', 'score', 'correct_answers_count', 'incorrect_answers_count')
    list_filter = ('section__exam',)
    search_fields = ('attempt__user__username', 'section__exam__title')

@admin.register(UserAnswer)
class UserAnswerAdmin(admin.ModelAdmin):
    list_display = ('attempt_section', 'question', 'is_correct', 'answered_at')
    list_filter = ('is_correct',)
    search_fields = ('question__text', 'attempt_section__attempt__user__username')
    date_hierarchy = 'answered_at'

@admin.register(UserSolutionView)
class UserSolutionViewAdmin(admin.ModelAdmin):
    list_display = ('user', 'question', 'credit_spent', 'viewed_at')
    list_filter = ('credit_spent',)
    search_fields = ('user__username', 'question__text')
    date_hierarchy = 'viewed_at'

# Flashcard Models
@admin.register(Flashcard)
class FlashcardAdmin(admin.ModelAdmin):
    list_display = ('english_content', 'uzbek_meaning', 'content_type', 'source_question', 'created_at')
    list_filter = ('content_type',)
    search_fields = ('english_content', 'uzbek_meaning', 'context_sentence')
    date_hierarchy = 'created_at'

@admin.register(UserFlashcardStatus)
class UserFlashcardStatusAdmin(admin.ModelAdmin):
    list_display = ('user', 'flashcard', 'status', 'next_review_at', 'ease_factor')
    list_filter = ('status',)
    search_fields = ('user__username', 'flashcard__english_content')
    date_hierarchy = 'next_review_at'

@admin.register(UserFlashcardDeck)
class UserFlashcardDeckAdmin(admin.ModelAdmin):
    list_display = ('user', 'title', 'created_at')
    search_fields = ('user__username', 'title')
    date_hierarchy = 'created_at'

@admin.register(FlashcardExam)
class FlashcardExamAdmin(admin.ModelAdmin):
    list_display = ('title', 'source_exam', 'created_at')
    search_fields = ('title', 'source_exam__title')
    date_hierarchy = 'created_at'

@admin.register(FlashcardExamAttempt)
class FlashcardExamAttemptAdmin(admin.ModelAdmin):
    list_display = ('user', 'flashcard_exam', 'started_at', 'completed_at')
    search_fields = ('user__username', 'flashcard_exam__title')
    date_hierarchy = 'started_at'

# Notification and Gamification
@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('user', 'title', 'is_read', 'created_at')
    list_filter = ('is_read',)
    search_fields = ('title', 'message', 'user__username')
    date_hierarchy = 'created_at'

@admin.register(Badge)
class BadgeAdmin(admin.ModelAdmin):
    list_display = ('title', 'trigger_condition')
    search_fields = ('title', 'description')

@admin.register(UserBadge)
class UserBadgeAdmin(admin.ModelAdmin):
    list_display = ('user', 'badge', 'awarded_at')
    search_fields = ('user__username', 'badge__title')
    date_hierarchy = 'awarded_at'

# Archive
@admin.register(UserAnswerArchive)
class UserAnswerArchiveAdmin(admin.ModelAdmin):
    list_display = ('attempt_section', 'question', 'is_correct', 'answered_at')
    list_filter = ('is_correct',)
    search_fields = ('question__text', 'attempt_section__attempt__user__username')
    date_hierarchy = 'answered_at'