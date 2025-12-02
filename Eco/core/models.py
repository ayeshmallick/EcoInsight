# core/models.py
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.conf import settings
from django.utils import timezone

class User(AbstractUser):
    phone = models.CharField(max_length=20, blank=True)
    ROLE_CHOICES = (
        ('admin', 'Admin'),
        ('editor', 'Editor'),
        ('user', 'User'),
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='user')

    @property
    def is_editor(self):
        # property so templates can use user.is_editor
        return self.role == 'editor' or self.is_superuser

    @property
    def is_admin(self):
        return self.role == 'admin' or self.is_superuser

    def is_author(self, obj):
        # utility: true if this user is the author of an object with .author FK
        return getattr(obj, 'author_id', None) == self.pk


# Content types: Article and ResearchPaper (similar structure)
class Article(models.Model):
    title = models.CharField(max_length=300)
    slug = models.SlugField(max_length=320, unique=True)
    summary = models.TextField(blank=True)
    content = models.TextField()
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='articles')
    published = models.BooleanField(default=False)
    publish_date = models.DateTimeField(default=timezone.now)
    cover_image = models.ImageField(upload_to='articles/images/', blank=True, null=True)
    attachment = models.FileField(upload_to='articles/files/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    tags = models.CharField(max_length=300, blank=True)  # simple comma-separated tags

    @property
    def tag_list(self):
        if self.tags:
            return [tag.strip() for tag in self.tags.split(',')]
        return []

    class Meta:
        ordering = ['-publish_date']

    def __str__(self):
        return self.title


class ResearchPaper(models.Model):
    title = models.CharField(max_length=300)
    slug = models.SlugField(max_length=320, unique=True)
    abstract = models.TextField(blank=True)
    content = models.TextField()
    authors = models.CharField(max_length=500, blank=True)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
                                    related_name='papers')
    pdf = models.FileField(upload_to='papers/', blank=True, null=True)
    published = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    @property
    def is_editor(self):
        return self.role == 'editor' or self.is_superuser

    @property
    def is_admin(self):
        return self.role == 'admin' or self.is_superuser

class Visit(models.Model):
    """
    Track daily visits per user or per anonymous session.
    - If user is authenticated, user is set.
    - If anonymous, session_key is used.
    One row per (user or session_key) per date.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="visits",
    )
    session_key = models.CharField(max_length=40, blank=True, null=True, db_index=True)
    date = models.DateField(db_index=True)
    count = models.PositiveIntegerField(default=0)
    last_seen = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = (
            ("user", "date"),
            ("session_key", "date"),
        )
        indexes = [
            models.Index(fields=["date"]),
            models.Index(fields=["session_key"]),
        ]

    def __str__(self):
        if self.user:
            return f"Visits for {self.user.username} on {self.date}: {self.count}"
        return f"Visits for session {self.session_key} on {self.date}: {self.count}"