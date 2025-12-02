from django.urls import path, include
from . import views
from django.contrib.auth import views as auth_views
from django.contrib import admin
from .views import DashboardView, AboutView, TeamView, ContactView
from .views import track_visit

urlpatterns = [
    path('', views.IndexView.as_view(), name='index'),
    path('article/add/', views.ArticleCreateView.as_view(), name='article_add'),
    path('article/<slug:slug>/', views.ArticleDetailView.as_view(), name='article_detail'),
    path('article/<slug:slug>/edit/', views.ArticleUpdateView.as_view(), name='article_edit'),

    path('paper/add/', views.PaperCreateView.as_view(), name='paper_add'),
    path('paper/<slug:slug>/', views.PaperDetailView.as_view(), name='paper_detail'),

    path('signup/', views.signup_view, name='signup'),
    path('search/', views.search_view, name='search'),
    # Note: Django's auth urls (login/logout/password reset) added in project urls
    path("password-reset/",
         auth_views.PasswordResetView.as_view(
             template_name="core/password_reset/password_reset_form.html",
             email_template_name="core/password_reset/password_reset_email.html",
             subject_template_name="core/password_reset/password_reset_subject.txt",
             success_url="/password-reset/done/",
         ),
         name="password_reset"),

    path("password-reset/done/",
         auth_views.PasswordResetDoneView.as_view(
             template_name="core/password_reset/password_reset_done.html"
         ),
         name="password_reset_done"),

    path("reset/<uidb64>/<token>/",
         auth_views.PasswordResetConfirmView.as_view(
             template_name="core/password_reset/password_reset_confirm.html",
             success_url="/reset/done/",
         ),
         name="password_reset_confirm"),

    path("reset/done/",
         auth_views.PasswordResetCompleteView.as_view(
             template_name="core/password_reset/password_reset_complete.html"
         ),
         name="password_reset_complete"),
    path('dashboard/', DashboardView.as_view(), name='dashboard'),
    path('track-visit/', track_visit, name='track_visit'),
    path('about/', AboutView.as_view(), name='about'),
    path('team/', TeamView.as_view(), name='team'),
    path('contact/', ContactView.as_view(), name='contact'),
]
