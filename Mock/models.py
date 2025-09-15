from django.db import models
from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db.models.signals import post_save
from django.dispatch import receiver
from datetime import timedelta
import re
# from tinymce.models import HTMLField # TINYMCE importini o'chiramiz
from ckeditor_uploader.fields import RichTextUploadingField # CKEditor importini qo'shamiz

from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from django.db.models import JSONField
import bleach


# =================================================================
# 1. TIZIM SOZLAMALARI MODELI
# =================================================================
class SystemConfiguration(models.Model):
    """
    Tizimning global sozlamalarini saqlash uchun yagona model (Singleton).
    Admin panel orqali tizimning ishlash mantig'ini kodni o'zgartirmasdan boshqarish imkonini beradi.
    """
    question_calibration_threshold = models.PositiveIntegerField(
        default=30,
        verbose_name="Savolni kalibrovka qilish uchun minimal javoblar soni",
        help_text="Savolning qiyinlik darajasi shu sondagi javoblardan so'ng avtomatik hisoblanadi."
    )
    solutions_enabled = models.BooleanField(default=True, verbose_name="Savol yechimlarini yoqish")
    default_solutions_are_free = models.BooleanField(
        default=False,
        verbose_name="Standart holatda yechimlar bepulmi?",
        help_text="Agar bu yoqilgan bo'lsa, 'Yechim bepulmi?' deb belgilanmagan barcha savollar yechimi pullik bo'ladi."
    )

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        pass

    @classmethod
    def get_solo(cls):
        obj, created = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        return "Tizimning global sozlamalari"

    class Meta:
        verbose_name = "Tizim sozlamasi"
        verbose_name_plural = "Tizim sozlamalari"

# =================================================================
# 2. FOYDALANUVCHI VA HUQUQLAR MODELLARI
# =================================================================
class CustomUser(AbstractUser):
    ROLE_CHOICES = [('teacher', 'Ustoz'), ('student', 'Talaba'), ('admin', 'Administrator')]
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='student', verbose_name="Foydalanuvchi roli")
    is_approved = models.BooleanField(default=True, verbose_name="Tasdiqlangan")
    ability = models.FloatField(default=0.0, verbose_name="Foydalanuvchi qobiliyati (Rasch)")
    teacher = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True,
                                 limit_choices_to={'role': 'teacher'}, related_name='students',
                                 verbose_name="Biriktirilgan ustoz")
    profile_picture = models.ImageField(upload_to='profile_pics/', null=True, blank=True, verbose_name="Profil rasmi")
    bio = models.TextField(max_length=500, blank=True, verbose_name="O'zi haqida")
    is_banned = models.BooleanField(default=False, verbose_name="Bloklangan")
    telegram_id = models.CharField(max_length=50, unique=True, null=True, blank=True, verbose_name="Telegram ID")

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"

    def has_active_subscription(self):
        return hasattr(self, 'subscription') and self.subscription.is_active()

    class Meta:
        verbose_name = "Foydalanuvchi"
        verbose_name_plural = "Foydalanuvchilar"

# =================================================================
# 3. TIJORIY MODELLAR (MARKETING, OBUNA, TO'LOVLAR)
# =================================================================
class PromoCode(models.Model):
    code = models.CharField(max_length=50, unique=True, verbose_name="Promo kod")
    DISCOUNT_TYPE_CHOICES = [('percentage', 'Foiz'), ('fixed', 'Fiks summa')]
    discount_type = models.CharField(max_length=20, choices=DISCOUNT_TYPE_CHOICES, default='percentage',
                                     verbose_name="Chegirma turi")
    discount_percent = models.PositiveIntegerField(null=True, blank=True, verbose_name="Chegirma foizi",
                                                   help_text="Foiz chegirmasi uchun, masalan, 10% uchun 10 kiriting")
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True,
                                         verbose_name="Fiks chegirma summasi",
                                         help_text="Fiks summa chegirmasi uchun, masalan, 50000 so'm")
    valid_from = models.DateTimeField(default=timezone.now, verbose_name="Amal qilish boshlanishi")
    valid_until = models.DateTimeField(verbose_name="Amal qilish tugashi")
    max_uses = models.PositiveIntegerField(default=1, verbose_name="Maksimal ishlatishlar soni")
    used_count = models.PositiveIntegerField(default=0, editable=False, verbose_name="Ishlatilganlar soni")
    is_active = models.BooleanField(default=True, verbose_name="Aktiv")

    def clean(self):
        if self.discount_type == 'percentage' and self.discount_percent is None:
            raise ValidationError("Foiz chegirmasi uchun 'discount_percent' to'ldirilishi kerak.")
        if self.discount_type == 'fixed' and self.discount_amount is None:
            raise ValidationError("Fiks summa chegirmasi uchun 'discount_amount' to'ldirilishi kerak.")

    def is_valid(self):
        now = timezone.now()
        return self.is_active and self.valid_from <= now and self.valid_until > now and self.used_count < self.max_uses

    def __str__(self):
        return f"{self.code} ({self.discount_percent}% or {self.discount_amount} so'm)"

    class Meta:
        verbose_name = "Promo kod"
        verbose_name_plural = "Promo kodlar"

