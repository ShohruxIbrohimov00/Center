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
from datetime import date
from django.utils.html import strip_tags 
from django.utils.translation import gettext_lazy as _
import bleach
import re
import math
from utils.irt import ThreeParameterLogisticModel

class Center(models.Model):
    """
    Har bir alohida mijoz (O'quv Markazi) uchun asosiy model (Tenant).
    """
    name = models.CharField(max_length=255, verbose_name="Markaz nomi")
    slug = models.SlugField(unique=True, help_text="Sayt URL uchun unikal nom")
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='owned_centers',
        verbose_name="O'qituvchi"
    )
    is_active = models.BooleanField(default=True, verbose_name="Aktiv (To'lov muddati o'tmagan)")

    @property
    def is_subscription_valid(self):
        latest_sub = self.subscriptions.filter(is_active=True).order_by('-end_date').first()
        if latest_sub:
            return latest_sub.end_date >= date.today()
        return False

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "O'quv Markazi"
        verbose_name_plural = "O'quv Markazlari"

class Group(models.Model):
    """
    O'qituvchilar tomonidan tashkil etiladigan o'quv guruhlari.
    """
    name = models.CharField(max_length=150, verbose_name="Guruh nomi")
    center = models.ForeignKey(
        'Center', 
        on_delete=models.CASCADE, 
        related_name='groups', 
        verbose_name="O'quv Markazi"
    )
    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='teaching_groups',
        limit_choices_to=models.Q(role='teacher') | models.Q(role='center_admin'),
        verbose_name="Biriktirilgan O'qituvchi"
    )
    students = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='enrolled_groups',
        limit_choices_to={'role': 'student'},
        blank=True,
        verbose_name="Guruh o'quvchilari"
    )
    is_active = models.BooleanField(default=True, verbose_name="Aktiv guruh")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.center.name})"
    
    class Meta:
        verbose_name = "Guruh"
        verbose_name_plural = "Guruhlar"
        unique_together = ('center', 'teacher', 'name')

class Subscription(models.Model):
    """
    O'quv markazining saytdan foydalanish muddatini boshqaradi.
    """
    center = models.ForeignKey(
        Center,
        on_delete=models.CASCADE,
        related_name='subscriptions',
        verbose_name="O'quv Markazi"
    )
    start_date = models.DateField(auto_now_add=True, verbose_name="Boshlanish sanasi")
    end_date = models.DateField(verbose_name="Tugash sanasi")
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="To'lov miqdori")
    is_active = models.BooleanField(default=True, verbose_name="To'lov aktivmi?")

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.center.is_active = self.center.is_subscription_valid
        self.center.save()

    def __str__(self):
        return f"{self.center.name} - {self.end_date} gacha"
    
    class Meta:
        verbose_name = "Obuna"
        verbose_name_plural = "Obunalar"

