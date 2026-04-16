from django.contrib import admin
from django.urls import include, path

from portal import assessment_views
from portal import views as portal_views


urlpatterns = [
    path("", include("social_django.urls", namespace="social")),
    path("login/", portal_views.login_page, name="portal-login"),
    path("logout/", portal_views.logout_view, name="portal-logout"),
    path("admin/", admin.site.urls),
    path("api/", include("portal.urls")),
    path("", portal_views.home_page, name="portal-home"),
    path("controls/", portal_views.controls_page, name="portal-controls"),
    path("reviews/", portal_views.reviews_page, name="portal-reviews"),
    path("review-tasks/", portal_views.review_tasks_page, name="portal-review-tasks"),
    path("audit-log/", portal_views.audit_log_page, name="portal-audit-log"),
    path("assessments/", assessment_views.assessments_page, name="portal-assessments"),
    path(
        "assessments/runs/<str:run_id>/report/",
        assessment_views.assessment_run_report,
        name="portal-assessment-run-report",
    ),
    path(
        "assessments/runs/<str:run_id>/files/<path:relative_path>",
        assessment_views.assessment_run_artifact,
        name="portal-assessment-run-artifact",
    ),
    path("policies/", portal_views.policies_page, name="portal-policies"),
    path("risks/", portal_views.risks_page, name="portal-risks"),
    path("vendors/", portal_views.vendors_page, name="portal-vendors"),
]
