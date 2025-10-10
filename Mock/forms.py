from django import forms
from django.forms import modelformset_factory
from .models import Question, Subtopic, Passage, Tag, Flashcard, RaschDifficultyLevel, AnswerOption, QuestionSolution
from .models import Topic,ExamSection,Exam,ExamSectionTopicRule,ExamSectionSubtopicRule,CustomUser,Purchase
from ckeditor_uploader.fields import RichTextUploadingField
from ckeditor.widgets import CKEditorWidget  
from django_select2.forms import Select2MultipleWidget, Select2Widget
from django.contrib.auth.forms import AuthenticationForm,PasswordChangeForm
from .models import CustomUser


form_control_class = 'shadow-sm appearance-none border border-gray-300 rounded-lg w-full py-3 px-4 text-gray-700 leading-tight focus:outline-none focus:ring-2 focus:ring-indigo-400 focus:border-transparent transition'

class SignUpForm(forms.ModelForm):
    password = forms.CharField(label="Parol", widget=forms.PasswordInput(attrs={'class': form_control_class}))
    password_confirm = forms.CharField(label="Parolni tasdiqlang", widget=forms.PasswordInput(attrs={'class': form_control_class}))

    class Meta:
        model = CustomUser
        # Ro'yxatdan o'tishda so'raladigan maydonlar
        fields = ['full_name', 'email', 'phone_number', 'username']
        labels = {
            'full_name': "To'liq ismingiz (F.I.Sh)",
            'email': "Elektron pochta",
            'phone_number': "Telefon raqamingiz",
            'username': "Foydalanuvchi nomi (login)",
        }
        widgets = {
            'full_name': forms.TextInput(attrs={'class': form_control_class, 'placeholder': 'Aliyev Vali G\'aniyevich'}),
            'email': forms.EmailInput(attrs={'class': form_control_class, 'placeholder': 'example@mail.com'}),
            'phone_number': forms.TextInput(attrs={'class': form_control_class, 'placeholder': '+998 xx xxx xx xx'}),
            'username': forms.TextInput(attrs={'class': form_control_class, 'placeholder': 'alivaliyev'}),
        }

    # Tekshiruv funksiyalari (clean_...) o'zgarishsiz qoladi, faqat email uchun qo'shiladi
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if CustomUser.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Bu elektron pochta manzili bilan allaqachon ro'yxatdan o'tilgan.")
        return email

    def clean_password_confirm(self):
        password = self.cleaned_data.get('password')
        password_confirm = self.cleaned_data.get('password_confirm')
        if password and password_confirm and password != password_confirm:
            raise forms.ValidationError("Kiritilgan parollar bir-biriga mos kelmadi.")
        return password_confirm
    
    # ... (clean_phone_number va clean_username o'zgarishsiz) ...
    def clean_phone_number(self):
        phone = self.cleaned_data.get('phone_number')
        if CustomUser.objects.filter(phone_number=phone).exists():
            raise forms.ValidationError("Bu telefon raqami bilan allaqachon ro'yxatdan o'tilgan.")
        return phone
    def clean_username(self):
        username = self.cleaned_data.get('username')
        if CustomUser.objects.filter(username=username).exists():
            raise forms.ValidationError("Bu foydalanuvchi nomi band. Boshqa nom tanlang.")
        return username

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password'])
        if commit:
            user.save()
        return user

class LoginForm(AuthenticationForm):
    pass 