class SystemConfiguration(models.Model):
    """
    Tizimning global sozlamalarini saqlash uchun yagona model (Singleton).
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
    payment_card_number = models.CharField(max_length=20, help_text="To'lov qabul qilinadigan plastik karta raqami. Format: 8600 1234 ...")
    payment_card_holder = models.CharField(max_length=100, help_text="Karta egasining ismi va familiyasi. Masalan: ALI VALIYEV")
    manager_phone_number = models.CharField(max_length=20, help_text="To'lovni tezkor tasdiqlash uchun menejer telefon raqami. Format: +998901234567")
    manager_telegram_username = models.CharField(max_length=100, blank=True, help_text="Menejerning telegram username'i (masalan, @menejer_username)")

    def __str__(self):
        return "Sayt Sozlamalari"

    class Meta:
        verbose_name = "Sayt Sozlamalari"
        verbose_name_plural = "Sayt Sozlamalari"

class CustomUser(AbstractUser):
    first_name = None
    last_name = None
    full_name = models.CharField(max_length=255, verbose_name="To'liq ism (F.I.Sh)")
    email = models.EmailField(unique=True, verbose_name="Elektron pochta")
    phone_number = models.CharField(max_length=20, unique=True, null=True, blank=True, verbose_name="Telefon raqami")
    center = models.ForeignKey(
        Center,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='members',
        verbose_name="O'quv Markazi"
    )
    ROLE_CHOICES = [
        ('student', "O'quvchi"),
        ('teacher', "O'qituvchi"),
        ('center_admin', "Markaz Admini"), 
        ('admin', "Platforma Super Admini"), 
    ]
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='student', verbose_name="Foydalanuvchi roli")
    profile_picture = models.ImageField(upload_to='profile_pics/', null=True, blank=True, verbose_name="Profil rasmi")
    bio = models.TextField(max_length=500, blank=True, verbose_name="O'zi haqida")
    ability = models.FloatField(default=0.0, verbose_name="Foydalanuvchi qobiliyati (Rasch)")
    teacher = models.ForeignKey(
        'self', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        limit_choices_to=models.Q(role='teacher') | models.Q(role='center_admin'),
        related_name='students',
        verbose_name="Biriktirilgan Ustoz/Admin"
    )
    is_approved = models.BooleanField(default=True, verbose_name="Tasdiqlangan")
    is_banned = models.BooleanField(default=False, verbose_name="Bloklangan")

    USERNAME_FIELD = 'username' 
    REQUIRED_FIELDS = ['email', 'full_name'] 

    def is_center_active(self):
        if self.center:
            return self.center.is_subscription_valid
        return True

    def __str__(self):
        return self.username

    def get_full_name(self):
        return self.full_name.strip()

    def get_short_name(self):
        return self.full_name.strip().split(' ')[0]
    
    def has_active_subscription(self):
        """
        Foydalanuvchining aktiv obunasi bor-yo'qligini tekshiradi.
        """
        # UserSubscription modelini import qilingan deb hisoblaymiz
        try:
            from .models import UserSubscription # Agar UserSubscription shu models.py da bo'lsa
        except ImportError:
            # Agar boshqa joyda bo'lsa, to'g'ri joydan import qiling
            return False 

        return UserSubscription.objects.filter(
            user=self,
            end_date__gt=timezone.now() # Tugash sanasi hozirdan katta bo'lsa
        ).exists()
    
    class Meta:
        verbose_name = "Foydalanuvchi"
        verbose_name_plural = "Foydalanuvchilar"

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
    center = models.ForeignKey(
        'Center',
        on_delete=models.CASCADE,
        related_name='promo_codes',
        verbose_name="O'quv Markazi"
    )

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
    center = models.ForeignKey(
        'Center',
        on_delete=models.CASCADE,
        related_name='exam_packages',
        verbose_name="O'quv Markazi"
    )

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
    STATUS_CHOICES = [
        ('pending', 'To\'lov kutilmoqda'),
        ('moderation', 'Tekshirilmoqda'),
        ('completed', 'Tasdiqlangan'),
        ('rejected', 'Rad etilgan'),
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
    payment_screenshot = models.FileField(upload_to='screenshots/%Y/%m/', null=True, blank=True, verbose_name="To'lov skrinshoti")
    payment_comment = models.TextField(blank=True, null=True, verbose_name="To'lovga izoh")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Xarid #{self.id} - {self.user.username if self.user else 'Noma`lum'}"

    def fulfill(self):
        if self.status == 'completed':
            return
        if self.purchase_type == 'subscription' and self.subscription_plan:
            UserSubscription.objects.update_or_create(
                user=self.user,
                defaults={
                    'plan': self.subscription_plan,
                    'start_date': timezone.now(),
                    'end_date': timezone.now() + timedelta(days=self.subscription_plan.duration_days)
                }
            )
        if self.purchase_type == 'package' and self.package:
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

class Flashcard(models.Model):
    """
    Lug'at yoki formulalarni saqlash uchun model. CKEditor yordamida kiritilgan matnlar
    apostrof muammolarini bartaraf etish uchun tozalangan.
    """
    
    CONTENT_TYPE_CHOICES = [
        ('word', _("So'z/Ibora")), 
        ('formula', _("Formula"))
    ]
    
    # --- Asosiy Maydonlar ---
    content_type = models.CharField(
        max_length=20, 
        choices=CONTENT_TYPE_CHOICES, 
        default='word', 
        verbose_name=_("Kontent turi")
    )
    
    english_content = RichTextUploadingField(verbose_name=_("Inglizcha kontent"))
    uzbek_meaning = RichTextUploadingField(verbose_name=_("O'zbekcha ma'nosi"))
    context_sentence = RichTextUploadingField( blank=True,  null=True,  verbose_name=_("Kontekst (gap)"))
    author = models.ForeignKey( settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='flashcards', verbose_name=_("Muallif"))
    source_question = models.ForeignKey( 'Question', on_delete=models.SET_NULL, related_name='associated_flashcards', verbose_name=_("Manba-savol"), null=True, blank=True)
    center = models.ForeignKey(
        'Center', 
        on_delete=models.CASCADE, 
        related_name='flashcards', 
        verbose_name=_("Tegishli Markaz"),
        null=True
    )

    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = _("Flashcard (lug'at)")
        verbose_name_plural = _("Flashcardlar (lug'atlar)")
        unique_together = ('english_content', 'center') 
        ordering = ['english_content']

    # --- Yordamchi Metod ---
    def _clean_apostrophes(self, text):
        """Noto'g'ri apostrof turlarini standart tirnoqqa (') almashtiradi."""
        if not text:
            return text
            
        # Eng keng tarqalgan noto'g'ri belgilarni standart ' ga almashtirish
        text = str(text)
        text = text.replace('‘', "'")  # Chap bitta tirnoq
        text = text.replace('’', "'")  # O'ng bitta tirnoq
        text = text.replace('`', "'")  # Backtick
        return text

    # --- Saqlash Metodi (Bazaga saqlashdan oldin tozalash) ---
    def save(self, *args, **kwargs):
        """Ma'lumotlar bazasiga saqlashdan oldin CKEditor matnlaridagi
        O'zbekcha apostrof xatolarini to'g'irlaydi."""
        
        # 1. O'zbekcha ma'nodagi apostroflarni to'g'irlash
        if self.uzbek_meaning:
            self.uzbek_meaning = self._clean_apostrophes(self.uzbek_meaning)
            
        # 2. Inglizcha kontentdagi apostroflarni to'g'irlash
        if self.english_content:
            self.english_content = self._clean_apostrophes(self.english_content)
            
        # 3. Kontekst gapdagi apostroflarni to'g'irlash
        if self.context_sentence:
            self.context_sentence = self._clean_apostrophes(self.context_sentence)
            
        super().save(*args, **kwargs)

    # --- Ko'rsatish Metodi (Select2/Admin uchun tozalash) ---
    def __str__(self):
        """Obyektni odam o'qishi uchun qisqa va toza formatda qaytaradi."""
        
        # 1. HTML teglarini olib tashlash (RichTextUploadingField uchun)
        cleaned_english_content = bleach.clean(self.english_content or '', tags=[], strip=True)
        cleaned_uzbek_meaning = bleach.clean(self.uzbek_meaning or '', tags=[], strip=True)
        
        # 2. Tozalangan matndagi noto'g'ri apostroflarni standartlashtirish
        cleaned_english_content = self._clean_apostrophes(cleaned_english_content)
        cleaned_uzbek_meaning = self._clean_apostrophes(cleaned_uzbek_meaning)
        
        # 3. Natijani qaytarish (matn uzunligini qisqartirish)
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
    repetition_count = models.PositiveIntegerField(default=0, verbose_name="Muvaffaqiyatli takrorlash soni")
    last_quality_rating = models.PositiveSmallIntegerField(default=5, verbose_name="Oxirgi baho (0-5)")

    class Meta:
        verbose_name = "Foydalanuvchi flashcard holati (SM2)"
        verbose_name_plural = "Foydalanuvchi flashcard holatlari (SM2)"
        unique_together = ('user', 'flashcard')

    def __str__(self):
        return f"{self.user.username} - {self.flashcard.english_content}: {self.get_status_display()}"

class FlashcardReviewLog(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='flashcard_reviews')
    flashcard = models.ForeignKey(Flashcard, on_delete=models.CASCADE, related_name='reviews_log')
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
    center = models.ForeignKey(
        'Center', 
        on_delete=models.CASCADE, 
        related_name='flashcard_decks', 
        verbose_name="Tegishli Markaz",
        null=True
    )

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
    is_exam_review = models.BooleanField(default=True, verbose_name="Imtihon takrorlash to'plami")
    created_at = models.DateTimeField(auto_now_add=True)
    center = models.ForeignKey(
        'Center', 
        on_delete=models.CASCADE, 
        related_name='flashcard_exams', 
        verbose_name="Tegishli Markaz",
        null=True
    )

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
    center = models.ForeignKey(
        'Center', 
        on_delete=models.CASCADE, 
        related_name='tags', 
        verbose_name="Tegishli Markaz",
        null=True
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Yaratilgan vaqt"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Yangilangan vaqt"
    )

    def __str__(self):
        if self.parent:
            return f"{self.parent.name} > {self.name}"
        return self.name

    class Meta:
        verbose_name = "Teg/Mavzu"
        verbose_name_plural = "Teglar/Mavzular"
        unique_together = ('name', 'parent', 'center')
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
    center = models.ForeignKey(
        'Center', 
        on_delete=models.CASCADE, 
        related_name='topics', 
        verbose_name="Tegishli Markaz",
        null=True
    )

    class Meta:
        verbose_name = "Umumiy mavzu"
        verbose_name_plural = "Umumiy mavzular"
        ordering = ['order']
        unique_together = ('name', 'teacher', 'center')

    def __str__(self):
        return self.name

class Subtopic(models.Model):
    name = models.CharField(max_length=200, verbose_name="Ichki mavzu nomi")
    topic = models.ForeignKey(Topic, on_delete=models.CASCADE, related_name='subtopics', verbose_name="Umumiy mavzu")
    order = models.PositiveIntegerField(default=0, verbose_name="Tartib raqami")
    center = models.ForeignKey(
        'Center', 
        on_delete=models.CASCADE, 
        related_name='subtopics', 
        verbose_name="Tegishli Markaz",
        null=True
    )

    class Meta:
        verbose_name = "Ichki mavzu"
        verbose_name_plural = "Ichki mavzular"
        ordering = ['order']
        unique_together = ('name', 'topic', 'center')

    def __str__(self):
        return f"{self.name} ({self.topic.name})"

class Passage(models.Model):
    title = models.CharField(max_length=255, verbose_name="Matn sarlavhasi")
    content = RichTextUploadingField(verbose_name="Matn (HTML)")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='passages',
                              verbose_name="Muallif")
    created_at = models.DateTimeField(auto_now_add=True)
    center = models.ForeignKey(
        'Center', 
        on_delete=models.CASCADE, 
        related_name='passages', 
        verbose_name="Tegishli Markaz",
        null=True
    )

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
    text = RichTextUploadingField(verbose_name="Savol matni", default="<p></p>")
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
    center = models.ForeignKey(
        'Center', 
        on_delete=models.CASCADE, 
        related_name='questions', 
        verbose_name="Tegishli Markaz",
        null=True
    )
    flashcards = models.ManyToManyField('Flashcard', related_name='questions', blank=True, verbose_name="Savolga oid flashcardlar")
    ANSWER_CHOICES = (('single', 'Yagona tanlov'), ('multiple', 'Ko\'p tanlov'), ('short_answer', 'Qisqa javob'))
    answer_format = models.CharField(max_length=20, choices=ANSWER_CHOICES, default='single', verbose_name="Javob formati")
    difficulty = models.FloatField(default=0.0, db_index=True, verbose_name="Qiyinlik darajasi (IRT difficulty)")
    discrimination = models.FloatField(default=1.0, verbose_name="Farqlash parametri (IRT discrimination)")
    guessing = models.FloatField(default=0.25, verbose_name="Taxmin parametri (IRT guessing)")
    difficulty_level = models.ForeignKey(RaschDifficultyLevel, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Qiyinlik darajasi")
    STATUS_CHOICES = (('draft', 'Qoralama'), ('published', 'Nashr qilingan'), ('archived', 'Arxivlangan'))
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft', db_index=True, verbose_name="Holati")
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

class QuestionSolution(models.Model):
    question = models.OneToOneField('Question', on_delete=models.CASCADE, related_name='solution', verbose_name="Savol")
    hint = RichTextUploadingField(blank=True, null=True, verbose_name="Yechim uchun maslahat")
    detailed_solution = RichTextUploadingField(blank=True, null=True, verbose_name="Yechim")
    
    class Meta:
        verbose_name = "Savol yechimi"
        verbose_name_plural = "Savollar yechimi"

    def __str__(self):
        return f"Savol: {self.question.id} yechimi"

class AnswerOption(models.Model):
    text = RichTextUploadingField(verbose_name="Variant matni", default="<p></p>")
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='options', verbose_name="Savol")
    is_correct = models.BooleanField(default=False, verbose_name="To'g'ri javob")

    class Meta:
        verbose_name = "Javob varianti"
        verbose_name_plural = "Javob variantlari"

    def __str__(self):
        cleaned_text = strip_tags(self.text)
        return cleaned_text[:70]

    def save(self, *args, **kwargs):
        cleaned_text = self.text.strip()
        if cleaned_text.startswith('<p>') and cleaned_text.endswith('</p>'):
            cleaned_text = cleaned_text[3:-4].strip()
        self.text = cleaned_text
        super().save(*args, **kwargs)

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