class ExamPackage(models.Model):
    name = models.CharField(max_length=100, verbose_name="Paket nomi")
    description = models.TextField(blank=True, null=True, verbose_name="Tavsif")
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Narxi (so'mda)")
    includes_flashcards = models.BooleanField(default=False, verbose_name="Flashcardlar to'plamini o'z ichiga oladimi?")
    exam_credits = models.PositiveIntegerField(verbose_name="Beriladigan imtihonlar soni (kredit)")
    solution_view_credits_on_purchase = models.PositiveIntegerField(default=0,
                                                                   verbose_name="Beriladigan yechimlar soni (kredit)")
    is_active = models.BooleanField(default=True, verbose_name="Aktiv")
    exams = models.ManyToManyField('Exam', related_name='packages', blank=True, verbose_name="Paketdagi imtihonlar")


    def __str__(self):
        return f"{self.name} - {self.exam_credits} imtihon / {self.solution_view_credits_on_purchase} yechim ({self.price} so'm)"

    class Meta:
        verbose_name = "Imtihon paketi"
        verbose_name_plural = "Imtihon paketlari"

class SubscriptionPlan(models.Model):
    name = models.CharField(max_length=100, verbose_name="Obuna rejasi nomi")
    description = models.TextField(blank=True, null=True, verbose_name="Tavsif")
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Narxi (so'mda)")
    duration_days = models.PositiveIntegerField(verbose_name="Amal qilish muddati (kunda)")
    includes_flashcards = models.BooleanField(default=False, verbose_name="Flashcardlar to'plamini o'z ichiga oladimi?")
    includes_solution_access = models.BooleanField(default=False,
                                                   verbose_name="Yechimlarni ko'rishni o'z ichiga oladimi?")
    is_active = models.BooleanField(default=True, verbose_name="Aktiv")

    def __str__(self):
        return f"{self.name} - {self.duration_days} kun ({self.price} so'm)"

    class Meta:
        verbose_name = "Obuna rejasi"
        verbose_name_plural = "Obuna rejalari"

class UserBalance(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='balance',
                                 verbose_name="Foydalanuvchi")
    exam_credits = models.PositiveIntegerField(default=0, verbose_name="Mavjud imtihon kreditlari")
    solution_view_credits = models.PositiveIntegerField(default=0, verbose_name="Mavjud yechim kreditlari")
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} - {self.exam_credits} imtihon / {self.solution_view_credits} yechim"

    class Meta:
        verbose_name = "Foydalanuvchi balansi"
        verbose_name_plural = "Foydalanuvchi balanslari"

class UserSubscription(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='subscription',
                                 verbose_name="Foydalanuvchi")
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.SET_NULL, null=True, verbose_name="Obuna rejasi")
    start_date = models.DateTimeField(verbose_name="Boshlangan sana")
    end_date = models.DateTimeField(verbose_name="Tugash sana")
    auto_renewal = models.BooleanField(default=False, verbose_name="Avtomatik uzaytirish")

    def is_active(self):
        return self.end_date > timezone.now()

    is_active.boolean = True
    is_active.short_description = "Aktivmi?"

    def __str__(self):
        return f"{self.user.username} - {self.plan.name if self.plan else 'Yo\'q'} ({'Aktiv' if self.is_active() else 'Aktiv emas'})"

    class Meta:
        verbose_name = "Foydalanuvchi obunasi"
        verbose_name_plural = "Foydalanuvchi obunalari"

