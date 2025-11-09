from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin
from django.utils.translation import gettext_lazy as _
from django.utils.safestring import mark_safe
from django.utils import timezone
from bleach import clean
from django.contrib.contenttypes.admin import GenericTabularInline
from django.urls import reverse
from ckeditor.widgets import CKEditorWidget
from .models import *

# Inline Classes
class AnswerOptionInline(admin.TabularInline):
    model = AnswerOption
    extra = 4
    fields = ('text', 'is_correct')
    formfield_overrides = {
        models.TextField: {'widget': CKEditorWidget},
    }

class QuestionSolutionInline(admin.TabularInline):
    model = QuestionSolution
    extra = 1
    fields = ('hint', 'detailed_solution')
    formfield_overrides = {
        models.TextField: {'widget': CKEditorWidget},
    }

class ExamSectionOrderInline(admin.TabularInline):
    model = ExamSectionOrder
    extra = 1
    fields = ('exam_section', 'order')
    raw_id_fields = ('exam_section',)
    ordering = ('order',)

class ExamSectionStaticQuestionInline(admin.TabularInline):
    model = ExamSectionStaticQuestion
    extra = 1
    fields = ('question', 'question_number')
    raw_id_fields = ('question',)
    ordering = ('question_number',)

class LessonInline(admin.TabularInline):
    model = Lesson
    extra = 1
    fields = ('order', 'title', 'related_exam')
    raw_id_fields = ('related_exam',)

# System and User Management
@admin.register(SystemConfiguration)
class SystemConfigurationAdmin(admin.ModelAdmin):
    list_display = ('question_calibration_threshold', 'solutions_enabled', 'default_solutions_are_free')
    fieldsets = (
        (None, {'fields': ('question_calibration_threshold', 'solutions_enabled', 'default_solutions_are_free')}),
    )

    def has_add_permission(self, request):
        return not self.model.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    list_display = ('payment_card_holder', 'payment_card_number', 'manager_phone_number', 'manager_telegram_username')
    fieldsets = (
        (_('To\'lov Ma\'lumotlari'), {'fields': ('payment_card_number', 'payment_card_holder')}),
        (_('Tezkor Tasdiqlash'), {'fields': ('manager_phone_number', 'manager_telegram_username')}),
    )

    def has_add_permission(self, request):
        return not self.model.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

@admin.register(Center)
class CenterAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'owner', 'is_active', 'is_subscription_valid')
    list_filter = ('is_active',)
    search_fields = ('name', 'slug', 'owner__username')
    raw_id_fields = ('owner',)
    readonly_fields = ('is_subscription_valid',)
    fieldsets = (
        (None, {
            'fields': ('name', 'slug', 'owner', 'is_active')
        }),
        (_('Holati'), {
            'fields': ('is_subscription_valid',)
        }),
    )

@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    list_display = ('name', 'center', 'teacher', 'is_active', 'created_at', 'student_count')
    list_filter = ('is_active', 'center', 'teacher')
    search_fields = ('name', 'center__name', 'teacher__username')
    filter_horizontal = ('students',)
    raw_id_fields = ('center', 'teacher')
    readonly_fields = ('created_at',)
    fieldsets = (
        (None, {'fields': ('name', 'center', 'teacher', 'students', 'is_active')}),
        (_('Sanalar'), {'fields': ('created_at',), 'classes': ('collapse',)}),
    )

    def student_count(self, obj):
        return obj.students.count()
    student_count.short_description = "O'quvchilar soni"

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.role == 'center_admin' and not request.user.is_superuser:
            return qs.filter(center=request.user.center)
        return qs