class Exam(models.Model):
    teacher = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name="Ustoz")
    title = models.CharField(max_length=200, verbose_name="Test nomi")
    is_subject_exam = models.BooleanField(
        default=False, 
        verbose_name="Mavzu testi", 
        help_text="Agar bu imtihon to'liq SAT sinovi emas, balki biror mavzu bo'yicha test bo'lsa"
    )
    passing_percentage = models.PositiveIntegerField(
        default=60, 
        verbose_name="O'tish foizi (%)",
        help_text="O'quvchi keyingi darsga o'tishi uchun to'plashi kerak bo'lgan minimal foiz (0-100)"
    )
    description = models.TextField(verbose_name="Tavsif", blank=True, null=True)
    is_premium = models.BooleanField(default=True, verbose_name="Pullik imtihon")
    is_active = models.BooleanField(default=True, verbose_name="Aktiv")
    created_at = models.DateTimeField(auto_now_add=True)
    center = models.ForeignKey(
        'Center', 
        on_delete=models.CASCADE, 
        related_name='exams', 
        verbose_name="Tegishli Markaz",
        null=True
    )
    sections = models.ManyToManyField(
        'ExamSection',
        through='ExamSectionOrder', 
        related_name='exams',
        verbose_name="Imtihon bo‘limlari"
    )

    class Meta:
        verbose_name = "Imtihon"
        verbose_name_plural = "Imtihonlar"
        unique_together = ('title', 'center')
        ordering = ['title']

    def get_or_create_flashcard_exam(self):
        if hasattr(self, 'flashcard_exam'):
            return getattr(self, 'flashcard_exam', None)
        question_ids = ExamSectionStaticQuestion.objects.filter(
            exam_section__in=self.sections.all() 
        ).values_list('question_id', flat=True).distinct()
        flashcard_ids = Flashcard.objects.filter(
            questions__id__in=question_ids
        ).values_list('id', flat=True).distinct()
        if not flashcard_ids:
            return None
        flashcard_exam, created = FlashcardExam.objects.get_or_create(
            source_exam=self,
            defaults={'title': f"{self.title} - Flashcard Mashg'uloti"}
        )
        flashcard_exam.flashcards.set(flashcard_ids)
        return flashcard_exam
    
    def __str__(self):
        return self.title