@receiver(post_save, sender=CustomUser)
def create_user_related_models(sender, instance, created, **kwargs):
    if created:
        UserBalance.objects.create(user=instance)

class Purchase(models.Model):
    STATUS_CHOICES = [('pending', 'Kutilmoqda'), ('completed', 'Yakunlangan'), ('failed', 'Xatolik')]
    PURCHASE_TYPE_CHOICES = [('package', 'Paket'), ('subscription', 'Obuna')]
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='purchases',
                             verbose_name="Foydalanuvchi")
    purchase_type = models.CharField(max_length=20, choices=PURCHASE_TYPE_CHOICES, verbose_name="Xarid turi")
    package = models.ForeignKey(ExamPackage, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Paket")
    subscription_plan = models.ForeignKey(SubscriptionPlan, on_delete=models.SET_NULL, null=True, blank=True,
                                          verbose_name="Obuna rejasi")
    amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Boshlang'ich summa")
    promo_code = models.ForeignKey(PromoCode, on_delete=models.SET_NULL, null=True, blank=True,
                                    verbose_name="Promo kod")
    final_amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Yakuniy summa")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', db_index=True,
                              verbose_name="Holati")
    payment_gateway_id = models.CharField(max_length=255, blank=True, null=True, db_index=True,
                                         verbose_name="To'lov tizimi IDsi")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Xarid #{self.id} - {self.user.username}"

    class Meta:
        verbose_name = "Xarid"
        verbose_name_plural = "Xaridlar"
        ordering = ['-created_at']

# =================================================================
# 7. FLASHCARD VA LUG'AT O'RGANISH MODELLARI
# =================================================================
class Flashcard(models.Model):
    CONTENT_TYPE_CHOICES = [('word', 'So\'z/Ibora'), ('formula', 'Formula')]
    content_type = models.CharField(max_length=20, choices=CONTENT_TYPE_CHOICES, default='word', verbose_name="Kontent turi")
    english_content = RichTextUploadingField(verbose_name="Inglizcha kontent")
    uzbek_meaning = RichTextUploadingField(verbose_name="O'zbekcha ma'nosi")
    context_sentence = RichTextUploadingField(blank=True, null=True, verbose_name="Kontekst (gap)")
    
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='flashcards', verbose_name="Muallif")
    
    source_question = models.ForeignKey(
        'Question', # 'Question' modeliga to'g'ri havolani ta'minlash uchun stringdan foydalanish
        on_delete=models.SET_NULL, 
        related_name='associated_flashcards',
        verbose_name="Manba-savol",
        null=True, 
        blank=True
    )
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Flashcard (lug'at)"
        verbose_name_plural = "Flashcardlar (lug'atlar)"
        unique_together = ('english_content', 'source_question')

    def __str__(self):
        cleaned_english_content = bleach.clean(self.english_content, tags=[], strip=True)
        cleaned_uzbek_meaning = bleach.clean(self.uzbek_meaning, tags=[], strip=True)
        return f"{cleaned_english_content} - {cleaned_uzbek_meaning}"

class UserFlashcardStatus(models.Model):
    STATUS_CHOICES = [('not_learned', 'O\'rganilmagan'), ('learning', 'O\'rganilmoqda'), ('learned', 'O\'rganilgan')]
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='flashcard_statuses')
    flashcard = models.ForeignKey(Flashcard, on_delete=models.CASCADE, related_name='user_statuses')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='not_learned', db_index=True,
                              verbose_name="O'zlashtirish holati")
    last_reviewed_at = models.DateTimeField(null=True, blank=True, verbose_name="Oxirgi ko'rilgan vaqt")
    next_review_at = models.DateTimeField(default=timezone.now, db_index=True, verbose_name="Keyingi takrorlash vaqti")
    ease_factor = models.FloatField(default=2.5, verbose_name="Osonlik faktori")
    review_interval = models.PositiveIntegerField(default=1, verbose_name="Takrorlash intervali (kunda)")

    class Meta:
        verbose_name = "Foydalanuvchi flashcard holati"
        verbose_name_plural = "Foydalanuvchi flashcard holatlari"
        unique_together = ('user', 'flashcard')

    def __str__(self):
        return f"{self.user.username} - {self.flashcard.english_content}: {self.get_status_display()}"