@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ('center', 'start_date', 'end_date', 'price', 'is_active')
    list_filter = ('is_active', 'center')
    search_fields = ('center__name',)
    date_hierarchy = 'end_date'
    raw_id_fields = ('center',)
    readonly_fields = ('start_date',)
    fieldsets = (
        (None, {'fields': ('center', 'start_date', 'end_date', 'price', 'is_active')}),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.role == 'center_admin' and not request.user.is_superuser:
            return qs.filter(center=request.user.center)
        return qs

@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'full_name', 'role', 'center', 'ability', 'teacher', 'is_approved', 'is_banned', 'is_staff')
    list_filter = ('role', 'is_approved', 'is_banned', 'is_staff', 'is_active', 'center')
    search_fields = ('username', 'full_name', 'email', 'phone_number')
    raw_id_fields = ('teacher', 'center')
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        (_('Shaxsiy ma\'lumotlar'), {'fields': ('full_name', 'email', 'phone_number', 'role', 'center', 'profile_picture', 'bio')}),
        (_('Boshqaruv ma\'lumotlari'), {'fields': ('ability', 'teacher', 'is_approved', 'is_banned')}),
        (_('Ruxsatlar'), {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        (_('Muhim sanalar'), {'fields': ('last_login', 'date_joined'), 'classes': ('collapse',)}),
    )
    add_fieldsets = (
        (None, {'classes': ('wide',), 'fields': ('username', 'password1', 'password2')}),
        (_('Shaxsiy ma\'lumotlar'), {'fields': ('full_name', 'email', 'phone_number', 'role', 'center', 'teacher')}),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.role == 'center_admin' and not request.user.is_superuser:
            return qs.filter(center=request.user.center)
        return qs

# Commercial Models
@admin.register(PromoCode)
class PromoCodeAdmin(admin.ModelAdmin):
    list_display = ('code', 'discount_type', 'discount_percent', 'discount_amount', 'is_active', 'valid_until', 'used_count', 'max_uses', 'center')
    list_filter = ('discount_type', 'is_active', 'center')
    search_fields = ('code',)
    date_hierarchy = 'valid_until'
    readonly_fields = ('used_count',)
    raw_id_fields = ('center',)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.role == 'center_admin' and not request.user.is_superuser:
            return qs.filter(center=request.user.center)
        return qs

@admin.register(ExamPackage)
class ExamPackageAdmin(admin.ModelAdmin):
    list_display = ('name', 'price', 'exam_credits', 'solution_view_credits_on_purchase', 'includes_flashcards', 'is_active', 'center')
    list_filter = ('is_active', 'includes_flashcards', 'center')
    search_fields = ('name', 'description')
    filter_horizontal = ('exams',)
    raw_id_fields = ('center',)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.role == 'center_admin' and not request.user.is_superuser:
            return qs.filter(center=request.user.center)
        return qs

@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = ('name', 'price', 'duration_days', 'includes_solution_access', 'includes_flashcards', 'is_active')
    list_filter = ('is_active', 'includes_solution_access', 'includes_flashcards')
    search_fields = ('name', 'description')

@admin.register(UserBalance)
class UserBalanceAdmin(admin.ModelAdmin):
    list_display = ('user', 'exam_credits', 'solution_view_credits', 'updated_at')
    list_filter = ('updated_at', 'user__center')
    search_fields = ('user__username', 'user__email')
    readonly_fields = ('updated_at',)
    raw_id_fields = ('user',)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.role == 'center_admin' and not request.user.is_superuser:
            return qs.filter(user__center=request.user.center)
        return qs

@admin.register(UserSubscription)
class UserSubscriptionAdmin(admin.ModelAdmin):
    list_display = ('user', 'plan', 'start_date', 'end_date', 'is_active', 'auto_renewal')
    list_filter = ('auto_renewal', 'plan', 'user__center')
    search_fields = ('user__username', 'plan__name')
    date_hierarchy = 'end_date'
    raw_id_fields = ('user', 'plan')

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.role == 'center_admin' and not request.user.is_superuser:
            return qs.filter(user__center=request.user.center)
        return qs

@admin.register(Purchase)
class PurchaseAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'purchase_type', 'item_name', 'final_amount', 'status', 'created_at', 'view_screenshot')
    list_filter = ('status', 'purchase_type', 'created_at')
    search_fields = ('user__username', 'id')
    list_editable = ('status',)
    date_hierarchy = 'created_at'
    ordering = ('-created_at',)
    readonly_fields = ('user', 'purchase_type', 'package', 'subscription_plan', 'amount', 'promo_code', 'final_amount', 'created_at', 'updated_at', 'view_screenshot_in_form', 'item_name')
    actions = ['approve_selected_purchases', 'reject_selected_purchases']
    raw_id_fields = ('user', 'package', 'subscription_plan', 'promo_code')
    fieldsets = (
        (_('Umumiy Ma\'lumot'), {'fields': ('user', 'status', 'purchase_type', 'item_name', 'final_amount')}),
        (_('Skrinshot va Izoh'), {'fields': ('view_screenshot_in_form', 'payment_comment')}),
        (_('Vaqt Belgilari'), {'fields': ('created_at', 'updated_at'), 'classes': ('collapse',)}),
    )

    def item_name(self, obj):
        if obj.package:
            return obj.package.name
        if obj.subscription_plan:
            return obj.subscription_plan.name
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
    approve_selected_purchases.short_description = "Tanlangan to'lovlarni TASDIQLASH"

    def reject_selected_purchases(self, request, queryset):
        queryset.update(status='rejected')
        self.message_user(request, f"{queryset.count()} ta to'lov rad etildi.", messages.WARNING)
    reject_selected_purchases.short_description = "Tanlangan to'lovlarni RAD ETISH"

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.role == 'center_admin' and not request.user.is_superuser:
            return qs.filter(user__center=request.user.center)
        return qs

# Content Models
@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ('name', 'parent', 'get_full_hierarchy', 'center', 'created_at')
    list_filter = ('parent', 'center')
    search_fields = ('name', 'description')
    list_select_related = ('parent', 'center')
    raw_id_fields = ('parent', 'center')

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.role == 'center_admin' and not request.user.is_superuser:
            return qs.filter(center=request.user.center)
        return qs

@admin.register(UserTagPerformance)
class UserTagPerformanceAdmin(admin.ModelAdmin):
    list_display = ('user', 'tag', 'success_rate', 'correct_answers', 'incorrect_answers', 'get_average_time_per_question', 'last_attempted_at')
    list_filter = ('tag', 'last_attempted_at', 'user__center')
    search_fields = ('user__username', 'tag__name')
    readonly_fields = ('success_rate', 'last_attempted_at', 'total_time_spent', 'attempts_count')
    raw_id_fields = ('user', 'tag')

    def get_average_time_per_question(self, obj):
        return obj.total_time_spent / obj.attempts_count if obj.attempts_count > 0 else 0
    get_average_time_per_question.short_description = "O'rtacha vaqt/savol (soniya)"

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.role == 'center_admin' and not request.user.is_superuser:
            return qs.filter(user__center=request.user.center)
        return qs

@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    list_display = ('name', 'teacher', 'order', 'center')
    list_filter = ('teacher', 'center')
    search_fields = ('name',)
    list_editable = ('order',)
    raw_id_fields = ('teacher', 'center')

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.role == 'center_admin' and not request.user.is_superuser:
            return qs.filter(center=request.user.center)
        return qs

@admin.register(Subtopic)
class SubtopicAdmin(admin.ModelAdmin):
    list_display = ('name', 'topic', 'order', 'center')
    list_filter = ('topic', 'topic__teacher', 'center')
    search_fields = ('name', 'topic__name')
    list_editable = ('order',)
    raw_id_fields = ('topic', 'center')

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.role == 'center_admin' and not request.user.is_superuser:
            return qs.filter(center=request.user.center)
        return qs

@admin.register(Passage)
class PassageAdmin(admin.ModelAdmin):
    list_display = ('title', 'author', 'center', 'created_at')
    list_filter = ('author', 'center')
    search_fields = ('title', 'content')
    date_hierarchy = 'created_at'
    raw_id_fields = ('author', 'center')
    formfield_overrides = {
        models.TextField: {'widget': CKEditorWidget},
    }

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.role == 'center_admin' and not request.user.is_superuser:
            return qs.filter(center=request.user.center)
        return qs

@admin.register(RaschDifficultyLevel)
class RaschDifficultyLevelAdmin(admin.ModelAdmin):
    list_display = ('name', 'min_difficulty', 'max_difficulty')
    search_fields = ('name',)
    ordering = ('min_difficulty',)

@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('id', 'get_text_preview', 'subtopic', 'author', 'answer_format', 'difficulty', 'is_calibrated', 'status', 'is_solution_free', 'center', 'created_at')
    list_filter = ('answer_format', 'status', 'is_calibrated', 'is_solution_free', 'subtopic__topic', 'difficulty_level', 'center')
    search_fields = ('text', 'tags__name', 'correct_short_answer')
    inlines = (AnswerOptionInline, QuestionSolutionInline)
    date_hierarchy = 'created_at'
    filter_horizontal = ('tags', 'flashcards')
    raw_id_fields = ('passage', 'subtopic', 'author', 'parent_question', 'center')
    fieldsets = (
        (None, {'fields': ('text', 'image', 'passage', 'subtopic', 'tags', 'flashcards', 'answer_format', 'correct_short_answer', 'author', 'center')}),
        (_('Difficulty Parameters'), {'fields': ('difficulty', 'discrimination', 'guessing', 'difficulty_level', 'is_calibrated', 'response_count')}),
        (_('Status'), {'fields': ('status', 'is_solution_free', 'parent_question', 'version')}),
        (_('Dates'), {'fields': ('created_at', 'updated_at'), 'classes': ('collapse',)}),
    )
    readonly_fields = ('response_count', 'version', 'created_at', 'updated_at')
    formfield_overrides = {
        models.TextField: {'widget': CKEditorWidget},
    }

    def get_text_preview(self, obj):
        cleaned_text = clean(str(obj.text), tags=[], strip=True)
        return mark_safe(cleaned_text[:100] + '...' if len(cleaned_text) > 100 else cleaned_text)
    get_text_preview.short_description = 'Savol matni (preview)'

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.role == 'center_admin' and not request.user.is_superuser:
            return qs.filter(center=request.user.center)
        return qs

@admin.register(QuestionSolution)
class QuestionSolutionAdmin(admin.ModelAdmin):
    list_display = ('question', 'get_hint_preview', 'get_detailed_solution_preview')
    list_filter = ('question__center',)
    search_fields = ('question__text', 'hint', 'detailed_solution')
    raw_id_fields = ('question',)
    formfield_overrides = {
        models.TextField: {'widget': CKEditorWidget},
    }

    def get_hint_preview(self, obj):
        cleaned_hint = clean(str(obj.hint or ''), tags=[], strip=True)
        return cleaned_hint[:50] + '...' if cleaned_hint and len(cleaned_hint) > 50 else cleaned_hint
    get_hint_preview.short_description = 'Hint (preview)'

    def get_detailed_solution_preview(self, obj):
        cleaned_solution = clean(str(obj.detailed_solution or ''), tags=[], strip=True)
        return cleaned_solution[:50] + '...' if cleaned_solution and len(cleaned_solution) > 50 else cleaned_solution
    get_detailed_solution_preview.short_description = 'Detailed Solution (preview)'

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.role == 'center_admin' and not request.user.is_superuser:
            return qs.filter(question__center=request.user.center)
        return qs

@admin.register(AnswerOption)
class AnswerOptionAdmin(admin.ModelAdmin):
    list_display = ('get_text_preview', 'question', 'is_correct')
    list_filter = ('is_correct', 'question__answer_format', 'question__center')
    search_fields = ('text', 'question__text')
    raw_id_fields = ('question',)
    formfield_overrides = {
        models.TextField: {'widget': CKEditorWidget},
    }

    def get_text_preview(self, obj):
        cleaned_text = clean(str(obj.text), tags=[], strip=True)
        return cleaned_text[:70] + '...' if len(cleaned_text) > 70 else cleaned_text
    get_text_preview.short_description = 'Variant matni (preview)'

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.role == 'center_admin' and not request.user.is_superuser:
            return qs.filter(question__center=request.user.center)
        return qs

@admin.register(QuestionReview)
class QuestionReviewAdmin(admin.ModelAdmin):
    list_display = ('question', 'user', 'status', 'created_at', 'get_comment_preview')
    list_filter = ('status', 'question__subtopic__topic', 'question__center')
    search_fields = ('comment', 'question__text', 'user__username')
    date_hierarchy = 'created_at'
    raw_id_fields = ('question', 'user')

    def get_comment_preview(self, obj):
        return obj.comment[:50] + '...' if len(obj.comment) > 50 else obj.comment
    get_comment_preview.short_description = 'Izoh (preview)'

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.role == 'center_admin' and not request.user.is_superuser:
            return qs.filter(question__center=request.user.center)
        return qs

# Exam Models
@admin.register(Exam)
class ExamAdmin(admin.ModelAdmin):
    list_display = ('title', 'teacher', 'is_subject_exam', 'passing_percentage', 'is_premium', 'is_active', 'center', 'created_at')
    list_filter = ('is_subject_exam', 'is_premium', 'is_active', 'center')
    search_fields = ('title', 'description')
    inlines = (ExamSectionOrderInline,)
    date_hierarchy = 'created_at'
    raw_id_fields = ('teacher', 'center')
    fieldsets = (
        (None, {'fields': ('teacher', 'title', 'description', 'is_subject_exam', 'passing_percentage', 'center')}),
        (_('Settings'), {'fields': ('is_premium', 'is_active')}),
        (_('Dates'), {'fields': ('created_at',), 'classes': ('collapse',)}),
    )
    readonly_fields = ('created_at',)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.role == 'center_admin' and not request.user.is_superuser:
            return qs.filter(center=request.user.center)
        return qs

@admin.register(ExamSection)
class ExamSectionAdmin(admin.ModelAdmin):
    list_display = ('name', 'section_type', 'duration_minutes', 'max_questions', 'min_difficulty', 'max_difficulty', 'created_by', 'center')
    list_filter = ('section_type', 'center')
    search_fields = ('name', 'section_type')
    inlines = (ExamSectionStaticQuestionInline,)
    raw_id_fields = ('created_by', 'center')
    fieldsets = (
        (None, {'fields': ('name', 'section_type', 'duration_minutes', 'max_questions', 'created_by', 'center')}),
        (_('Difficulty'), {'fields': ('min_difficulty', 'max_difficulty'), 'classes': ('collapse',)}),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.role == 'center_admin' and not request.user.is_superuser:
            return qs.filter(center=request.user.center)
        return qs

@admin.register(ExamSectionOrder)
class ExamSectionOrderAdmin(admin.ModelAdmin):
    list_display = ('exam', 'exam_section', 'order')
    list_filter = ('exam__center',)
    search_fields = ('exam__title', 'exam_section__name')
    list_editable = ('order',)
    raw_id_fields = ('exam', 'exam_section')

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.role == 'center_admin' and not request.user.is_superuser:
            return qs.filter(exam__center=request.user.center)
        return qs

@admin.register(ExamSectionStaticQuestion)
class ExamSectionStaticQuestionAdmin(admin.ModelAdmin):
    list_display = ('exam_section', 'question', 'question_number')
    list_filter = ('exam_section__section_type', 'exam_section__exams__center')
    search_fields = ('question__text', 'exam_section__name')
    list_editable = ('question_number',)
    raw_id_fields = ('exam_section', 'question')

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.role == 'center_admin' and not request.user.is_superuser:
            return qs.filter(exam_section__exams__center=request.user.center)
        return qs

@admin.register(UserAttempt)
class UserAttemptAdmin(admin.ModelAdmin):
    list_display = ('user', 'exam', 'mode', 'is_completed', 'final_total_score', 'get_duration', 'started_at', 'completed_at')
    list_filter = ('is_completed', 'exam__is_subject_exam', 'mode', 'exam__center')
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

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.role == 'center_admin' and not request.user.is_superuser:
            return qs.filter(exam__center=request.user.center)
        return qs

@admin.register(UserAttemptSection)
class UserAttemptSectionAdmin(admin.ModelAdmin):
    list_display = ('attempt', 'section', 'score', 'correct_answers_count', 'incorrect_answers_count', 'is_completed', 'started_at', 'completed_at')
    list_filter = ('section__section_type', 'is_completed', 'attempt__exam__center')
    search_fields = ('attempt__user__username', 'section__exam__title')
    filter_horizontal = ('questions',)
    raw_id_fields = ('attempt', 'section')
    readonly_fields = ('started_at', 'completed_at')

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.role == 'center_admin' and not request.user.is_superuser:
            return qs.filter(attempt__exam__center=request.user.center)
        return qs

@admin.register(UserAttemptQuestion)
class UserAttemptQuestionAdmin(admin.ModelAdmin):
    list_display = ('attempt_section', 'question', 'question_number')
    list_filter = ('attempt_section__section__section_type', 'attempt_section__attempt__exam__center')
    search_fields = ('question__text', 'attempt_section__attempt__user__username')
    list_editable = ('question_number',)
    raw_id_fields = ('attempt_section', 'question')

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.role == 'center_admin' and not request.user.is_superuser:
            return qs.filter(attempt_section__attempt__exam__center=request.user.center)
        return qs

@admin.register(UserAnswer)
class UserAnswerAdmin(admin.ModelAdmin):
    list_display = ('attempt_section', 'question', 'is_correct', 'answered_at', 'time_taken_seconds')
    list_filter = ('is_correct', 'attempt_section__section__section_type', 'attempt_section__attempt__exam__center')
    search_fields = ('question__text', 'attempt_section__attempt__user__username')
    date_hierarchy = 'answered_at'
    raw_id_fields = ('attempt_section', 'question')
    filter_horizontal = ('selected_options',)
    readonly_fields = ('answered_at',)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.role == 'center_admin' and not request.user.is_superuser:
            return qs.filter(attempt_section__attempt__exam__center=request.user.center)
        return qs

@admin.register(UserSolutionView)
class UserSolutionViewAdmin(admin.ModelAdmin):
    list_display = ('user', 'question', 'credit_spent', 'viewed_at')
    list_filter = ('credit_spent', 'question__center')
    search_fields = ('user__username', 'question__text')
    date_hierarchy = 'viewed_at'
    raw_id_fields = ('user', 'question')
    readonly_fields = ('viewed_at',)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.role == 'center_admin' and not request.user.is_superuser:
            return qs.filter(question__center=request.user.center)
        return qs

# Course and Lesson Models
@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ('title', 'teacher', 'course_type', 'online_lesson_flow', 'is_premium', 'is_active', 'price', 'center', 'created_at')
    list_filter = ('course_type', 'online_lesson_flow', 'is_premium', 'is_active', 'center')
    search_fields = ('title', 'description', 'teacher__full_name')
    date_hierarchy = 'created_at'
    raw_id_fields = ('teacher', 'center')
    fieldsets = (
        (None, {'fields': ('title', 'description', 'teacher', 'course_type', 'online_lesson_flow', 'center')}),
        (_('Settings'), {'fields': ('is_premium', 'is_active', 'price')}),
        (_('Dates'), {'fields': ('created_at',), 'classes': ('collapse',)}),
    )
    readonly_fields = ('created_at',)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.role == 'center_admin' and not request.user.is_superuser:
            return qs.filter(center=request.user.center)
        return qs

@admin.register(CourseModule)
class CourseModuleAdmin(admin.ModelAdmin):
    list_display = ('title', 'course', 'order', 'lesson_count')
    list_filter = ('course', 'course__teacher', 'course__center')
    search_fields = ('title', 'course__title')
    list_editable = ('order',)
    raw_id_fields = ('course',)
    inlines = (LessonInline,)

    def lesson_count(self, obj):
        return obj.lessons.count()
    lesson_count.short_description = "Darslar soni"

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.role == 'center_admin' and not request.user.is_superuser:
            return qs.filter(course__center=request.user.center)
        return qs

@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = ('title', 'module', 'order', 'related_exam_link', 'is_premium_exam', 'has_resources')
    list_filter = ('module__course', 'module__course__center', 'related_exam__is_premium')
    search_fields = ('title', 'module__title')
    list_editable = ('order',)
    raw_id_fields = ('module', 'related_exam')
    fieldsets = (
        (None, {'fields': ('title', 'module', 'order', 'related_exam')}),
    )

    def related_exam_link(self, obj):
        if obj.related_exam:
            try:
                exam_url = reverse(f"admin:{obj.related_exam._meta.app_label}_exam_change", args=[obj.related_exam.pk])
                return mark_safe(f'<a href="{exam_url}">{obj.related_exam.title}</a>')
            except:
                return obj.related_exam.title
        return "Test biriktirilmagan"
    related_exam_link.short_description = "Mavzu Testi"

    def is_premium_exam(self, obj):
        if obj.related_exam:
            return obj.related_exam.is_premium
        return False
    is_premium_exam.boolean = True
    is_premium_exam.short_description = "Test Pullik"

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.role == 'center_admin' and not request.user.is_superuser:
            return qs.filter(module__course__center=request.user.center)
        return qs

@admin.register(LessonResource)
class LessonResourceAdmin(admin.ModelAdmin):
    list_display = ('lesson', 'resource_type', 'title', 'link', 'order')
    list_filter = ('resource_type', 'lesson__module__course__center')
    search_fields = ('title', 'link', 'lesson__title')
    list_editable = ('order',)
    raw_id_fields = ('lesson',)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.role == 'center_admin' and not request.user.is_superuser:
            return qs.filter(lesson__module__course__center=request.user.center)
        return qs

@admin.register(CourseSchedule)
class CourseScheduleAdmin(admin.ModelAdmin):
    list_display = ('course', 'related_lesson', 'start_time', 'end_time', 'location')
    list_filter = ('course', 'course__center')
    search_fields = ('course__title', 'related_lesson__title', 'location')
    date_hierarchy = 'start_time'
    raw_id_fields = ('course', 'related_lesson')

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.role == 'center_admin' and not request.user.is_superuser:
            return qs.filter(course__center=request.user.center)
        return qs

# Flashcard Models
@admin.register(Flashcard)
class FlashcardAdmin(admin.ModelAdmin):
    list_display = ('get_english_preview', 'get_uzbek_preview', 'content_type', 'source_question', 'author', 'center', 'created_at')
    list_filter = ('content_type', 'author', 'center')
    search_fields = ('english_content', 'uzbek_meaning', 'context_sentence')
    date_hierarchy = 'created_at'
    raw_id_fields = ('source_question', 'author', 'center')
    fieldsets = (
        (None, {'fields': ('content_type', 'english_content', 'uzbek_meaning', 'context_sentence', 'author', 'source_question', 'center')}),
        (_('Dates'), {'fields': ('created_at',), 'classes': ('collapse',)}),
    )
    readonly_fields = ('created_at',)

    def get_english_preview(self, obj):
        cleaned_content = clean(str(obj.english_content), tags=[], strip=True)
        return cleaned_content[:50] + '...' if len(cleaned_content) > 50 else cleaned_content
    get_english_preview.short_description = 'English Content (preview)'

    def get_uzbek_preview(self, obj):
        cleaned_meaning = clean(str(obj.uzbek_meaning), tags=[], strip=True)
        return cleaned_meaning[:50] + '...' if len(cleaned_meaning) > 50 else cleaned_meaning
    get_uzbek_preview.short_description = 'Uzbek Meaning (preview)'

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.role == 'center_admin' and not request.user.is_superuser:
            return qs.filter(center=request.user.center)
        return qs

@admin.register(UserFlashcardStatus)
class UserFlashcardStatusAdmin(admin.ModelAdmin):
    list_display = ('user', 'flashcard', 'status', 'next_review_at', 'ease_factor', 'review_interval', 'repetition_count', 'last_quality_rating')
    list_filter = ('status', 'repetition_count', 'flashcard__center')
    search_fields = ('user__username', 'flashcard__english_content')
    date_hierarchy = 'next_review_at'
    raw_id_fields = ('user', 'flashcard')
    readonly_fields = ('last_reviewed_at', 'next_review_at')

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.role == 'center_admin' and not request.user.is_superuser:
            return qs.filter(flashcard__center=request.user.center)
        return qs

@admin.register(FlashcardReviewLog)
class FlashcardReviewLogAdmin(admin.ModelAdmin):
    list_display = ('user', 'flashcard_content', 'quality_rating', 'reviewed_at')
    list_filter = ('quality_rating', 'reviewed_at', 'flashcard__center')
    search_fields = ('user__username', 'flashcard__english_content')
    raw_id_fields = ('user', 'flashcard')
    readonly_fields = ('reviewed_at',)

    def flashcard_content(self, obj):
        if obj.flashcard:
            return clean(obj.flashcard.english_content, tags=[], strip=True)[:50]
        return "Noma'lum"
    flashcard_content.short_description = "Flashcard Content"

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.role == 'center_admin' and not request.user.is_superuser:
            return qs.filter(flashcard__center=request.user.center)
        return qs

@admin.register(UserFlashcardDeck)
class UserFlashcardDeckAdmin(admin.ModelAdmin):
    list_display = ('user', 'title', 'center', 'created_at')
    list_filter = ('center',)
    search_fields = ('user__username', 'title', 'description')
    date_hierarchy = 'created_at'
    filter_horizontal = ('flashcards',)
    raw_id_fields = ('user', 'center')
    readonly_fields = ('created_at',)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.role == 'center_admin' and not request.user.is_superuser:
            return qs.filter(center=request.user.center)
        return qs

@admin.register(FlashcardExam)
class FlashcardExamAdmin(admin.ModelAdmin):
    list_display = ('title', 'source_exam', 'get_flashcard_count', 'is_exam_review', 'center', 'created_at')
    list_filter = ('is_exam_review', 'center')
    search_fields = ('title', 'source_exam__title')
    date_hierarchy = 'created_at'
    filter_horizontal = ('flashcards',)
    raw_id_fields = ('source_exam', 'center')
    readonly_fields = ('created_at',)

    def get_flashcard_count(self, obj):
        return obj.flashcards.count()
    get_flashcard_count.short_description = "Kartochkalar soni"

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.role == 'center_admin' and not request.user.is_superuser:
            return qs.filter(center=request.user.center)
        return qs

# Notification and Gamification Models
@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('user', 'title', 'is_read', 'created_at', 'get_message_preview')
    list_filter = ('is_read', 'user__center')
    search_fields = ('title', 'message', 'user__username')
    date_hierarchy = 'created_at'
    raw_id_fields = ('user',)
    readonly_fields = ('created_at',)

    def get_message_preview(self, obj):
        return obj.message[:50] + '...' if len(obj.message) > 50 else obj.message
    get_message_preview.short_description = 'Xabar (preview)'

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.role == 'center_admin' and not request.user.is_superuser:
            return qs.filter(user__center=request.user.center)
        return qs

@admin.register(Badge)
class BadgeAdmin(admin.ModelAdmin):
    list_display = ('title', 'trigger_type', 'exam_count', 'min_score', 'streak_days', 'flashcard_count', 'daily_min_score', 'referral_count', 'center')
    list_filter = ('trigger_type', 'center')
    search_fields = ('title', 'description')
    raw_id_fields = ('center',)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.role == 'center_admin' and not request.user.is_superuser:
            return qs.filter(center=request.user.center)
        return qs

@admin.register(UserBadge)
class UserBadgeAdmin(admin.ModelAdmin):
    list_display = ('user', 'badge', 'awarded_at', 'center')
    list_filter = ('badge', 'center')
    search_fields = ('user__username', 'badge__title')
    date_hierarchy = 'awarded_at'
    raw_id_fields = ('user', 'badge', 'center')
    readonly_fields = ('awarded_at',)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.role == 'center_admin' and not request.user.is_superuser:
            return qs.filter(center=request.user.center)
        return qs

@admin.register(LeaderboardEntry)
class LeaderboardEntryAdmin(admin.ModelAdmin):
    list_display = ('user', 'leaderboard_type', 'week_number', 'score', 'updated_at', 'center')
    list_filter = ('leaderboard_type', 'week_number', 'center')
    search_fields = ('user__username',)
    date_hierarchy = 'updated_at'
    raw_id_fields = ('user', 'center')
    readonly_fields = ('updated_at',)
    ordering = ('leaderboard_type', 'week_number', '-score')

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.role == 'center_admin' and not request.user.is_superuser:
            return qs.filter(center=request.user.center)
        return qs

@admin.register(UserMissionProgress)
class UserMissionProgressAdmin(admin.ModelAdmin):
    list_display = ('user', 'exam_attempts_completed', 'study_attempts_completed', 'highest_score', 'updated_at')
    list_filter = ('updated_at', 'user__center')
    search_fields = ('user__username',)
    raw_id_fields = ('user',)
    readonly_fields = ('updated_at',)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.role == 'center_admin' and not request.user.is_superuser:
            return qs.filter(user__center=request.user.center)
        return qs

# Archive Models
@admin.register(UserAnswerArchive)
class UserAnswerArchiveAdmin(admin.ModelAdmin):
    list_display = ('attempt_section', 'question', 'is_correct', 'answered_at', 'time_taken_seconds')
    list_filter = ('is_correct', 'attempt_section__attempt__exam__center')
    search_fields = ('question__text', 'attempt_section__attempt__user__username')
    date_hierarchy = 'answered_at'
    raw_id_fields = ('attempt_section', 'question')
    readonly_fields = ('answered_at',)
    filter_horizontal = ('selected_options',)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.role == 'center_admin' and not request.user.is_superuser:
            return qs.filter(attempt_section__attempt__exam__center=request.user.center)
        return qs