class ExamSection(models.Model):
    name = models.CharField(max_length=150, unique=True, verbose_name="Bo‘lim nomi", 
                           help_text="Masalan: Qiyin darajali Writing, Yengil darajali Math-Calc.")
    SECTION_TYPES = (
        ('subject_test', 'Mavzu testi'),
        ('read_write_m1', 'Reading'),
        ('read_write_m2', 'Writing and Language'),
        ('math_no_calc', 'Math (No Calculator)'),
        ('math_calc', 'Math (Calculator)'),
    )
    section_type = models.CharField(max_length=30, choices=SECTION_TYPES, verbose_name="Bo‘lim turi")
    duration_minutes = models.PositiveIntegerField(verbose_name="Davomiyligi (minut)")
    max_questions = models.PositiveIntegerField(verbose_name="Maksimal savollar soni")
    static_questions = models.ManyToManyField('Question', through='ExamSectionStaticQuestion',
                                            related_name='static_exam_sections', blank=True,
                                            verbose_name="Statik savollar")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    min_difficulty = models.FloatField(null=True, blank=True, verbose_name="Minimal qiyinlik (IRT)")
    max_difficulty = models.FloatField(null=True, blank=True, verbose_name="Maksimal qiyinlik (IRT)")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Yaratilgan vaqti")
    center = models.ForeignKey(
        'Center', 
        on_delete=models.CASCADE, 
        related_name='exam_sections', 
        verbose_name="Tegishli Markaz",
        null=True
    )

    class Meta:
        verbose_name = "Bo‘lim shabloni"
        verbose_name_plural = "Bo‘lim shablonlari"
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.get_section_type_display()})"

