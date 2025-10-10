from django.db import models
from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db.models.signals import post_save
from django.dispatch import receiver
from datetime import timedelta
from ckeditor_uploader.fields import RichTextUploadingField 
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.auth.models import AbstractUser
from django.utils.html import strip_tags 
import bleach
import re
import math
from utils.irt import ThreeParameterLogisticModel

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

class SiteSettings(models.Model):
    # To'lov uchun ma'lumotlar
    payment_card_number = models.CharField(max_length=20, help_text="To'lov qabul qilinadigan plastik karta raqami. Format: 8600 1234 ...")
    payment_card_holder = models.CharField(max_length=100, help_text="Karta egasining ismi va familiyasi. Masalan: ALI VALIYEV")
    
    # Tezkor tasdiqlash uchun ma'lumotlar
    manager_phone_number = models.CharField(max_length=20, help_text="To'lovni tezkor tasdiqlash uchun menejer telefon raqami. Format: +998901234567")
    manager_telegram_username = models.CharField(max_length=100, blank=True, help_text="Menejerning telegram username'i (masalan, @menejer_username)")

    def __str__(self):
        return "Sayt Sozlamalari"

    class Meta:
        verbose_name = "Sayt Sozlamalari"
        verbose_name_plural = "Sayt Sozlamalari"

# =================================================================
# 2. FOYDALANUVCHI VA HUQUQLAR MODELLARI
# =================================================================


class CustomUser(AbstractUser):
    # AbstractUser'dagi first_name va last_name'ni ishlatmaymiz
    first_name = None
    last_name = None

    # Ularning o'rniga yangi maydon
    full_name = models.CharField(max_length=255, verbose_name="To'liq ism (F.I.Sh)")
    
    # Email maydonini majburiy va unikal qilamiz
    email = models.EmailField(unique=True, verbose_name="Elektron pochta")

    # Boshqa maydonlar
    phone_number = models.CharField(max_length=20, unique=True, verbose_name="Telefon raqami")
    
    ROLE_CHOICES = [
        ('student', 'Talaba'),
        ('teacher', 'Ustoz'),
        ('admin', 'Administrator'),
    ]
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='student', verbose_name="Foydalanuvchi roli")
    
    profile_picture = models.ImageField(upload_to='profile_pics/', null=True, blank=True, verbose_name="Profil rasmi")
    bio = models.TextField(max_length=500, blank=True, verbose_name="O'zi haqida")
    
    # ability va teacher maydonlari sizning asosiy logikangiz uchun qoldirildi
    ability = models.FloatField(default=0.0, verbose_name="Foydalanuvchi qobiliyati (Rasch)")
    teacher = models.ForeignKey(
        'self', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        limit_choices_to={'role': 'teacher'}, 
        related_name='students',
        verbose_name="Biriktirilgan ustoz"
    )

    is_approved = models.BooleanField(default=True, verbose_name="Tasdiqlangan")
    is_banned = models.BooleanField(default=False, verbose_name="Bloklangan")

    USERNAME_FIELD = 'username' # Tizimga kirish uchun username ishlatiladi
    REQUIRED_FIELDS = ['email', 'full_name', 'phone_number'] # Superuser yaratishda so'raladigan maydonlar

    def __str__(self):
        return self.username

    def get_full_name(self):
        # Django'ning standart get_full_name() funksiyasini to'g'rilab qo'yamiz
        return self.full_name.strip()

    def get_short_name(self):
        # get_short_name() funksiyasini ham to'g'rilaymiz
        return self.full_name.strip().split(' ')[0]

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
        return f"{self.user.username} - {self.plan.name if self.plan else 'Yoq'} ({'Aktiv' if self.is_active() else 'Aktiv emas'})"

    class Meta:
        verbose_name = "Foydalanuvchi obunasi"
        verbose_name_plural = "Foydalanuvchi obunalari"

