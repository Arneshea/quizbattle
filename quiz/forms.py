from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.forms import inlineformset_factory

from .models import Quiz, Question


class QuizForm(forms.ModelForm):
    class Meta:
        model = Quiz
        fields = ['title', 'description']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.TextInput(attrs={'class': 'form-control'}),
        }


class QuestionForm(forms.ModelForm):
    class Meta:
        model = Question
        fields = ['text', 'option_a', 'option_b', 'option_c', 'option_d',
                  'correct_option', 'time_limit_seconds']
        widgets = {
            'text': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Question text'}),
            'option_a': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Option A'}),
            'option_b': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Option B'}),
            'option_c': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Option C'}),
            'option_d': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Option D'}),
            'correct_option': forms.Select(attrs={'class': 'form-select'}),
            'time_limit_seconds': forms.NumberInput(attrs={'class': 'form-control', 'min': 5, 'max': 300}),
        }

    def clean_time_limit_seconds(self):
        value = self.cleaned_data['time_limit_seconds']
        if value < 5 or value > 300:
            raise forms.ValidationError('Time limit must be between 5 and 300 seconds.')
        return value


QuestionFormSet = inlineformset_factory(
    Quiz, Question, form=QuestionForm, extra=1, can_delete=True
)


class SignUpForm(UserCreationForm):
    class Meta:
        model = User
        fields = ['username', 'password1', 'password2']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'