class ExamSectionOrder(models.Model):
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name='examsectionorder')
    exam_section = models.ForeignKey(ExamSection, on_delete=models.CASCADE)
    order = models.PositiveIntegerField(verbose_name="Tartib raqami")
    
    class Meta:
        unique_together = ('exam', 'order')
        ordering = ['order']
        verbose_name = "Imtihon bo‘limi tartibi"

    def __str__(self):
        return f"{self.exam.title} - {self.order}-o‘rin: {self.exam_section.name}"

class ExamSectionStaticQuestion(models.Model):
    exam_section = models.ForeignKey(ExamSection, on_delete=models.CASCADE)
    question = models.ForeignKey('Question', on_delete=models.CASCADE)
    question_number = models.PositiveIntegerField(verbose_name="Savol tartib raqami")

    class Meta:
        ordering = ['question_number']
        unique_together = ('exam_section', 'question')
        verbose_name = "Bo'limning statik savoli"
        verbose_name_plural = "Bo'limning statik savollari"

class UserAttempt(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='attempts',
                            verbose_name="Foydalanuvchi")
    exam = models.ForeignKey('Exam', on_delete=models.CASCADE, verbose_name="Imtihon", related_name='user_attempts')
    started_at = models.DateTimeField(auto_now_add=True, verbose_name="Boshlangan vaqti")
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name="Tugatilgan vaqti")
    is_completed = models.BooleanField(default=False, db_index=True, verbose_name="Tugatilgan")
    final_ebrw_score = models.PositiveIntegerField(null=True, blank=True, verbose_name="Yakuniy EBRW balli")
    final_math_score = models.PositiveIntegerField(null=True, blank=True, verbose_name="Yakuniy Math balli")
    final_total_score = models.PositiveIntegerField(null=True, blank=True, verbose_name="Yakuniy umumiy ball")
    correct_percentage = models.FloatField(default=0.0, verbose_name="To'g'ri javoblar foizi")
    mode = models.CharField(max_length=50, default='exam', verbose_name="Imtihon rejimi")

    class Meta:
        verbose_name = "Foydalanuvchi urinishi"
        verbose_name_plural = "Foydalanuvchi urinishlari"

    def __str__(self):
        return f"{self.user.username} - {self.exam.title} ({self.mode})"

    def is_passed(self):
        if self.exam.is_subject_exam:
            return self.correct_percentage >= self.exam.passing_percentage
        return True