class ProfileUpdateForm(forms.ModelForm):
    """Foydalanuvchi o'z profilidagi asosiy ma'lumotlarni o'zgartirishi uchun forma."""
    
    # Email'ni o'zgartirishda xatolik bo'lmasligi uchun maxsus logikani qo'shamiz
    def __init__(self, *args, **kwargs):
        super(ProfileUpdateForm, self).__init__(*args, **kwargs)
        self.fields['email'].required = True # Email majburiy

    def clean_email(self):
        email = self.cleaned_data.get('email').lower()
        # Agar email o'zgartirilgan bo'lsa va yangi email band bo'lsa, xatolik beramiz
        if self.instance.email != email and CustomUser.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Bu elektron pochta manzili bilan boshqa foydalanuvchi ro'yxatdan o'tgan.")
        return email

    class Meta:
        model = CustomUser
        # O'zgartirilishi mumkin bo'lgan maydonlar ro'yxati
        fields = ['full_name', 'email', 'bio', 'profile_picture']
        
        labels = {
            'full_name': "To'liq ism (F.I.Sh)",
            'email': "Elektron pochta",
            'bio': "O'zi haqida qisqacha",
            'profile_picture': "Profil rasmini o'zgartirish",
        }
        
        widgets = {
            'full_name': forms.TextInput(attrs={'class': 'form-field', 'placeholder': 'Ism va familiyangiz'}),
            'email': forms.EmailInput(attrs={'class': 'form-field', 'placeholder': 'Email manzilingiz'}),
            'bio': forms.Textarea(attrs={'class': 'form-field', 'rows': 4, 'placeholder': 'O\'zingiz haqingizda qisqacha ma\'lumot...'}),
            'profile_picture': forms.FileInput(attrs={'class': 'form-field-file'}), # Fayl yuklash uchun alohida stil kerak bo'lishi mumkin
        }

class CustomPasswordChangeForm(PasswordChangeForm):
    old_password = forms.CharField(label="Joriy parol", widget=forms.PasswordInput(attrs={'class': form_control_class, 'autocomplete': 'current-password'}))
    new_password1 = forms.CharField(label="Yangi parol", widget=forms.PasswordInput(attrs={'class': form_control_class, 'autocomplete': 'new-password'}))
    new_password2 = forms.CharField(label="Yangi parolni tasdiqlang", widget=forms.PasswordInput(attrs={'class': form_control_class, 'autocomplete': 'new-password'}))

class AnswerOptionForm(forms.ModelForm):
    text = forms.CharField(
        label="Javob varianti matni",
        widget=CKEditorWidget(config_name='default'),
        required=True
    )
    is_correct = forms.BooleanField(required=False, label="To'g'ri javob")

    class Meta:
        model = AnswerOption
        fields = ['text', 'is_correct']

    def clean_text(self):
        text = self.cleaned_data.get('text')
        if not text.strip():
            raise forms.ValidationError("Javob varianti matni bo'sh bo'lmasligi kerak.")
        return text

AnswerOptionFormSet = modelformset_factory(
    AnswerOption,
    form=AnswerOptionForm,
    fields=('text', 'is_correct'),
    extra=4,  # Boshlang'ichda faqat 2 ta variant
    max_num=5,  # Maksimal 5 ta variant
    can_delete=True
)