class UserFlashcardDeck(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='flashcard_decks')
    title = models.CharField(max_length=200, verbose_name="To'plam nomi")
    description = models.TextField(blank=True, null=True, verbose_name="Tavsif")
    flashcards = models.ManyToManyField(Flashcard, blank=True, verbose_name="To'plamdagi kartochkalar")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Shaxsiy flashcard to'plami"
        verbose_name_plural = "Shaxsiy flashcard to'plamlari"

    def __str__(self):
        return f"{self.user.username} - {self.title}"

class FlashcardExam(models.Model):
    source_exam = models.OneToOneField('Exam', on_delete=models.CASCADE, related_name='flashcard_exam',
                                       verbose_name="Asosiy imtihon")
    title = models.CharField(max_length=255, verbose_name="Flashcard mashg'ulot nomi")
    flashcards = models.ManyToManyField('Flashcard', related_name='flashcard_exams', blank=True, verbose_name="Flashcardlar")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title

    class Meta:
        verbose_name = "Flashcard mashg'uloti"
        verbose_name_plural = "Flashcard mashg'ulotlari"

class FlashcardExamAttempt(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='flashcard_attempts')
    flashcard_exam = models.ForeignKey(FlashcardExam, on_delete=models.CASCADE, related_name='attempts')
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Flashcard mashg'uloti urinishi"
        verbose_name_plural = "Flashcard mashg'uloti urinishlari"

    def __str__(self):
        return f"{self.user.username} - {self.flashcard_exam.title}"

# =================================================================
# 4. KONTENT VA SAVOLLAR BANKI MODELLARI
# =================================================================

class Tag(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name="Teg nomi")

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Teg"
        verbose_name_plural = "Teglar"

class Topic(models.Model):
    name = models.CharField(max_length=200, verbose_name="Mavzu nomi")
    teacher = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name="Ustoz")
    order = models.PositiveIntegerField(default=0, verbose_name="Tartib raqami")

    class Meta:
        verbose_name = "Umumiy mavzu"
        verbose_name_plural = "Umumiy mavzular"
        ordering = ['order']
        unique_together = ('name', 'teacher')

    def __str__(self):
        return self.name

class Subtopic(models.Model):
    name = models.CharField(max_length=200, verbose_name="Ichki mavzu nomi")
    topic = models.ForeignKey(Topic, on_delete=models.CASCADE, related_name='subtopics', verbose_name="Umumiy mavzu")
    order = models.PositiveIntegerField(default=0, verbose_name="Tartib raqami")

    class Meta:
        verbose_name = "Ichki mavzu"
        verbose_name_plural = "Ichki mavzular"
        ordering = ['order']
        unique_together = ('name', 'topic')

    def __str__(self):
        return f"{self.name} ({self.topic.name})"

class Passage(models.Model):
    title = models.CharField(max_length=255, verbose_name="Matn sarlavhasi")
    content = RichTextUploadingField(verbose_name="Matn (HTML)") # `TextField` dan `RichTextUploadingField` ga o'zgartirildi
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='passages',
                               verbose_name="Muallif")
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        # CKEditor o'zining tozalash funksiyalariga ega, shuning uchun bu qism shart emas
        # Lekin qo'shimcha xavfsizlik uchun qoldirilishi mumkin
        # self.content = bleach.clean(self.content, tags=['p', 'b', 'i', 'u', 'strong', 'em'], strip=True)
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "Matn (Passage)"
        verbose_name_plural = "Matnlar (Passages)"

    def __str__(self):
        return self.title

class RaschDifficultyLevel(models.Model):
    name = models.CharField(max_length=50, unique=True, verbose_name="Daraja nomi")
    min_difficulty = models.FloatField(default=-3.0, verbose_name="Minimal qiyinlik")
    max_difficulty = models.FloatField(default=3.0, verbose_name="Maksimal qiyinlik")

    class Meta:
        verbose_name = "Rasch qiyinlik darajasi"
        verbose_name_plural = "Rasch qiyinlik darajalari"
        ordering = ['min_difficulty']

    def __str__(self):
        return f"{self.name} ({self.min_difficulty} - {self.max_difficulty})"

