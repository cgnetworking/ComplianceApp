from django.urls import path

from . import assessment_views, views


urlpatterns = [
    path("state/", views.bootstrap_state, name="api-state"),
    path("assessments/", assessment_views.assessments_collection, name="api-assessments"),
    path("assessments/<str:profile_id>/", assessment_views.assessment_profile_detail, name="api-assessment-profile"),
    path(
        "assessments/<str:profile_id>/certificate/",
        assessment_views.assessment_profile_certificate,
        name="api-assessment-profile-certificate",
    ),
    path(
        "assessments/<str:profile_id>/certificate.cer",
        assessment_views.assessment_profile_certificate_download,
        name="api-assessment-profile-certificate-download",
    ),
    path(
        "assessments/<str:profile_id>/runs/",
        assessment_views.assessment_profile_runs,
        name="api-assessment-profile-runs",
    ),
    path("assessments/runs/<str:run_id>/", assessment_views.assessment_run_detail, name="api-assessment-run"),
    path(
        "assessments/runs/<str:run_id>/logs/",
        assessment_views.assessment_run_logs,
        name="api-assessment-run-logs",
    ),
    path("mapping/uploads/", views.upload_mapping, name="api-mapping-uploads"),
    path("policies/uploads/", views.upload_policies, name="api-policy-uploads"),
    path("policies/<str:document_id>/", views.policy_document, name="api-policy-document"),
    path(
        "policies/<str:document_id>/approver/",
        views.policy_document_approver,
        name="api-policy-document-approver",
    ),
    path(
        "policies/<str:document_id>/approval/",
        views.policy_document_approval,
        name="api-policy-document-approval",
    ),
    path("vendors/uploads/", views.upload_vendors, name="api-vendor-uploads"),
    path("risks/", views.risk_register, name="api-risks"),
    path("checklist/", views.checklist_items, name="api-checklist-items"),
    path("checklist/<str:checklist_item_id>/", views.checklist_item, name="api-checklist-item"),
    path("state/mapping/", views.mapping_state, name="api-mapping-state"),
    path("state/review/", views.review_state, name="api-review-state"),
    path("state/control/", views.control_state, name="api-control-state"),
]