class QuestionForm(forms.ModelForm):
    text = forms.CharField(
        label="Savol matni",
        widget=CKEditorWidget(config_name='default', attrs={'id': 'id_text'}),
        required=True
    )
    hint = forms.CharField(
        label="Yechim uchun maslahat",
        widget=CKEditorWidget(config_name='default', attrs={'id': 'id_hint'}),
        required=False
    )
    detailed_solution = forms.CharField(
        label="Batafsil yechim",
        widget=CKEditorWidget(config_name='default', attrs={'id': 'id_detailed_solution'}),
        required=False
    )
    correct_short_answer = forms.CharField(label="To'g'ri qisqa javob", required=False)

    class Meta:
        model = Question
        fields = [
            'text', 'subtopic', 'answer_format', 'passage', 'image',
            'flashcards', 'tags', 'difficulty_level', 'difficulty',
            'discrimination', 'guessing', 'status', 'is_solution_free',
            'correct_short_answer'
        ]
        widgets = {
            'answer_format': Select2Widget(attrs={'class': 'w-full', 'id': 'id_answer_format'}),
            'subtopic': Select2Widget(attrs={'class': 'w-full', 'id': 'id_subtopic'}),
            'passage': Select2Widget(attrs={'class': 'w-full', 'id': 'id_passage'}),
            'flashcards': Select2MultipleWidget(attrs={'class': 'w-full', 'id': 'id_flashcards'}),
            'tags': Select2MultipleWidget(attrs={'class': 'w-full', 'id': 'id_tags'}),
            'difficulty_level': Select2Widget(attrs={'class': 'w-full', 'id': 'id_difficulty_level'}),
            'difficulty': forms.NumberInput(attrs={
                'class': 'w-full border rounded-md p-2',
                'step': '0.1', 'min': '-3.0', 'max': '3.0',
                'id': 'id_difficulty',
                'placeholder': 'Oson: -3.0 to -1.0, O‘rta: -1.0 to 1.0, Qiyin: 1.0 to 3.0'
            }),
            'discrimination': forms.NumberInput(attrs={'class': 'w-full border rounded-md p-2', 'step': '0.1', 'min': '0.0', 'max': '2.0', 'id': 'id_discrimination'}),
            'guessing': forms.NumberInput(attrs={
                'class': 'w-full border rounded-md p-2',
                'step': '0.01', 'min': '0.0', 'max': '1.0',
                'id': 'id_guessing',
                'placeholder': 'Multiple-choice uchun 0.0–0.2'
            }),
            'status': Select2Widget(attrs={'class': 'w-full', 'id': 'id_status'}),
            'is_solution_free': forms.CheckboxInput(attrs={'class': 'form-checkbox h-5 w-5 text-indigo-600', 'id': 'id_is_solution_free'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and hasattr(self.instance, 'solution'):
            self.fields['hint'].initial = self.instance.solution.hint
            self.fields['detailed_solution'].initial = self.instance.solution.detailed_solution
        if self.instance and self.instance.correct_short_answer:
            self.fields['correct_short_answer'].initial = self.instance.correct_short_answer
        if not self.instance.pk:
            self.fields['difficulty'].initial = -1.0
            self.fields['discrimination'].initial = 1.0
            self.fields['guessing'].initial = 0.1

    def clean(self):
        cleaned_data = super().clean()
        answer_format = cleaned_data.get('answer_format')
        correct_short_answer = cleaned_data.get('correct_short_answer')
        difficulty = cleaned_data.get('difficulty')
        difficulty_level = cleaned_data.get('difficulty_level')
        guessing = cleaned_data.get('guessing')

        if answer_format == 'short_answer' and not correct_short_answer:
            self.add_error('correct_short_answer', "Qisqa javob formatida to'g'ri javob kiritilishi shart.")
        elif answer_format in ['single', 'multiple'] and correct_short_answer:
            self.add_error('correct_short_answer', "Yagona yoki ko'p javob formatida qisqa javob kiritilmasligi kerak.")

        if answer_format == 'multiple' and guessing is not None and guessing > 0.2:
            self.add_error('guessing', "Multiple-choice savollar uchun taxmin qilish 0.0–0.2 oralig'ida bo'lishi kerak.")

        if difficulty is not None:
            if difficulty < -3.0 or difficulty > 3.0:
                self.add_error('difficulty', "Qiyinlik -3.0 dan 3.0 gacha bo'lishi kerak.")
            if difficulty_level:
                if difficulty_level.name.lower() == 'easy' and (difficulty < -3.0 or difficulty > -1.0):
                    self.add_error('difficulty', "Oson savollar uchun qiyinlik -3.0 dan -1.0 gacha bo'lishi kerak.")
                elif difficulty_level.name.lower() == 'medium' and (difficulty < -1.0 or difficulty > 1.0):
                    self.add_error('difficulty', "O'rta savollar uchun qiyinlik -1.0 dan 1.0 gacha bo'lishi kerak.")
                elif difficulty_level.name.lower() == 'hard' and (difficulty < 1.0 or difficulty > 3.0):
                    self.add_error('difficulty', "Qiyin savollar uchun qiyinlik 1.0 dan 3.0 gacha bo'lishi kerak.")

        if discrimination := cleaned_data.get('discrimination'):
            if discrimination < 0.0 or discrimination > 2.0:
                self.add_error('discrimination', "Diskriminatsiya 0.0 dan 2.0 gacha bo'lishi kerak.")

        if guessing is not None and (guessing < 0.0 or guessing > 1.0):
            self.add_error('guessing', "Taxmin qilish 0.0 dan 1.0 gacha bo'lishi kerak.")

        return cleaned_data
       
class PassageForm(forms.ModelForm):
    content = forms.CharField(
        label="Matn (HTML)",
        widget=CKEditorWidget(config_name='default', attrs={'id': 'id_content'}),
        required=False
    )

    class Meta:
        model = Passage
        fields = ['title', 'content']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'w-full px-3 py-2 border rounded-md', 'id': 'id_title'}),
        }