class Question(models.Model):
    text = RichTextUploadingField(verbose_name="Savol matni", default="<p></p>") # `HTMLField` dan `RichTextUploadingField` ga o'zgartirildi
    image = models.ImageField(upload_to='questions/', blank=True, null=True, verbose_name="Savol rasmi")
    passage = models.ForeignKey(Passage, on_delete=models.CASCADE, null=True, blank=True, related_name='questions', verbose_name="Matn")
    subtopic = models.ForeignKey(Subtopic, on_delete=models.PROTECT, related_name='questions', verbose_name="Ichki mavzu")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='questions', verbose_name="Muallif")
    tags = models.ManyToManyField(Tag, blank=True, verbose_name="Teglar")

    correct_short_answer = models.CharField(
        max_length=255, 
        blank=True, 
        null=True, 
        verbose_name="To'g'ri qisqa javob"
    )
    
    # Endi bu yerda Flashcard modeliga to'g'ridan-to'g'ri havola berish mumkin
    flashcards = models.ManyToManyField(Flashcard, related_name='questions', blank=True, verbose_name="Savolga oid flashcardlar")
    
    ANSWER_CHOICES = (('single', 'Yagona tanlov'), ('multiple', 'Ko\'p tanlov'), ('short_answer', 'Qisqa javob'))
    answer_format = models.CharField(max_length=20, choices=ANSWER_CHOICES, default='single', verbose_name="Javob formati")
    difficulty = models.FloatField(default=0.0, db_index=True, verbose_name="Qiyinlik darajasi (Rasch)")
    difficulty_level = models.ForeignKey(RaschDifficultyLevel, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Qiyinlik darajasi")
    STATUS_CHOICES = (('draft', 'Qoralama'), ('published', 'Nashr qilingan'), ('archived', 'Arxivlangan'))
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft', db_index=True,verbose_name="Holati")
    is_calibrated = models.BooleanField(default=False, db_index=True, verbose_name="Kalibrlanganmi?")
    response_count = models.PositiveIntegerField(default=0, verbose_name="Javoblar soni")
    is_solution_free = models.BooleanField(default=False, verbose_name="Yechim bepulmi?")
    version = models.PositiveIntegerField(default=1, verbose_name="Versiya")
    parent_question = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='versions', verbose_name="Asl (ota-ona) savol")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Savol"
        verbose_name_plural = "Savollar"
        ordering = ['-created_at']

    def __str__(self):
        cleaned_text = bleach.clean(self.text, tags=[], strip=True)
        return f"{cleaned_text[:60]}... (v{self.version})"

class QuestionTranslation(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='translations')
    language = models.CharField(max_length=10, default='uz', verbose_name="Til")
    text = RichTextUploadingField(verbose_name="Savol matni (HTML)") # `TextField` dan `RichTextUploadingField` ga o'zgartirildi

    def save(self, *args, **kwargs):
        # CKEditor o'zining tozalash funksiyalariga ega
        # self.text = bleach.clean(self.text, tags=['p', 'b', 'i', 'u', 'strong', 'em'], strip=True)
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "Savol tarjimasi"
        verbose_name_plural = "Savol tarjimasi"
        unique_together = ('question', 'language')

    def __str__(self):
        return f"{self.question.id} - {self.language}"

class QuestionSolution(models.Model):
    question = models.OneToOneField('Question', on_delete=models.CASCADE, related_name='solution', verbose_name="Savol")
    hint = RichTextUploadingField(blank=True, null=True, verbose_name="Yechim uchun maslahat") # `HTMLField` dan `RichTextUploadingField` ga o'zgartirildi
    detailed_solution = RichTextUploadingField(blank=True, null=True, verbose_name="Yechim") # `HTMLField` dan `RichTextUploadingField` ga o'zgartirildi
    
    class Meta:
        verbose_name = "Savol yechimi"
        verbose_name_plural = "Savollar yechimi"

    def __str__(self):
        return f"Savol: {self.question.id} yechimi"

class AnswerOption(models.Model):
    text = RichTextUploadingField(verbose_name="Variant matni", default="<p></p>") # `HTMLField` dan `RichTextUploadingField` ga o'zgartirildi
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='options', verbose_name="Savol")
    is_correct = models.BooleanField(default=False, verbose_name="To'g'ri javob")

    class Meta:
        verbose_name = "Javob varianti"
        verbose_name_plural = "Javob variantlari"

    def __str__(self):
        cleaned_text = bleach.clean(self.text, tags=[], strip=True)
        return cleaned_text[:70]

