from django.contrib import admin
from django.urls import include, path

from portal import views as portal_views


urlpatterns = [
    path("", include("social_django.urls", namespace="social")),
    path("login/", portal_views.login_page, name="portal-login"),
    path("logout/", portal_views.logout_view, name="portal-logout"),
    path("admin/", admin.site.urls),
    path("api/", include("portal.urls")),
    path("", portal_views.home_page, name="portal-home"),
    path("index.html", portal_views.home_page, name="portal-index"),
    path("controls.html", portal_views.controls_page, name="portal-controls"),
    path("reports.html", portal_views.reports_page, name="portal-reports"),
    path("reviews.html", portal_views.reviews_page, name="portal-reviews"),
    path("review-tasks.html", portal_views.review_tasks_page, name="portal-review-tasks"),
    path("audit-log.html", portal_views.audit_log_page, name="portal-audit-log"),
    path("policies.html", portal_views.policies_page, name="portal-policies"),
    path("risks.html", portal_views.risks_page, name="portal-risks"),
    path("vendors.html", portal_views.vendors_page, name="portal-vendors"),
]