class UserAttemptSection(models.Model):
    attempt = models.ForeignKey(UserAttempt, on_delete=models.CASCADE, related_name='section_attempts',
                              verbose_name="Urinish")
    section = models.ForeignKey('ExamSection', on_delete=models.CASCADE, verbose_name="Bo‘lim")
    score = models.PositiveIntegerField(default=0, verbose_name="Bo‘lim balli")
    correct_answers_count = models.PositiveIntegerField(default=0, verbose_name="To'g'ri javoblar soni")
    incorrect_answers_count = models.PositiveIntegerField(default=0, verbose_name="Noto'g'ri javoblar soni")
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name="Tugatilgan vaqti")
    questions = models.ManyToManyField(
        'Question', 
        through='UserAttemptQuestion', 
        related_name='attempted_in_sections', 
        blank=True,
        verbose_name="Berilgan savollar"
    )
    remaining_time_seconds = models.PositiveIntegerField(null=True, blank=True, verbose_name="Qolgan vaqt (soniya)")
    is_completed = models.BooleanField(default=False, verbose_name="Yakunlangan")

    class Meta:
        verbose_name = "Bo‘lim urinishi"
        verbose_name_plural = "Bo‘lim urinishlari"
        unique_together = ('attempt', 'section')

    def __str__(self):
        return f"{self.attempt} - {self.section}"

class UserAttemptQuestion(models.Model):
    attempt_section = models.ForeignKey('UserAttemptSection', on_delete=models.CASCADE)
    question = models.ForeignKey('Question', on_delete=models.CASCADE)
    question_number = models.PositiveIntegerField(
        verbose_name="Savol tartibi",
        default=1
    )
    
    class Meta:
        verbose_name = "Urinish savoli tartibi"
        verbose_name_plural = "Urinish savollari tartibi"
        unique_together = ('attempt_section', 'question')
        ordering = ['question_number']

    def __str__(self):
        return f"S-{self.attempt_section.id} Q-{self.question_number}: {self.question.id}"

class UserAnswer(models.Model):
    attempt_section = models.ForeignKey(UserAttemptSection, on_delete=models.CASCADE, related_name='user_answers')
    question = models.ForeignKey('Question', on_delete=models.CASCADE)
    selected_options = models.ManyToManyField('AnswerOption', blank=True, verbose_name="Tanlangan variantlar")
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
# 5.5. Kurs va kurs mavzulari va mavzu testlar ishlash
# =================================================================
from django.db import models
from django.conf import settings
from django.utils import timezone
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey

COURSE_TYPE_CHOICES = (
    ('online', 'Online Kurs'),
    ('offline', 'Offline Kurs (An\'anaviy)'),
)