class Purchase(models.Model):
    # YANGI, KENGAYTIRILGAN STATUSLAR
    STATUS_CHOICES = [
        ('pending',      'To\'lov kutilmoqda'), # Xarid yaratildi, foydalanuvchi yo'riqnomani ko'rdi
        ('moderation',   'Tekshirilmoqda'),   # Foydalanuvchi skrinshotni yukladi, admin tasdiqlashi kutilmoqda
        ('completed',    'Tasdiqlangan'),    # Admin yoki tizim tasdiqladi
        ('rejected',     'Rad etilgan'),      # Admin rad etdi
    ]
    PURCHASE_TYPE_CHOICES = [('package', 'Paket'), ('subscription', 'Obuna')]
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='purchases', verbose_name="Foydalanuvchi")
    purchase_type = models.CharField(max_length=20, choices=PURCHASE_TYPE_CHOICES, verbose_name="Xarid turi")
    package = models.ForeignKey(ExamPackage, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Paket")
    subscription_plan = models.ForeignKey(SubscriptionPlan, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Obuna rejasi")
    
    amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Boshlang'ich summa")
    promo_code = models.ForeignKey(PromoCode, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Promo kod")
    final_amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Yakuniy summa")
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', db_index=True, verbose_name="Holati")
    
    # YANGI QO'SHILGAN MAYDONLAR
    payment_screenshot = models.FileField(upload_to='screenshots/%Y/%m/', null=True, blank=True, verbose_name="To'lov skrinshoti")
    payment_comment = models.TextField(blank=True, null=True, verbose_name="To'lovga izoh")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True) # Avtomatik tasdiqlash uchun muhim

    def __str__(self):
        return f"Xarid #{self.id} - {self.user.username if self.user else 'Noma`lum'}"

    def fulfill(self):
        """Xarid tasdiqlanganda foydalanuvchiga xizmatni yoqish uchun yagona funksiya"""
        if self.status == 'completed': # Ikki marta bajarilishini oldini olish
            return

        if self.purchase_type == 'subscription' and self.subscription_plan:
            # Foydalanuvchiga obuna berish
            UserSubscription.objects.update_or_create(
                user=self.user,
                defaults={
                    'plan': self.subscription_plan,
                    'start_date': timezone.now(),
                    'end_date': timezone.now() + timedelta(days=self.subscription_plan.duration_days)
                }
            )
        
        if self.purchase_type == 'package' and self.package:
            # Foydalanuvchiga kreditlar berish
            user_balance, created = UserBalance.objects.get_or_create(user=self.user)
            user_balance.exam_credits += self.package.exam_credits
            user_balance.solution_view_credits += self.package.solution_view_credits_on_purchase
            user_balance.save()

        self.status = 'completed'
        self.save()
        
    class Meta:
        verbose_name = "Xarid"
        verbose_name_plural = "Xaridlar"
        ordering = ['-created_at']


# =================================================================
# 7. FLASHCARD VA LUG'AT O'RGANISH MODELLARI (YANGLANGAN)
# =================================================================

class Flashcard(models.Model):
    CONTENT_TYPE_CHOICES = [('word', 'So\'z/Ibora'), ('formula', 'Formula')]
    content_type = models.CharField(max_length=20, choices=CONTENT_TYPE_CHOICES, default='word', verbose_name="Kontent turi")
    english_content = RichTextUploadingField(verbose_name="Inglizcha kontent")
    uzbek_meaning = RichTextUploadingField(verbose_name="O'zbekcha ma'nosi")
    context_sentence = RichTextUploadingField(blank=True, null=True, verbose_name="Kontekst (gap)")
    
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='flashcards', verbose_name="Muallif")
    
    source_question = models.ForeignKey(
        'Question', 
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
        # 'Question' modelini import qilish talab qilinadi, shuning uchun 'Question' emas, 
        # balki faqat 'english_content' bo'yicha unique_together qo'shildi
        unique_together = ('english_content', 'author')

    def __str__(self):
        cleaned_english_content = bleach.clean(self.english_content, tags=[], strip=True)
        cleaned_uzbek_meaning = bleach.clean(self.uzbek_meaning, tags=[], strip=True)
        return f"{cleaned_english_content[:50]} - {cleaned_uzbek_meaning[:50]}"

class UserFlashcardStatus(models.Model):
    STATUS_CHOICES = [('not_learned', 'O\'rganilmagan'), ('learning', 'O\'rganilmoqda'), ('learned', 'O\'rganilgan')]
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='flashcard_statuses')
    flashcard = models.ForeignKey(Flashcard, on_delete=models.CASCADE, related_name='user_statuses')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='not_learned', db_index=True,
                              verbose_name="O'zlashtirish holati")
    last_reviewed_at = models.DateTimeField(null=True, blank=True, verbose_name="Oxirgi ko'rilgan vaqt")
    next_review_at = models.DateTimeField(default=timezone.now, db_index=True, verbose_name="Keyingi takrorlash vaqti")
    ease_factor = models.FloatField(default=2.5, verbose_name="Osonlik faktori (SM2)")
    review_interval = models.PositiveIntegerField(default=1, verbose_name="Takrorlash intervali (kunda)")
    
    # ✅ YANGI: Nechanchi marta to'g'ri (3 yoki undan yuqori) javob berilgani
    repetition_count = models.PositiveIntegerField(default=0, verbose_name="Muvaffaqiyatli takrorlash soni")
    # ✅ YANGI: Oxirgi marta berilgan baho (0-5)
    last_quality_rating = models.PositiveSmallIntegerField(default=5, verbose_name="Oxirgi baho (0-5)")


    class Meta:
        verbose_name = "Foydalanuvchi flashcard holati (SM2)"
        verbose_name_plural = "Foydalanuvchi flashcard holatlari (SM2)"
        unique_together = ('user', 'flashcard')

    def __str__(self):
        return f"{self.user.username} - {self.flashcard.english_content}: {self.get_status_display()}"