class AnswerOptionTranslation(models.Model):
    answer_option = models.ForeignKey(AnswerOption, on_delete=models.CASCADE, related_name='translations')
    language = models.CharField(max_length=10, default='uz', verbose_name="Til")
    text = RichTextUploadingField(verbose_name="Variant matni (HTML)") # `TextField` dan `RichTextUploadingField` ga o'zgartirildi

    def save(self, *args, **kwargs):
        # CKEditor o'zining tozalash funksiyalariga ega
        # self.text = bleach.clean(self.text, tags=['p', 'b', 'i', 'u', 'strong', 'em'], strip=True)
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "Javob varianti tarjimasi"
        verbose_name_plural = "Javob variantlari tarjimasi"
        unique_together = ('answer_option', 'language')

    def __str__(self):
        return f"{self.answer_option.id} - {self.language}"

class QuestionReview(models.Model):
    REVIEW_STATUS_CHOICES = [('open', 'Ochiq'), ('in_progress', 'Ko\'rib chiqilmoqda'), ('resolved', 'Hal qilindi')]
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='reviews', verbose_name="Savol")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                             verbose_name="Xabar bergan foydalanuvchi")
    comment = models.TextField(verbose_name="Izoh")
    status = models.CharField(max_length=20, choices=REVIEW_STATUS_CHOICES, default='open', db_index=True,
                              verbose_name="Holati")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        cleaned_text = bleach.clean(self.question.text, tags=[], strip=True)
        return f"{cleaned_text[:30]}... bo'yicha xabar"

    class Meta:
        verbose_name = "Savol bo'yicha shikoyat"
        verbose_name_plural = "Savollar bo'yicha shikoyatlar"
        ordering = ['-created_at']

# =================================================================
# 5. IMTIHON VA FOYDALANUVCHI FAOLIYATI MODELLARI
# =================================================================

class Exam(models.Model):
    EXAM_TYPE_CHOICES = [('adaptive', 'Adaptiv (generatsiyalanuvchi)'), ('static', 'Statik (qotirilgan)')]
    exam_type = models.CharField(max_length=20, choices=EXAM_TYPE_CHOICES, default='adaptive',
                                 verbose_name="Imtihon turi",
                                 help_text="Adaptiv - qoidalar asosida, Statik - aniq savollar ro'yxati asosida")
    teacher = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name="Ustoz")
    title = models.CharField(max_length=200, verbose_name="Test nomi")
    description = models.TextField(verbose_name="Tavsif", blank=True, null=True)
    is_premium = models.BooleanField(default=True, verbose_name="Pullik imtihon")
    is_active = models.BooleanField(default=True, verbose_name="Aktiv")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Imtihon"
        verbose_name_plural = "Imtihonlar"

    def __str__(self):
        return self.title

class ExamSection(models.Model):
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name='sections', verbose_name="Imtihon")
    SECTION_TYPES = (
        ('reading', 'Reading'), ('writing', 'Writing and Language'), ('math_no_calc', 'Math (No Calculator)'),
        ('math_calc', 'Math (Calculator)'))
    section_type = models.CharField(max_length=30, choices=SECTION_TYPES, verbose_name="Bo‘lim turi")
    duration_minutes = models.PositiveIntegerField(verbose_name="Davomiyligi (minut)")
    max_questions = models.PositiveIntegerField(verbose_name="Maksimal savollar soni")
    module_number = models.PositiveIntegerField(default=1, verbose_name="Modul raqami")
    order = models.PositiveIntegerField(default=0, verbose_name="Tartib raqami")
    static_questions = models.ManyToManyField(Question, through='ExamSectionStaticQuestion',
                                             related_name='static_exam_sections', blank=True,
                                             verbose_name="Statik savollar")
    min_difficulty = models.FloatField(null=True, blank=True, verbose_name="Minimal qiyinlik (Rasch)")
    max_difficulty = models.FloatField(null=True, blank=True, verbose_name="Maksimal qiyinlik (Rasch)")

    class Meta:
        verbose_name = "Imtihon bo‘limi"
        verbose_name_plural = "Imtihon bo‘limlari"
        ordering = ['order']
        unique_together = ('exam', 'section_type', 'module_number')

    def __str__(self):
        return f"{self.exam.title} - {self.get_section_type_display()} (Modul {self.module_number})"

