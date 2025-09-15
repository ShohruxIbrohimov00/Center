from django import forms
from django.forms import modelformset_factory
from .models import Question, Subtopic, Topic, Passage, Tag, Exam, ExamSection, ExamSectionTopicRule, ExamSectionSubtopicRule, Flashcard, RaschDifficultyLevel, AnswerOption
from ckeditor.fields import RichTextField
from ckeditor.widgets import CKEditorWidget
from django_select2.forms import Select2MultipleWidget

class AnswerOptionForm(forms.ModelForm):
    # CKEditorWidget bilan CharField dan foydalanamiz
    text = forms.CharField(label="Javob varianti matni", widget=CKEditorWidget())
    is_correct = forms.BooleanField(required=False, label="To'g'ri javob")

    class Meta:
        model = AnswerOption
        fields = ['text', 'is_correct']

AnswerOptionFormSet = modelformset_factory(
    AnswerOption,
    form=AnswerOptionForm,
    fields=('text', 'is_correct'),
    extra=2, 
    max_num=6,
    can_delete=True
)

class QuestionForm(forms.ModelForm):
    # Savol matni, yechim va maslahat uchun CKEditorWidget ishlatamiz
    text = forms.CharField(label="Savol matni", widget=CKEditorWidget(), required=False)
    hint = forms.CharField(label="Yechim uchun maslahat", widget=CKEditorWidget(), required=False)
    detailed_solution = forms.CharField(label="Yechim", widget=CKEditorWidget(), required=False)

    class Meta:
        model = Question
        fields = [
            'text', 'subtopic', 'answer_format', 'passage', 'image',
            'flashcards', 'tags', 'difficulty_level', 'difficulty', 'status',
        ]
        widgets = {
            'answer_format': forms.Select(attrs={'id': 'id_answer_format', 'class': 'w-full border rounded-md p-2'}),
            'subtopic': forms.Select(attrs={'class': 'w-full border rounded-md p-2'}),
            'passage': forms.Select(attrs={'class': 'w-full border rounded-md p-2'}),
            'flashcards': forms.SelectMultiple(attrs={'class': 'w-full border rounded-md p-2'}),
            'tags': forms.SelectMultiple(attrs={'class': 'w-full border rounded-md p-2'}),
            'difficulty_level': forms.Select(attrs={'class': 'w-full border rounded-md p-2'}),
            'difficulty': forms.NumberInput(attrs={'class': 'w-full border rounded-md p-2', 'step': '0.1'}),
            'status': forms.Select(attrs={'class': 'w-full border rounded-md p-2'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and hasattr(self.instance, 'solution'):
            self.fields['hint'].initial = self.instance.solution.hint
            self.fields['detailed_solution'].initial = self.instance.solution.detailed_solution

class PassageForm(forms.ModelForm):
    content = forms.CharField(label="Matn (HTML)", widget=CKEditorWidget(), required=False)

    class Meta:
        model = Passage
        fields = ['title', 'content']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500'}),
        }
          
class FlashcardForm(forms.ModelForm):
    english_content = forms.CharField(label="Inglizcha kontent", widget=CKEditorWidget(), required=False)
    uzbek_meaning = forms.CharField(label="O'zbekcha ma'nosi", widget=CKEditorWidget(), required=False)
    context_sentence = forms.CharField(label="Kontekst (gap)", widget=CKEditorWidget(), required=False)

    class Meta:
        model = Flashcard
        fields = [
            'content_type',
            'english_content',
            'uzbek_meaning',
            'context_sentence'
        ]
        widgets = {
            'content_type': forms.Select(attrs={'class': 'w-full px-3 py-2 border rounded-md'}),
        }

class TopicForm(forms.ModelForm):
    class Meta:
        model = Topic
        fields = ['name', 'order']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500',
                'placeholder': 'Mavzu nomini kiriting'
            }),
            'order': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500',
                'placeholder': 'Tartib raqami'
            })
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
            'name': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500',
                'placeholder': 'Ichki mavzu nomini kiriting'
            }),
            'topic': forms.Select(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500'
            }),
            'order': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500',
                'placeholder': 'Tartib raqami'
            })
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
            'title': forms.TextInput(attrs={
                'class': 'shadow appearance-none border rounded-md w-full py-2 px-3 text-gray-700 focus:outline-none focus:ring focus:border-blue-300 transition duration-150'
            }),
            'description': forms.Textarea(attrs={
                'class': 'shadow appearance-none border rounded-md w-full py-2 px-3 text-gray-700 focus:outline-none focus:ring focus:border-blue-300 transition duration-150',
                'rows': 4
            }),
            'is_premium': forms.CheckboxInput(attrs={
                'class': 'form-checkbox h-5 w-5 text-green-600'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-checkbox h-5 w-5 text-green-600'
            }),
        }