class FlashcardForm(forms.ModelForm):
    english_content = forms.CharField(
        label="Inglizcha kontent",
        widget=CKEditorWidget(config_name='default', attrs={'id': 'id_english_content'}),
        required=False
    )
    uzbek_meaning = forms.CharField(
        label="O'zbekcha ma'nosi",
        widget=CKEditorWidget(config_name='default', attrs={'id': 'id_uzbek_meaning'}),
        required=False
    )
    context_sentence = forms.CharField(
        label="Kontekst (gap)",
        widget=CKEditorWidget(config_name='default', attrs={'id': 'id_context_sentence'}),
        required=False
    )

    class Meta:
        model = Flashcard
        fields = ['content_type', 'english_content', 'uzbek_meaning', 'context_sentence', 'source_question']
        widgets = {
            'content_type': Select2Widget(attrs={'class': 'w-full', 'id': 'id_content_type'}),
            'source_question': Select2Widget(attrs={'class': 'w-full', 'id': 'id_source_question'}),
        }

class TopicForm(forms.ModelForm):
    class Meta:
        model = Topic
        fields = ['name', 'order']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'w-full px-4 py-2 border rounded-md', 'id': 'id_name'}),
            'order': forms.NumberInput(attrs={'class': 'w-full px-4 py-2 border rounded-md', 'id': 'id_order'}),
        }
        labels = {
            'name': 'Mavzu nomi',
            'order': 'Tartib raqami'
        }

class SubtopicForm(forms.ModelForm):
    class Meta:
        model = Subtopic
        fields = ['name', 'topic', 'order']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'w-full px-4 py-2 border rounded-md', 'id': 'id_name'}),
            'topic': Select2Widget(attrs={'class': 'w-full', 'id': 'id_topic'}),
            'order': forms.NumberInput(attrs={'class': 'w-full px-4 py-2 border rounded-md', 'id': 'id_order'}),
        }
        labels = {
            'name': 'Ichki mavzu nomi',
            'topic': 'Asosiy mavzu',
            'order': 'Tartib raqami'
        }

