# core/context_processors.py

from django.utils import timezone
from django.db.models import Sum
from django.contrib.auth import get_user_model
from .models import Article
from django.db.models import Value
from django.db.models.functions import Lower

User = get_user_model()


def recent_articles_context(request):
    """
    Adds a small site context:
      - recent_articles_session: Article queryset for article IDs stored in session (if any)
      - visit_total & visit_last_seen for authenticated users (if Visit model exists)
    Defensive: failures won't break page rendering.
    """
    ctx = {}

    try:
        # recent articles from session (store article PKs in session['recent_articles'])
        raw_ids = request.session.get("recent_articles", []) or []
        # normalize to ints and preserve order & uniqueness
        recent_ids = []
        for x in raw_ids:
            try:
                ix = int(x)
            except Exception:
                continue
            if ix not in recent_ids:
                recent_ids.append(ix)

        if recent_ids:
            recent = Article.objects.filter(pk__in=recent_ids).order_by('-publish_date')[:6]
            # preserve the session order
            articles_map = {a.pk: a for a in recent}
            ordered = [articles_map[pk] for pk in recent_ids if pk in articles_map]
            ctx['recent_articles_session'] = ordered
        else:
            ctx['recent_articles_session'] = []
    except Exception:
        ctx['recent_articles_session'] = []

    # optional visit stats if Visit model exists
    try:
        from .models import Visit  # local import for safety
        if request.user.is_authenticated:
            total = Visit.objects.filter(user=request.user).aggregate(total=Sum('count'))['total'] or 0
            last_visit = Visit.objects.filter(user=request.user).order_by('-last_seen').first()
            ctx['visit_total'] = total
            ctx['visit_last_seen'] = getattr(last_visit, 'last_seen', None)
        else:
            ctx.setdefault('visit_total', 0)
            ctx.setdefault('visit_last_seen', None)
    except Exception:
        # no Visit model or other error — keep defaults
        ctx.setdefault('visit_total', 0)
        ctx.setdefault('visit_last_seen', None)

    return ctx


def search_filters(request):
    """
    Provides lists for dropdowns: authors, tags, categories (if available).
      - authors: list of (id, username)
      - tags: list of unique tag strings (split on comma)
      - categories: list of unique category values if Article has category attribute
    This builds authors from the Article table to avoid depending on a specific related_name.
    """
    authors = []
    try:
        # safer: derive author ids directly from Article table (works regardless of related_name)
        author_ids = Article.objects.values_list('author_id', flat=True).distinct()
        authors_qs = User.objects.filter(pk__in=author_ids)
        authors = [(u.pk, getattr(u, 'username', str(u))) for u in authors_qs]
    except Exception:
        authors = []

    # TAGS: read Article.tags (assumes a comma-separated string)
    tags_set = set()
    try:
        for a in Article.objects.exclude(tags__isnull=True).exclude(tags__exact='').values_list('tags', flat=True):
            for t in str(a).split(','):
                t = t.strip()
                if t:
                    tags_set.add(t)
    except Exception:
        tags_set = set()
    tags = sorted(tags_set, key=lambda s: s.lower())

    # CATEGORIES (optional): only if Article has attribute 'category' (string or FK handled simply)
    categories = []
    try:
        if hasattr(Article, 'category'):
            # try to pull string categories; if it's a FK, we attempt to read its string value
            raw_cats = Article.objects.exclude(category__isnull=True).exclude(category__exact='').values_list('category', flat=True).distinct()
            cats = [str(c).strip() for c in raw_cats if c and str(c).strip()]
            categories = sorted(set(cats), key=lambda s: s.lower())
    except Exception:
        categories = []

    return {
        'filter_authors': authors,
        'filter_tags': tags,
        'filter_categories': categories,
    }
