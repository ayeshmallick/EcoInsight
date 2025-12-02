from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import ListView, DetailView, CreateView, UpdateView, TemplateView, FormView
from .models import Article, ResearchPaper, Visit
from .forms import SignUpForm, ArticleForm, ResearchPaperForm
from django.urls import reverse_lazy
from django.contrib.auth import login
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import Q, Sum
from django.core.paginator import Paginator
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django.shortcuts import redirect, render
from django.core.exceptions import PermissionDenied
from datetime import timedelta
from django.utils import timezone
from django.http import JsonResponse
from django.db.models import F
from django.views.decorators.http import require_GET
from django.core.paginator import Paginator
from django.core.mail import EmailMessage
from django.contrib import messages
from .forms import ContactForm


# Basic index: list of published articles and papers
class IndexView(ListView):
    model = Article
    template_name = 'core/index.html'
    context_object_name = 'articles'
    paginate_by = 6

    def get_queryset(self):
        return Article.objects.filter(published=True).order_by('-publish_date')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        # today's date
        today = timezone.now().date()

        # Global: sum of counts for today
        total = Visit.objects.filter(date=today).aggregate(total=Sum('count'))['total'] or 0
        ctx['total_visits_today'] = total

        # Per-user: if logged in
        user_visits = 0
        if self.request.user.is_authenticated:
            user_visits = Visit.objects.filter(user=self.request.user, date=today).aggregate(total=Sum('count'))[
                              'total'] or 0
        ctx['user_visits_today'] = user_visits

        # Optionally expose recently viewed (if you like)
        recent_ids = self.request.session.get('recent_articles', [])[:6]
        if recent_ids:
            ctx['recent_articles_session'] = Article.objects.filter(pk__in=recent_ids).order_by('-publish_date')

        return ctx

class ArticleDetailView(DetailView):
    model = Article
    template_name = 'core/article_detail.html'
    context_object_name = 'article'
    slug_field = 'slug'
    slug_url_kwarg = 'slug'

    def get(self, request, *args, **kwargs):
        # call the parent to build the response/context first
        response = super().get(request, *args, **kwargs)

        # Safely update session-based recently viewed list
        try:
            article = self.get_object()
            session = request.session

            # read session list and normalize to ints
            raw = session.get('recent_articles', [])
            normalized = []
            for item in raw:
                try:
                    normalized.append(int(item))
                except Exception:
                    # ignore bad values
                    continue

            # remove existing occurrence if present (safe)
            if article.pk in normalized:
                normalized.remove(article.pk)

            # insert at front
            normalized.insert(0, article.pk)

            # cap list length
            MAX_RECENT = 10
            session['recent_articles'] = normalized[:MAX_RECENT]
            # mark session modified so Django saves it
            session.modified = True
        except Exception:
            # never break the page for analytics bugs
            pass

        return response

# Create / Edit mixins for role-based access
class EditorRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        user = self.request.user
        return user.is_authenticated and (user.is_editor or user.is_admin)

    def handle_no_permission(self):
        # redirect to login page if not authenticated, otherwise show 403-like redirect to home
        if not self.request.user.is_authenticated:
            return redirect('login')
        return redirect('index')

class EditorStrictMixin(UserPassesTestMixin):
    """
    Strict mixin: redirect to login if not authenticated; raise 403 if authenticated but not editor.
    """
    def test_func(self):
        user = getattr(self.request, "user", None)
        return bool(user and user.is_authenticated and (user.is_editor or user.is_admin))

    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            return redirect('login')
        raise PermissionDenied("You must be an editor to access this page")

class ArticleCreateView(LoginRequiredMixin, EditorRequiredMixin, CreateView):
    model = Article
    form_class = ArticleForm
    template_name = 'core/article_form.html'
    success_url = reverse_lazy('index')

    def form_valid(self, form):
        form.instance.author = self.request.user
        return super().form_valid(form)

class ArticleUpdateView(LoginRequiredMixin, EditorRequiredMixin, UpdateView):
    model = Article
    form_class = ArticleForm
    template_name = 'core/article_form.html'
    success_url = reverse_lazy('index')

# Research paper views (similar)
class PaperDetailView(DetailView):
    model = ResearchPaper
    template_name = 'core/article_detail.html'  # reuse detail template
    context_object_name = 'article'

class PaperCreateView(LoginRequiredMixin, EditorRequiredMixin, CreateView):
    model = ResearchPaper
    form_class = ResearchPaperForm
    template_name = 'core/article_form.html'
    success_url = reverse_lazy('index')

# Signup
def signup_view(request):
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('index')
    else:
        form = SignUpForm()
    return render(request, 'core/signup.html', {'form': form})

# Simple search parser supporting AND / OR / phrase queries
def parse_search_query(q):
    import re
    tokens = re.findall(r'"([^"]+)"|(\S+)', q)
    cleaned = []
    for t1, t2 in tokens:
        token = t1 if t1 else t2
        cleaned.append(token)
    return cleaned