class ExamSectionStaticQuestion(models.Model):
    exam_section = models.ForeignKey(ExamSection, on_delete=models.CASCADE)
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    question_number = models.PositiveIntegerField(verbose_name="Savol tartib raqami")

    class Meta:
        ordering = ['question_number']
        unique_together = ('exam_section', 'question')
        verbose_name = "Bo'limning statik savoli"
        verbose_name_plural = "Bo'limning statik savollari"

class ExamSectionTopicRule(models.Model):
    exam_section = models.ForeignKey(ExamSection, on_delete=models.CASCADE, related_name='topic_rules',
                                     verbose_name="Bo‘lim")
    topic = models.ForeignKey(Topic, on_delete=models.CASCADE, verbose_name="Umumiy mavzu")
    questions_count = models.PositiveIntegerField(verbose_name="Savollar soni")

    class Meta:
        verbose_name = "Bo‘lim mavzu qoidasi (Adaptiv)"
        verbose_name_plural = "Bo‘lim mavzu qoidalari (Adaptiv)"
        unique_together = ('exam_section', 'topic')

    def __str__(self):
        return f"{self.exam_section} - {self.topic.name}: {self.questions_count} ta savol"

class ExamSectionSubtopicRule(models.Model):
    topic_rule = models.ForeignKey(ExamSectionTopicRule, on_delete=models.CASCADE, related_name='subtopic_rules',
                                     verbose_name="Mavzu qoidasi")
    subtopic = models.ForeignKey(Subtopic, on_delete=models.CASCADE, verbose_name="Ichki mavzu")
    questions_count = models.PositiveIntegerField(verbose_name="Savollar soni")

    class Meta:
        verbose_name = "Bo‘lim ichki mavzu qoidasi (Adaptiv)"
        verbose_name_plural = "Bo‘lim ichki mavzu qoidalari (Adaptiv)"
        unique_together = ('topic_rule', 'subtopic')

    def __str__(self):
        return f"{self.subtopic.name}: {self.questions_count} ta savol"

class UserAttempt(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='attempts',
                             verbose_name="Foydalanuvchi")
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, verbose_name="Imtihon")
    started_at = models.DateTimeField(auto_now_add=True, verbose_name="Boshlangan vaqti")
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name="Tugatilgan vaqti")
    is_completed = models.BooleanField(default=False, db_index=True, verbose_name="Tugatilgan")
    final_ebrw_score = models.PositiveIntegerField(null=True, blank=True, verbose_name="Yakuniy EBRW balli")
    final_math_score = models.PositiveIntegerField(null=True, blank=True, verbose_name="Yakuniy Math balli")
    final_total_score = models.PositiveIntegerField(null=True, blank=True, verbose_name="Yakuniy umumiy ball")

    class Meta:
        verbose_name = "Foydalanuvchi urinishi"
        verbose_name_plural = "Foydalanuvchi urinishlari"

    def __str__(self):
        return f"{self.user.username} - {self.exam.title}"

class UserAttemptSection(models.Model):
    attempt = models.ForeignKey(UserAttempt, on_delete=models.CASCADE, related_name='section_attempts',
                                 verbose_name="Urinish")
    section = models.ForeignKey(ExamSection, on_delete=models.CASCADE, verbose_name="Bo‘lim")
    score = models.PositiveIntegerField(default=0, verbose_name="Bo‘lim balli")
    ability_estimate = models.FloatField(default=0.0, verbose_name="Taxminiy qobiliyat (Rasch)")
    correct_answers_count = models.PositiveIntegerField(default=0, verbose_name="To'g'ri javoblar soni")
    incorrect_answers_count = models.PositiveIntegerField(default=0, verbose_name="Noto'g'ri javoblar soni")
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name="Tugatilgan vaqti")
    questions = models.ManyToManyField(Question, related_name='attempted_in_sections', blank=True,
                                       verbose_name="Berilgan savollar")
    remaining_time_seconds = models.PositiveIntegerField(null=True, blank=True, verbose_name="Qolgan vaqt (soniya)")

    class Meta:
        verbose_name = "Bo‘lim urinishi"
        verbose_name_plural = "Bo‘lim urinishlari"
        unique_together = ('attempt', 'section')

    def __str__(self):
        return f"{self.attempt} - {self.section}"