class FlashcardReviewLog(models.Model):
    """
    Har bir flashcard takrorlanishini loglash uchun yangi model.
    Bu chuqur statistika uchun juda muhimdir.
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='flashcard_reviews')
    flashcard = models.ForeignKey(Flashcard, on_delete=models.CASCADE, related_name='reviews_log')
    # 0 (mutlaqo unutgan) dan 5 (mukammal esladi) gacha bo'lgan baho
    quality_rating = models.PositiveSmallIntegerField(verbose_name="Sifat bahosi (0-5)")
    reviewed_at = models.DateTimeField(auto_now_add=True, verbose_name="Ko'rib chiqish vaqti")
    
    class Meta:
        verbose_name = "Flashcard takrorlash logi"
        verbose_name_plural = "Flashcard takrorlash loglari"
        ordering = ['-reviewed_at']
    
    def __str__(self):
        return f"{self.user.username} - {self.flashcard.english_content[:30]} - Baho: {self.quality_rating}"

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

# =================================================================
# 4. KONTENT VA SAVOLLAR BANKI MODELLARI
# =================================================================

class Tag(models.Model):
    name = models.CharField(max_length=100, verbose_name="Teg/Mavzu nomi")
    parent = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='children',
        verbose_name="Ota-ona teg (yuqori darajali mavzu)"
    )
    description = models.TextField(
        blank=True,
        null=True,
        verbose_name="Tavsif",
        help_text="Ushbu teg/mavzu haqida qisqacha ma'lumot"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,  # Faqat yaratilish vaqtini avtomatik saqlaydi
        verbose_name="Yaratilgan vaqt"
    )
    updated_at = models.DateTimeField(
        auto_now=True,  # Faqat yangilanish vaqtini avtomatik saqlaydi
        verbose_name="Yangilangan vaqt"
    )

    def __str__(self):
        if self.parent:
            return f"{self.parent.name} > {self.name}"
        return self.name

    class Meta:
        verbose_name = "Teg/Mavzu"
        verbose_name_plural = "Teglar/Mavzular"
        unique_together = ('name', 'parent')
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['parent']),
        ]

    def get_full_hierarchy(self):
        hierarchy = [self.name]
        current = self
        while current.parent:
            hierarchy.append(current.parent.name)
            current = current.parent
        return " > ".join(reversed(hierarchy))

class UserTagPerformance(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='tag_performances')
    tag = models.ForeignKey(Tag, on_delete=models.CASCADE, related_name='user_performances')
    correct_answers = models.PositiveIntegerField(default=0, verbose_name="To'g'ri javoblar soni")
    incorrect_answers = models.PositiveIntegerField(default=0, verbose_name="Noto'g'ri javoblar soni")
    total_time_spent = models.PositiveIntegerField(default=0, verbose_name="Sarflangan umumiy vaqt (soniya)")
    attempts_count = models.PositiveIntegerField(default=0, verbose_name="Urinishlar soni")
    average_difficulty = models.FloatField(default=0.0, verbose_name="O'rtacha qiyinlik (Rasch)")
    last_attempted_at = models.DateTimeField(null=True, blank=True, verbose_name="Oxirgi urinilgan vaqt")

    class Meta:
        verbose_name = "Foydalanuvchi teg/mavzu bo'yicha ko'rsatkichi"
        verbose_name_plural = "Foydalanuvchi teglar/mavzular bo'yicha ko'rsatkichlari"
        unique_together = ('user', 'tag')

    def __str__(self):
        return f"{self.user.username} - {self.tag.name}"

    def success_rate(self):
        total = self.correct_answers + self.incorrect_answers
        return (self.correct_answers / total * 100) if total > 0 else 0.0
    
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
    difficulty = models.FloatField(default=0.0, db_index=True, verbose_name="Qiyinlik darajasi (IRT difficulty)")
    discrimination = models.FloatField(default=1.0, verbose_name="Farqlash parametri (IRT discrimination)")
    guessing = models.FloatField(default=0.25, verbose_name="Taxmin parametri (IRT guessing)")
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
    # 'text' maydoni avvalgidek RichTextUploadingField bo'lib qoladi
    text = RichTextUploadingField(verbose_name="Variant matni", default="<p></p>") 
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='options', verbose_name="Savol")
    is_correct = models.BooleanField(default=False, verbose_name="To'g'ri javob")

    class Meta:
        verbose_name = "Javob varianti"
        verbose_name_plural = "Javob variantlari"

    def __str__(self):
        cleaned_text = strip_tags(self.text) # str uchun bleach.clean o'rniga oddiy strip_tags ishlatamiz
        return cleaned_text[:70]

    def save(self, *args, **kwargs):
        # 1. Matnni serverga saqlashdan oldin tozalash
        cleaned_text = self.text.strip()
        
        # 2. CKEditor/RichText tomonidan qo'shilgan keraksiz <p> teglarni olib tashlash
        # (Faqat matnning boshida va oxirida bo'lsa)
        if cleaned_text.startswith('<p>') and cleaned_text.endswith('</p>'):
            # Matnning boshidagi "<p>" (3 ta belgi) va oxiridagi "</p>" (4 ta belgi) ni olib tashlash
            # O'rtadagi barcha boshqa HTML teglari (masalan, <b> yoki <i>) saqlanib qoladi.
            cleaned_text = cleaned_text[3:-4].strip()
        
        self.text = cleaned_text
        super().save(*args, **kwargs)

class AnswerOptionTranslation(models.Model):
    answer_option = models.ForeignKey(AnswerOption, on_delete=models.CASCADE, related_name='translations')
    language = models.CharField(max_length=10, default='uz', verbose_name="Til")
    text = RichTextUploadingField(verbose_name="Variant matni (HTML)") # `TextField` dan `RichTextUploadingField` ga o'zgartirildi

    def save(self, *args, **kwargs):
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


class LiveExam(models.Model):
    exam = models.ForeignKey(
        'Exam',
        on_delete=models.CASCADE,
        related_name='live_exams',
        verbose_name="Bog'langan imtihon"
    )
    title = models.CharField(max_length=255, verbose_name="Imtihon nomi")
    description = models.TextField(blank=True, verbose_name="Tavsif")
    start_time = models.DateTimeField(verbose_name="Boshlanish vaqti")
    registration_deadline = models.DateTimeField(verbose_name="Ro'yxatdan o'tish oxirgi muddati")
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Narx (so'm)")
    is_active = models.BooleanField(default=True, verbose_name="Faol")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Yaratilgan vaqt")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Yangilangan vaqt")

    def __str__(self):
        return f"{self.title} ({self.start_time})"

    class Meta:
        verbose_name = "Live Imtihon"
        verbose_name_plural = "Live Imtihonlar"

    def is_registration_open(self):
        """Ro'yxatdan o'tish ochiq yoki yopiq ekanligini aniqlaydi."""
        return timezone.now() <= self.registration_deadline

    def is_exam_started(self):
        """Imtihon boshlangan yoki boshlanmaganligini aniqlaydi."""
        return timezone.now() >= self.start_time

class LiveExamRegistration(models.Model):
    live_exam = models.ForeignKey(
        LiveExam,
        on_delete=models.CASCADE,
        related_name='registrations',
        verbose_name="Live Imtihon"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='live_exam_registrations',
        verbose_name="Foydalanuvchi"
    )
    purchase = models.OneToOneField(
        'Purchase',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='live_exam_registration',
        verbose_name="Bog'langan xarid"
    )
    payment_status = models.CharField(
        max_length=20,
        choices=(('pending', "Kutilmoqda"), ('completed', "To'langan"), ('failed', "Muvaffaqiyatsiz")),
        default='pending',
        verbose_name="To'lov holati"
    )
    payment_amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="To'langan summa")
    registered_at = models.DateTimeField(auto_now_add=True, verbose_name="Ro'yxatdan o'tgan vaqt")

    def __str__(self):
        return f"{self.user.username} - {self.live_exam.title}"
    class Meta:
        verbose_name = "Live Imtihon Ro'yxati"
        verbose_name_plural = "Live Imtihon Ro'yxatlari"
        unique_together = ('live_exam', 'user')

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
        ('read_write_m1', 'Reading'), ('read_write_m2', 'Writing and Language'), ('math_no_calc', 'Math (No Calculator)'),
        ('math_calc', 'Math (Calculator)'))
    section_type = models.CharField(max_length=30, choices=SECTION_TYPES, verbose_name="Bo‘lim turi")
    duration_minutes = models.PositiveIntegerField(verbose_name="Davomiyligi (minut)")
    max_questions = models.PositiveIntegerField(verbose_name="Maksimal savollar soni")
    module_number = models.PositiveIntegerField(default=1, verbose_name="Modul raqami")
    order = models.PositiveIntegerField(default=0, verbose_name="Tartib raqami")
    static_questions = models.ManyToManyField(Question, through='ExamSectionStaticQuestion',
                                             related_name='static_exam_sections', blank=True,
                                             verbose_name="Statik savollar")
    min_difficulty = models.FloatField(null=True, blank=True, verbose_name="Minimal qiyinlik (IRT)")
    max_difficulty = models.FloatField(null=True, blank=True, verbose_name="Maksimal qiyinlik (IRT)")

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
    questions_count = models.PositiveIntegerField(default=0, verbose_name="Savollar soni")

    class Meta:
        verbose_name = "Bo‘lim ichki mavzu qoidasi (Adaptiv)"
        verbose_name_plural = "Bo‘lim ichki mavzu qoidalari (Adaptiv)"
        
    def __str__(self):
        return f"{self.subtopic.name}: {self.questions_count} ta savol"

class ExamSectionTagRule(models.Model):
    exam_section = models.ForeignKey(ExamSection, on_delete=models.CASCADE, related_name='tag_rules', verbose_name="Bo‘lim")
    tag = models.ForeignKey(Tag, on_delete=models.CASCADE, verbose_name="Teg/Mavzu")
    questions_count = models.PositiveIntegerField(verbose_name="Savollar soni")

    class Meta:
        verbose_name = "Bo‘lim teg qoidasi (Adaptiv)"
        verbose_name_plural = "Bo‘lim teg qoidalari (Adaptiv)"
        unique_together = ('exam_section', 'tag')

    def __str__(self):
        return f"{self.exam_section} - {self.tag.name}: {self.questions_count} ta savol"
    
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

    # Bu siz so'ragan maydon
    mode = models.CharField(max_length=50, default='exam', verbose_name="Imtihon rejimi")

    class Meta:
        verbose_name = "Foydalanuvchi urinishi"
        verbose_name_plural = "Foydalanuvchi urinishlari"

    def __str__(self):
        return f"{self.user.username} - {self.exam.title} ({self.mode})"

    def generate_adaptive_section(self, section_order):
        """Adaptiv imtihon uchun 2-modul savollarini 1-modul natijasi asosida tanlash."""
        if self.exam.exam_type != 'adaptive' or section_order != 2:
            return

        first_section = self.section_attempts.filter(section__order=1).first()
        if not first_section or not first_section.is_completed:
            raise ValidationError("2-modulni boshlash uchun 1-modul yakunlanishi kerak.")

        first_section_ability = first_section.ability_estimate

        second_section = self.section_attempts.filter(section__order=2).first()
        if second_section:
            if first_section_ability > 1.0:
                min_diff = 1.0
                max_diff = 3.0
            else:
                min_diff = -3.0
                max_diff = 1.0

            rules = ExamSectionTagRule.objects.filter(exam_section=second_section.section)
            for rule in rules:
                questions = Question.objects.filter(tags=rule.tag, difficulty__gte=min_diff, difficulty__lte=max_diff).order_by('?')[:rule.questions_count]
                second_section.questions.add(*questions)

class UserAttemptSection(models.Model):
    attempt = models.ForeignKey(UserAttempt, on_delete=models.CASCADE, related_name='section_attempts',
                                 verbose_name="Urinish")
    section = models.ForeignKey(ExamSection, on_delete=models.CASCADE, verbose_name="Bo‘lim")
    score = models.PositiveIntegerField(default=0, verbose_name="Bo‘lim balli")
    ability_estimate = models.FloatField(default=0.0, verbose_name="Taxminiy qobiliyat (IRT)")
    correct_answers_count = models.PositiveIntegerField(default=0, verbose_name="To'g'ri javoblar soni")
    incorrect_answers_count = models.PositiveIntegerField(default=0, verbose_name="Noto'g'ri javoblar soni")
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name="Tugatilgan vaqti")
    questions = models.ManyToManyField(Question, related_name='attempted_in_sections', blank=True,
                                       verbose_name="Berilgan savollar")
    remaining_time_seconds = models.PositiveIntegerField(null=True, blank=True, verbose_name="Qolgan vaqt (soniya)")
    is_completed = models.BooleanField(default=False, verbose_name="Yakunlangan")

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
    is_marked_for_review = models.BooleanField(default=False, verbose_name="Ko'rib chiqish uchun belgilangan")
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
    TRIGGER_TYPES = [
        ('exam_completed', 'Imtihon yakunlandi'),  # Misol: exam_count=5 (5 ta imtihon yakunlagan bo'lsa)
        ('score_achieved', 'Ball yetkazildi'),     # Misol: min_score=80 (80 ball yetkazgan bo'lsa)
        ('streak', 'Ketma-ketlik'),                # Misol: streak_days=7 (7 kun ketma-ket mashq qilgan bo'lsa)
        ('flashcard_learned', 'Flashcard o\'rganildi'),  # Misol: flashcard_count=50 (50 ta flashcard o'rganilgan bo'lsa)
        # Yangi meyorlar qo'shildi
        ('daily_high_score', 'Eng yaxshi kunlik natija'),  # Kunlik eng yuqori ball
        ('referral', 'Do\'stlarni taklif qilish'),         # Taklif qilingan do'stlar soni
    ]
    title = models.CharField(max_length=100, unique=True, verbose_name="Nishon nomi")
    description = models.TextField(verbose_name="Tavsif")
    icon = models.ImageField(upload_to='badges/', verbose_name="Nishon ikonasi")
    trigger_type = models.CharField(
        max_length=50,
        choices=TRIGGER_TYPES,
        verbose_name="Meyor turi",
        help_text="Nishon qachon berilishini tanlang"
    )
    # Har bir meyor uchun alohida maydonlar (JSON emas, oddiy kiritish)
    exam_count = models.PositiveIntegerField(
        default=0,
        blank=True,
        verbose_name="Imtihonlar soni (imtihon yakunlash meyorida)",
        help_text="Agar 'Imtihon yakunlandi' tanlangan bo'lsa, shu son yetkazilsa nishon beriladi"
    )
    min_score = models.PositiveIntegerField(
        default=0,
        blank=True,
        verbose_name="Minimal ball (ball yetkazish meyorida)",
        help_text="Agar 'Ball yetkazildi' tanlangan bo'lsa, shu balldan yuqori bo'lsa nishon beriladi"
    )
    streak_days = models.PositiveIntegerField(
        default=0,
        blank=True,
        verbose_name="Ketma-ket kunlar soni (ketma-ketlik meyorida)",
        help_text="Agar 'Ketma-ketlik' tanlangan bo'lsa, shu kun ketma-ket mashq qilinsa nishon beriladi"
    )
    flashcard_count = models.PositiveIntegerField(
        default=0,
        blank=True,
        verbose_name="Flashcardlar soni (flashcard o'rganish meyorida)",
        help_text="Agar 'Flashcard o'rganildi' tanlangan bo'lsa, shu son o'rganilsa nishon beriladi"
    )
    # Yangi meyorlar uchun maydonlar
    daily_min_score = models.PositiveIntegerField(
        default=0,
        blank=True,
        verbose_name="Kunlik minimal ball (eng yaxshi kunlik natija meyorida)"
    )
    referral_count = models.PositiveIntegerField(
        default=0,
        blank=True,
        verbose_name="Taklif qilingan do'stlar soni (referral meyorida)"
    )

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

class LeaderboardEntry(models.Model):
    LEADERBOARD_TYPES = [
        ('effort', 'Mehnat bo\'yicha (ko\'p imtihon ishlaganlar)'),
        ('performance', 'Natija bo\'yicha (yuqori ball olganlar)'),
    ]
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='leaderboard_entries')
    leaderboard_type = models.CharField(max_length=20, choices=LEADERBOARD_TYPES, verbose_name="Leaderboard turi")
    week_number = models.PositiveIntegerField(verbose_name="Hafta raqami")  # Haftalik reset uchun
    score = models.PositiveIntegerField(default=0, verbose_name="Ball yoki ko'rsatkich")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Leaderboard kirishi"
        verbose_name_plural = "Leaderboard kirishlari"
        unique_together = ('user', 'leaderboard_type', 'week_number')
        indexes = [
            models.Index(fields=['leaderboard_type', 'week_number', '-score']),
        ]
        ordering = ['-score']

    def __str__(self):
        return f"{self.user.username} - {self.get_leaderboard_type_display()} (Hafta {self.week_number}): {self.score}"

class UserMissionProgress(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='mission_progress')
    exam_attempts_completed = models.PositiveIntegerField(default=0, verbose_name="Yakunlangan exam mode urinishlari")
    study_attempts_completed = models.PositiveIntegerField(default=0, verbose_name="Yakunlangan study mode urinishlari")
    highest_score = models.PositiveIntegerField(default=0, verbose_name="Eng yuqori ball (exam mode)")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Foydalanuvchi missiya progressi"
        verbose_name_plural = "Foydalanuvchi missiya progresslari"

    def __str__(self):
        return f"{self.user.username} - Exam: {self.exam_attempts_completed}, Study: {self.study_attempts_completed}"


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