ONLINE_LESSON_FLOW_CHOICES = (
    ('self_paced', 'Ixtiyoriy (Talaba o\'zi boshqaradi)'),
    ('scheduled', 'Jadval asosida (Muddatli/Vaqtli)'),
)

RESOURCE_TYPE_CHOICES = (
    ('video', 'Videodars Linki'),
    ('task', 'Vazifa/Amaliyot Linki'),
    ('solution_video', 'Yechim Videolinki'),
    ('solution_file', 'Yechim Fayli Linki/Yuklama'),
    ('other', 'Boshqa Resurs (PDF, Google Doc va h.k.)'),
)

class Course(models.Model):
    title = models.CharField(max_length=200, verbose_name="Kurs nomi")
    description = models.TextField(verbose_name="Tavsif", blank=True, null=True)
    teacher = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, verbose_name="Ustoz")
    course_type = models.CharField(
        max_length=10, 
        choices=COURSE_TYPE_CHOICES, 
        default='online', 
        verbose_name="Kurs turi"
    )
    online_lesson_flow = models.CharField(
        max_length=10, 
        choices=ONLINE_LESSON_FLOW_CHOICES, 
        default='self_paced', 
        verbose_name="Online darslar turi",
        help_text="'Ixtiyoriy'da tezlik talabaga bog'liq, 'Jadval asosida'da vaqt cheklangan."
    )
    is_premium = models.BooleanField(default=True, verbose_name="Pullik kurs")
    is_active = models.BooleanField(default=True, verbose_name="Aktiv")
    price = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0.00,
        verbose_name="Kurs narxi"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    center = models.ForeignKey(
        'Center', 
        on_delete=models.CASCADE, 
        related_name='courses', 
        verbose_name="Tegishli Markaz",
        null=True
    )
    groups = models.ManyToManyField(
        'Group',
        related_name='courses', 
        blank=True,
        verbose_name="Kurs o'tiladigan guruhlar"
    )

    class Meta:
        verbose_name = "Kurs"
        verbose_name_plural = "Kurslar"
        unique_together = ('title', 'center')
        ordering = ['title']

    def __str__(self):
        return self.title

    @property
    def is_online(self):
        return self.course_type == 'online'
    
    @property
    def is_scheduled(self):
        return self.is_online and self.online_lesson_flow == 'scheduled'

class CourseModule(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='modules', verbose_name="Kurs")
    title = models.CharField(max_length=200, verbose_name="Modul nomi")
    description = models.TextField(verbose_name="Tavsif", blank=True, null=True)
    order = models.PositiveIntegerField(default=0, verbose_name="Tartib raqami")

    class Meta:
        verbose_name = "Kurs Moduli"
        verbose_name_plural = "Kurs Modullari"
        ordering = ['order']
        unique_together = ('course', 'order')

    def __str__(self):
        return f"{self.course.title} - {self.title}"

class Lesson(models.Model):
    module = models.ForeignKey(CourseModule, on_delete=models.CASCADE, related_name='lessons', verbose_name="Modul")
    title = models.CharField(max_length=200, verbose_name="Dars nomi")
    related_exam = models.OneToOneField(
        'Exam', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='lesson', 
        verbose_name="Mavzu testi",
        help_text="Bu darsga test biriktirilishi shart emas. Agar biriktirilsa, keyingi darsga o'tish uchun talab etiladi."
    )
    order = models.PositiveIntegerField(default=0, verbose_name="Tartib raqami")

    class Meta:
        verbose_name = "Dars"
        verbose_name_plural = "Darslar"
        ordering = ['module__order', 'order']
        unique_together = ('module', 'order')

    def __str__(self):
        return f"{self.module.title} - {self.title}"

    @property
    def has_resources(self):
        return self.resources.exists()

    @property
    def has_exam(self):
        return self.related_exam is not None

class LessonResource(models.Model):
    lesson = models.ForeignKey(
        Lesson, 
        on_delete=models.CASCADE, 
        related_name='resources', 
        verbose_name="Dars"
    )
    resource_type = models.CharField(
        max_length=20, 
        choices=RESOURCE_TYPE_CHOICES, 
        verbose_name="Resurs turi"
    )
    link = models.URLField(
        max_length=500, 
        verbose_name="Resurs linki",
        help_text="Video, fayl yoki boshqa materialga tashqi URL manzil."
    )
    title = models.CharField(
        max_length=200, 
        verbose_name="Resurs nomi (Masalan: 1-qism)", 
        blank=True, 
        null=True
    )
    order = models.PositiveIntegerField(default=0, verbose_name="Tartib raqami")

    class Meta:
        verbose_name = "Dars Resursi"
        verbose_name_plural = "Dars Resurslari"
        ordering = ['resource_type', 'order']

    def __str__(self):
        return f"{self.get_resource_type_display()} - {self.lesson.title}"