def search_view(request):
    q = request.GET.get('q', '').strip()
    selected_author = request.GET.get('author', '').strip()
    selected_tag = request.GET.get('tag', '').strip()
    selected_category = request.GET.get('category', '').strip()

    results = Article.objects.filter(published=True)

    # text query
    if q:
        tokens = parse_search_query(q)
        q_obj = None
        current_op = 'AND'
        for token in tokens:
            if token.upper() == 'OR':
                current_op = 'OR'
                continue
            token_q = (Q(title__icontains=token) |
                       Q(content__icontains=token) |
                       Q(summary__icontains=token) |
                       Q(tags__icontains=token))
            if q_obj is None:
                q_obj = token_q
            else:
                if current_op == 'AND':
                    q_obj = q_obj & token_q
                else:
                    q_obj = q_obj | token_q
            current_op = 'AND'
        if q_obj is not None:
            results = results.filter(q_obj)

    # author filter (id or username)
    if selected_author:
        try:
            uid = int(selected_author)
            results = results.filter(author__pk=uid)
        except Exception:
            results = results.filter(author__username__iexact=selected_author)

    # tag filter (simple contains)
    if selected_tag:
        results = results.filter(tags__icontains=selected_tag)

    # category filter (if Article has category field)
    if selected_category and hasattr(Article, 'category'):
        results = results.filter(category__iexact=selected_category)

    results = results.distinct().order_by('-publish_date')

    paginator = Paginator(results, 8)
    page = request.GET.get('page')
    page_obj = paginator.get_page(page)

    context = {
        'query': q,
        'page_obj': page_obj,
        'selected_author': selected_author,
        'selected_tag': selected_tag,
        'selected_category': selected_category,
    }
    return render(request, 'core/search_results.html', context)

# Basic context processor for recent articles (based on session)
def recent_articles_context(request):
    recent_ids = request.session.get('recent_articles', [])
    articles = Article.objects.filter(pk__in=recent_ids)
    # Preserve order:
    ordered = sorted(articles, key=lambda a: recent_ids.index((a.pk)))
    return {'recent_articles_session': ordered}

class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'core/dashboard.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        # total visits across dates
        total = Visit.objects.filter(user=user).aggregate(total=Sum('count'))['total'] or 0
        last_visit = Visit.objects.filter(user=user).order_by('-last_seen').first()
        ctx['visit_total'] = total
        ctx['visit_last_seen'] = getattr(last_visit, 'last_seen', None)
        # recently viewed
        recent_ids = self.request.session.get('recent_articles', [])[:10]
        ctx['recently_viewed'] = Article.objects.filter(pk__in=recent_ids).order_by('-publish_date')
        # optionally include last 7 days visits
        today = timezone.now().date()
        last_week = Visit.objects.filter(user=user, date__gte=today - timezone.timedelta(days=7)).order_by('date')
        ctx['last_week_visits'] = last_week
        return ctx

@require_GET
def track_visit(request):
    """
    Endpoint to be polled by JS (every second). It increments today's Visit
    (per-user if authenticated, else per-session) and returns the totals:
      { "total_today": int, "user_today": int_or_null }
    """
    from .models import Visit  # local import to avoid circular issues
    from django.utils import timezone
    now = timezone.now()
    today = now.date()

    # identify visitor: prefer authenticated user, otherwise session key
    user = request.user if request.user.is_authenticated else None

    # ensure session key exists for anonymous users
    if not user:
        if not request.session.session_key:
            request.session.save()
        sk = request.session.session_key
        if not sk:
            return JsonResponse({"error": "no session"}, status=400)
    else:
        sk = None

    # increment (atomic) for the relevant Visit row
    if user:
        visit_obj, created = Visit.objects.get_or_create(user=user, date=today, defaults={"count": 0})
        Visit.objects.filter(pk=visit_obj.pk).update(count=F("count") + 1)
        visit_obj.refresh_from_db()
        user_count = visit_obj.count
    else:
        visit_obj, created = Visit.objects.get_or_create(session_key=sk, date=today, defaults={"count": 0})
        Visit.objects.filter(pk=visit_obj.pk).update(count=F("count") + 1)
        visit_obj.refresh_from_db()
        user_count = visit_obj.count

    # global total for today
    total = Visit.objects.filter(date=today).aggregate(total=Sum("count"))["total"] or 0

    return JsonResponse({
        "total_today": int(total),
        "user_today": int(user_count),
    })

class AboutView(TemplateView):
    template_name = "core/about.html"

class TeamView(TemplateView):
    template_name = "core/team.html"

class ContactView(FormView):
    template_name = "core/contact.html"
    form_class = ContactForm
    success_url = reverse_lazy('contact')  # or reverse_lazy('contact') to stay on page

    def form_valid(self, form):
        # send email using console email backend in development
        name = form.cleaned_data['name']
        email = form.cleaned_data['email']
        subject = form.cleaned_data['subject']
        message = form.cleaned_data['message']

        full_message = f"Contact form submitted\n\nFrom: {name} <{email}>\n\nMessage:\n{message}"

        # Use EmailMessage to send via configured backend (console for dev)
        try:
            email_msg = EmailMessage(
                subject=f"[Contact] {subject}",
                body=full_message,
                from_email=None,  # will use DEFAULT_FROM_EMAIL if set in settings
                to=[self.request.site_admin_email] if hasattr(self.request, 'site_admin_email') else None,
            )
            # If no recipient supplied above, fallback to DEFAULT_FROM_EMAIL (console backend just prints)
            if not email_msg.to or email_msg.to == [None]:
                # send to DEFAULT_FROM_EMAIL if configured; otherwise console will still print
                email_msg.to = [None]

            email_msg.send(fail_silently=False)
        except Exception:
            # don't break on email errors for demo
            pass

        messages.success(self.request, "Thanks — your message was submitted. We'll get back to you soon.")
        return super().form_valid(form)