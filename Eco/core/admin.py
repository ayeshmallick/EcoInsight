from django.contrib import admin
from .models import User, Article, ResearchPaper
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Role', {'fields': ('role',)}),
    )

@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = ('title', 'author', 'published', 'publish_date')
    prepopulated_fields = {"slug": ("title",)}
    search_fields = ('title', 'content', 'summary', 'tags')

@admin.register(ResearchPaper)
class ResearchPaperAdmin(admin.ModelAdmin):
    list_display = ('title', 'uploaded_by', 'published', 'created_at')
    prepopulated_fields = {"slug": ("title",)}