class ExamSectionForm(forms.ModelForm):
    class Meta:
        model = ExamSection
        fields = ['section_type', 'duration_minutes', 'max_questions', 'module_number', 'order']
        widgets = {
            'section_type': forms.Select(attrs={
                'class': 'shadow appearance-none border rounded-md w-full py-2 px-3 text-gray-700 focus:outline-none focus:ring focus:border-blue-300 transition duration-150'
            }),
            'duration_minutes': forms.NumberInput(attrs={
                'class': 'shadow appearance-none border rounded-md w-full py-2 px-3 text-gray-700 focus:outline-none focus:ring focus:border-blue-300 transition duration-150',
                'min': 1
            }),
            'max_questions': forms.NumberInput(attrs={
                'class': 'shadow appearance-none border rounded-md w-full py-2 px-3 text-gray-700 focus:outline-none focus:ring focus:border-blue-300 transition duration-150',
                'min': 1
            }),
            'module_number': forms.NumberInput(attrs={
                'class': 'shadow appearance-none border rounded-md w-full py-2 px-3 text-gray-700 focus:outline-none focus:ring focus:border-blue-300 transition duration-150',
                'min': 1
            }),
            'order': forms.NumberInput(attrs={
                'class': 'shadow appearance-none border rounded-md w-full py-2 px-3 text-gray-700 focus:outline-none focus:ring focus:border-blue-300 transition duration-150',
                'min': 1
            }),
        }
    
    def __init__(self, *args, **kwargs):
        exam_type = kwargs.pop('exam_type', 'static')
        super().__init__(*args, **kwargs)
        
        if exam_type == 'static':
            if 'min_difficulty' in self.fields:
                del self.fields['min_difficulty']
            if 'max_difficulty' in self.fields:
                del self.fields['max_difficulty']
    
    def clean_duration_minutes(self):
        duration = self.cleaned_data['duration_minutes']
        if duration < 1:
            raise forms.ValidationError("Davomiylik 1 daqiqadan kam bo'lmasligi kerak.")
        return duration
    
    def clean_max_questions(self):
        max_questions = self.cleaned_data['max_questions']
        if max_questions < 1:
            raise forms.ValidationError("Maksimal savollar soni 1 tadan kam bo'lmasligi kerak.")
        return max_questions
    
    def clean_module_number(self):
        module_number = self.cleaned_data['module_number']
        if module_number < 1:
            raise forms.ValidationError("Modul raqami 1 dan kam bo'lmasligi kerak.")
        return module_number
    
    def clean_order(self):
        order = self.cleaned_data['order']
        if order < 1:
            raise forms.ValidationError("Tartib raqami 1 dan kam bo'lmasligi kerak.")
        return order

class ExamSectionTopicRuleForm(forms.ModelForm):
    class Meta:
        model = ExamSectionTopicRule
        fields = ['topic', 'questions_count']
        widgets = {
            'topic': forms.Select(attrs={
                'class': 'shadow appearance-none border rounded-md w-full py-2 px-3 text-gray-700 focus:outline-none focus:ring focus:border-blue-300 transition duration-150'
            }),
            'questions_count': forms.NumberInput(attrs={
                'class': 'shadow appearance-none border rounded-md w-full py-2 px-3 text-gray-700 focus:outline-none focus:ring focus:border-blue-300 transition duration-150',
                'min': 1
            }),
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
            'subtopic': forms.Select(attrs={
                'class': 'shadow appearance-none border rounded-md w-full py-2 px-3 text-gray-700 focus:outline-none focus:ring focus:border-blue-300 transition duration-150'
            }),
            'questions_count': forms.NumberInput(attrs={
                'class': 'shadow appearance-none border rounded-md w-full py-2 px-3 text-gray-700 focus:outline-none focus:ring focus:border-blue-300 transition duration-150',
                'min': 1
            }),
        }
    
    def clean_questions_count(self):
        questions_count = self.cleaned_data['questions_count']
        if questions_count < 1:
            raise forms.ValidationError("Savollar soni 1 tadan kam bo'lmasligi kerak.")
        return questions_count

class PurchaseForm(forms.Form):
    promo_code = forms.CharField(max_length=50, required=False, label="Promo kod (agar mavjud bo'lsa)",
                                 widget=forms.TextInput(attrs={'placeholder': 'Promo kodingizni kiriting', 'class': 'form-input mt-1 block w-full'}))