class ExamForm(forms.ModelForm):
    class Meta:
        model = Exam
        fields = ['title', 'description', 'is_premium', 'is_active']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'w-full px-3 py-2 border rounded-md', 'id': 'id_title'}),
            'description': forms.Textarea(attrs={'class': 'w-full px-3 py-2 border rounded-md', 'rows': 4, 'id': 'id_description'}),
            'is_premium': forms.CheckboxInput(attrs={'class': 'form-checkbox h-5 w-5 text-indigo-600', 'id': 'id_is_premium'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-checkbox h-5 w-5 text-indigo-600', 'id': 'id_is_active'}),
        }

class ExamSectionForm(forms.ModelForm):
    class Meta:
        model = ExamSection
        fields = ['section_type', 'duration_minutes', 'max_questions', 'module_number', 'order', 'min_difficulty', 'max_difficulty']
        widgets = {
            'section_type': Select2Widget(attrs={'class': 'w-full', 'id': 'id_section_type'}),
            'duration_minutes': forms.NumberInput(attrs={'class': 'w-full px-3 py-2 border rounded-md', 'min': 1, 'id': 'id_duration_minutes'}),
            'max_questions': forms.NumberInput(attrs={'class': 'w-full px-3 py-2 border rounded-md', 'min': 1, 'id': 'id_max_questions'}),
            'module_number': forms.NumberInput(attrs={'class': 'w-full px-3 py-2 border rounded-md', 'min': 1, 'id': 'id_module_number'}),
            'order': forms.NumberInput(attrs={'class': 'w-full px-3 py-2 border rounded-md', 'min': 1, 'id': 'id_order'}),
            'min_difficulty': forms.NumberInput(attrs={'class': 'w-full px-3 py-2 border rounded-md', 'step': '0.1', 'id': 'id_min_difficulty'}),
            'max_difficulty': forms.NumberInput(attrs={'class': 'w-full px-3 py-2 border rounded-md', 'step': '0.1', 'id': 'id_max_difficulty'}),
        }

    def __init__(self, *args, **kwargs):
        exam_type = kwargs.pop('exam_type', 'static')
        super().__init__(*args, **kwargs)
        if exam_type == 'static':
            if 'min_difficulty' in self.fields:
                del self.fields['min_difficulty']
            if 'max_difficulty' in self.fields:
                del self.fields['max_difficulty']

    def clean(self):
        cleaned_data = super().clean()
        duration = cleaned_data.get('duration_minutes')
        max_questions = cleaned_data.get('max_questions')
        module_number = cleaned_data.get('module_number')
        order = cleaned_data.get('order')
        min_difficulty = cleaned_data.get('min_difficulty')
        max_difficulty = cleaned_data.get('max_difficulty')

        if duration is not None and duration < 1:
            self.add_error('duration_minutes', "Davomiylik 1 daqiqadan kam bo'lmasligi kerak.")
        if max_questions is not None and max_questions < 1:
            self.add_error('max_questions', "Maksimal savollar soni 1 tadan kam bo'lmasligi kerak.")
        if module_number is not None and module_number < 1:
            self.add_error('module_number', "Modul raqami 1 dan kam bo'lmasligi kerak.")
        if order is not None and order < 1:
            self.add_error('order', "Tartib raqami 1 dan kam bo'lmasligi kerak.")
        if min_difficulty is not None and max_difficulty is not None and min_difficulty > max_difficulty:
            self.add_error('min_difficulty', "Minimal qiyinlik maksimal qiyinlikdan katta bo'lmasligi kerak.")

        return cleaned_data

class ExamSectionTopicRuleForm(forms.ModelForm):
    class Meta:
        model = ExamSectionTopicRule
        fields = ['topic', 'questions_count']
        widgets = {
            'topic': Select2Widget(attrs={'class': 'w-full', 'id': 'id_topic'}),
            'questions_count': forms.NumberInput(attrs={'class': 'w-full px-3 py-2 border rounded-md', 'min': 1, 'id': 'id_questions_count'}),
        }

    def clean_questions_count(self):
        questions_count = self.cleaned_data['questions_count']
        if questions_count < 1:
            raise forms.ValidationError("Savollar soni 1 tadan kam bo'lmasligi kerak.")
        return questions_count

class ExamSectionSubtopicRuleForm(forms.ModelForm):
    class Meta:
        model = ExamSectionSubtopicRule
        fields = ['subtopic', 'questions_count']
        widgets = {
            'subtopic': Select2Widget(attrs={'class': 'w-full', 'id': 'id_subtopic'}),
            'questions_count': forms.NumberInput(attrs={'class': 'w-full px-3 py-2 border rounded-md', 'min': 1, 'id': 'id_questions_count'}),
        }

    def clean_questions_count(self):
        questions_count = self.cleaned_data['questions_count']
        if questions_count < 1:
            raise forms.ValidationError("Savollar soni 1 tadan kam bo'lmasligi kerak.")
        return questions_count

class PurchaseForm(forms.Form):
    promo_code = forms.CharField(
        max_length=50,
        required=False,
        label="Promo kod (agar mavjud bo'lsa)",
        widget=forms.TextInput(attrs={'placeholder': 'Promo kodingizni kiriting', 'class': 'w-full px-3 py-2 border rounded-md', 'id': 'id_promo_code'})
    )

class ScreenshotUploadForm(forms.ModelForm):
    class Meta:
        model = Purchase
        fields = ['payment_screenshot', 'payment_comment']
        labels = {
            'payment_screenshot': 'To\'lov cheki (skrinshot yoki PDF)',
            'payment_comment': 'To\'lov haqida izoh (ixtiyoriy)',
        }
        widgets = {
            'payment_comment': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Masalan, qaysi kartadan yoki qachon to\'lov qilganingiz haqida...'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['payment_screenshot'].required = True # Skrinshot yuklash majburiy