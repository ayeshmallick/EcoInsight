# core/middleware.py
import datetime
from django.utils import timezone
from django.conf import settings
from django.db import models
from .models import Visit

# throttle: how often to count the same session/user (seconds)
THROTTLE_SECONDS = 0  # default: once per hour

# Paths we should skip counting (the heartbeat endpoint will be added separately)
THROTTLE_SECONDS = 0
SKIP_PATHS = ["/track-visit/"]


class VisitMiddleware:
    """
    Middleware to track visits per day.
      - uses session key or user to identify the visitor,
      - increases today's Visit.count at most once per THROTTLE_SECONDS,
      - stores `last_visit_time` in session for throttle.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # call view
        response = self.get_response(request)

        # process visit after response so we don't delay page rendering
        try:
            self.process_visit(request)
        except Exception:
            # analytics must never break the site
            pass

        return response

    def process_visit(self, request):
        # Only count safe HTTP methods; avoid counting AJAX non-GET resources
        if request.method != "GET":
            return

        path = (request.path or "").lower()

        # skip static/media/admin and the tracking endpoint
        if settings.STATIC_URL and path.startswith(settings.STATIC_URL):
            return
        if settings.MEDIA_URL and path.startswith(settings.MEDIA_URL):
            return
        if path.startswith("/admin/"):
            return
        if path in SKIP_PATHS:
            return

        session = request.session
        now = timezone.now()

        # read last visit time (isoformat stored)
        last_ts = session.get("last_visit_time")
        if last_ts:
            try:
                # parse isoformat; handle naive/tz-aware robustly
                last_time = datetime.datetime.fromisoformat(last_ts)
                if last_time.tzinfo is None:
                    last_time = last_time.replace(tzinfo=timezone.utc)
            except Exception:
                last_time = now - datetime.timedelta(seconds=THROTTLE_SECONDS + 1)
        else:
            last_time = now - datetime.timedelta(seconds=THROTTLE_SECONDS + 1)

        # Throttle - only count if enough time elapsed since last count
        if (now - last_time).total_seconds() < THROTTLE_SECONDS:
            return

        # Save the time we last counted so we won't count again until throttle window passes
        session["last_visit_time"] = now.isoformat()

        today = now.date()

        # Update Visit row: either by user or session_key for anonymous
        if request.user.is_authenticated:
            visit_obj, created = Visit.objects.get_or_create(
                user=request.user, date=today, defaults={"count": 0}
            )
        else:
            # ensure session has a session_key
            if not session.session_key:
                session.save()
            sk = session.session_key
            if not sk:
                return
            visit_obj, created = Visit.objects.get_or_create(
                session_key=sk, date=today, defaults={"count": 0}
            )

        # atomic increment (use F to avoid race conditions)
        Visit.objects.filter(pk=visit_obj.pk).update(count=models.F("count") + 1, last_seen=now)
        # refresh from db to keep object consistent if needed
        try:
            visit_obj.refresh_from_db()
        except Exception:
            pass