class CourseSchedule(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='schedules', verbose_name="Kurs")
    related_lesson = models.ForeignKey(
        Lesson, 
        on_delete=models.CASCADE, 
        related_name='schedules', 
        verbose_name="Bog'liq dars",
        help_text="Bu jadval qaysi darsga tegishli ekanligini ko'rsatadi."
    )
    start_time = models.DateTimeField(verbose_name="Boshlanish vaqti")
    end_time = models.DateTimeField(verbose_name="Tugash vaqti", blank=True, null=True)
    location = models.CharField(max_length=255, blank=True, null=True, verbose_name="Manzil/Xona")

    class Meta:
        verbose_name = "Dars Jadvali"
        verbose_name_plural = "Dars Jadvali"
        ordering = ['start_time']

    def __str__(self):
        return f"{self.related_lesson.title} - {self.start_time.strftime('%Y-%m-%d %H:%M')}"

class UserSolutionView(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='solution_views')
    question = models.ForeignKey('Question', on_delete=models.CASCADE, related_name='solution_views')
    viewed_at = models.DateTimeField(auto_now_add=True)
    credit_spent = models.BooleanField(default=False, verbose_name="Kredit sarflandimi?")

    class Meta:
        verbose_name = "Ko'rilgan savol yechimi"
        verbose_name_plural = "Ko'rilgan savol yechimlari"
        unique_together = ('user', 'question')

    def __str__(self):
        return f"{self.user.username} -> {self.question.id}-savol yechimi"

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

class Badge(models.Model):
    TRIGGER_TYPES = [
        ('exam_completed', 'Imtihon yakunlandi'),
        ('score_achieved', 'Ball yetkazildi'),
        ('streak', 'Ketma-ketlik'),
        ('flashcard_learned', 'Flashcard o\'rganildi'),
        ('daily_high_score', 'Eng yaxshi kunlik natija'),
        ('referral', 'Do\'stlarni taklif qilish'),
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
    center = models.ForeignKey(
        'Center', 
        on_delete=models.CASCADE, 
        related_name='badges', 
        verbose_name="Tegishli Markaz",
        null=True
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
    center = models.ForeignKey(
        'Center', 
        on_delete=models.CASCADE, 
        related_name='user_badges', 
        verbose_name="Tegishli Markaz",
        null=True
    )

    class Meta:
        unique_together = ('user', 'badge', 'center')
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
    week_number = models.PositiveIntegerField(verbose_name="Hafta raqami")
    score = models.PositiveIntegerField(default=0, verbose_name="Ball yoki ko'rsatkich")
    updated_at = models.DateTimeField(auto_now=True)
    center = models.ForeignKey(
        'Center', 
        on_delete=models.CASCADE, 
        related_name='leaderboard_entries', 
        verbose_name="Tegishli Markaz",
        null=True
    )

    class Meta:
        verbose_name = "Leaderboard kirishi"
        verbose_name_plural = "Leaderboard kirishlari"
        unique_together = ('user', 'leaderboard_type', 'week_number', 'center')
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

class UserAnswerArchive(models.Model):
    attempt_section = models.ForeignKey('UserAttemptSection', on_delete=models.CASCADE, related_name='archived_answers')
    question = models.ForeignKey('Question', on_delete=models.CASCADE)
    selected_options = models.ManyToManyField('AnswerOption', blank=True, verbose_name="Tanlangan variantlar")
    short_answer_text = models.CharField(max_length=255, blank=True, null=True, verbose_name="Qisqa javob matni")
    is_correct = models.BooleanField(null=True, verbose_name="To'g'riligi")
    answered_at = models.DateTimeField()
    time_taken_seconds = models.PositiveIntegerField(null=True, blank=True, verbose_name="Sarflangan vaqt (soniya)")

    class Meta:
        verbose_name = "Arxivlangan foydalanuvchi javobi"
        verbose_name_plural = "Arxivlangan foydalanuvchi javoblari"

    def __str__(self):
        return f"Arxiv: {self.attempt_section.attempt.user.username} javobi"