class UserAnswer(models.Model):
    attempt_section = models.ForeignKey(UserAttemptSection, on_delete=models.CASCADE, related_name='user_answers')
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    selected_options = models.ManyToManyField(AnswerOption, blank=True, verbose_name="Tanlangan variantlar")
    short_answer_text = models.CharField(max_length=255, blank=True, null=True, verbose_name="Qisqa javob matni")
    is_correct = models.BooleanField(null=True, verbose_name="To'g'riligi")
    answered_at = models.DateTimeField(auto_now_add=True)
    time_taken_seconds = models.PositiveIntegerField(null=True, blank=True, verbose_name="Sarflangan vaqt (soniya)")

    class Meta:
        verbose_name = "Foydalanuvchi javobi"
        verbose_name_plural = "Foydalanuvchi javoblari"
        unique_together = ('attempt_section', 'question')

    def __str__(self):
        return f"{self.attempt_section.attempt.user.username} javobi"


# =================================================================
# 6. SAVOL YECHIMLARINI KO'RISHNI NAZORAT QILISH
# =================================================================
class UserSolutionView(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='solution_views')
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='solution_views')
    viewed_at = models.DateTimeField(auto_now_add=True)
    credit_spent = models.BooleanField(default=False, verbose_name="Kredit sarflandimi?")

    class Meta:
        verbose_name = "Ko'rilgan savol yechimi"
        verbose_name_plural = "Ko'rilgan savol yechimlari"
        unique_together = ('user', 'question')

    def __str__(self):
        return f"{self.user.username} -> {self.question.id}-savol yechimi"

# =================================================================
# 8. FOYDALANUVCHI FAOLIYATI VA XABARNOMALAR
# =================================================================
class Notification(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=255, verbose_name="Sarlavha")
    message = models.TextField(verbose_name="Xabar matni")
    is_read = models.BooleanField(default=False, db_index=True, verbose_name="O'qilganmi?")
    created_at = models.DateTimeField(auto_now_add=True)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, null=True, blank=True)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    related_object = GenericForeignKey('content_type', 'object_id')

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Xabarnoma"
        verbose_name_plural = "Xabarnomalar"

    def __str__(self):
        return f"{self.user.username} uchun xabarnoma"

# =================================================================
# 9. GAMIFIKATSIYA MODELLARI
# =================================================================
class Badge(models.Model):
    title = models.CharField(max_length=100, unique=True, verbose_name="Nishon nomi")
    description = models.TextField(verbose_name="Tavsif")
    icon = models.ImageField(upload_to='badges/', verbose_name="Nishon ikonasi")
    trigger_condition = models.CharField(max_length=100, verbose_name="Trigger sharti")
    condition_params = JSONField(null=True, blank=True, verbose_name="Shart parametrlari",
                                 help_text="JSON formatida qo'shimcha shartlar (masalan, {'min_score': 80, 'exam_count': 5})")

    def __str__(self):
        return self.title

    class Meta:
        verbose_name = "Nishon (Yutuq)"
        verbose_name_plural = "Nishonlar (Yutuqlar)"

class UserBadge(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='badges')
    badge = models.ForeignKey(Badge, on_delete=models.CASCADE, related_name='awarded_users')
    awarded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'badge')
        verbose_name = "Foydalanuvchi nishoni"
        verbose_name_plural = "Foydalanuvchi nishonlari"

    def __str__(self):
        return f"{self.user.username} - {self.badge.title}"

# =================================================================
# 10. MA'LUMOTLAR ARXIVI
# =================================================================
class UserAnswerArchive(models.Model):
    attempt_section = models.ForeignKey(UserAttemptSection, on_delete=models.CASCADE, related_name='archived_answers')
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    selected_options = models.ManyToManyField(AnswerOption, blank=True, verbose_name="Tanlangan variantlar")
    short_answer_text = models.CharField(max_length=255, blank=True, null=True, verbose_name="Qisqa javob matni")
    is_correct = models.BooleanField(null=True, verbose_name="To'g'riligi")
    answered_at = models.DateTimeField()
    time_taken_seconds = models.PositiveIntegerField(null=True, blank=True, verbose_name="Sarflangan vaqt (soniya)")

    class Meta:
        verbose_name = "Arxivlangan foydalanuvchi javobi"
        verbose_name_plural = "Arxivlangan foydalanuvchi javoblari"

    def __str__(self):
        return f"Arxiv: {self.attempt_section.attempt.user.username} javobi"