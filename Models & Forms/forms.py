from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import User, Article, ResearchPaper
from django.utils.text import slugify

class SignUpForm(UserCreationForm):
    email = forms.EmailField(required=True)
    role = forms.ChoiceField(choices=User.ROLE_CHOICES, initial='user')

    class Meta:
        model = User
        fields = ('username', 'email', 'role', 'password1', 'password2')

class ArticleForm(forms.ModelForm):
    class Meta:
        model = Article
        fields = ['title', 'slug', 'summary', 'content', 'cover_image', 'attachment', 'tags', 'published']

    def clean_slug(self):
        slug = self.cleaned_data['slug']
        return slugify(slug)

class ResearchPaperForm(forms.ModelForm):
    class Meta:
        model = ResearchPaper
        fields = ['title', 'slug', 'abstract', 'content', 'authors', 'pdf', 'published']

    def clean_slug(self):
        from django.utils.text import slugify
        return slugify(self.cleaned_data['slug'])

class ContactForm(forms.Form):
    name = forms.CharField(max_length=120, required=True, widget=forms.TextInput(attrs={'placeholder': 'Your name'}))
    email = forms.EmailField(required=True, widget=forms.EmailInput(attrs={'placeholder': 'you@example.com'}))
    subject = forms.CharField(max_length=200, required=True, widget=forms.TextInput(attrs={'placeholder': 'Subject'}))
    message = forms.CharField(required=True, widget=forms.Textarea(attrs={'placeholder': 'Write your message here', 'rows':6}))