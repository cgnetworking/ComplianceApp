from django.urls import path

from . import views


urlpatterns = [
    path("state/", views.bootstrap_state, name="api-state"),
    path("zero-trust/status/", views.zero_trust_assessment_status, name="api-zero-trust-status"),
    path(
        "zero-trust/authentication/",
        views.zero_trust_assessment_authentication,
        name="api-zero-trust-authentication",
    ),
    path(
        "zero-trust/certificate/",
        views.zero_trust_assessment_certificate,
        name="api-zero-trust-certificate",
    ),
    path(
        "zero-trust/certificate/public-key/",
        views.zero_trust_assessment_certificate_public_key,
        name="api-zero-trust-certificate-public-key",
    ),
    path("zero-trust/run/", views.zero_trust_assessment_run, name="api-zero-trust-run"),
    path("zero-trust/report/", views.zero_trust_assessment_report, name="api-zero-trust-report"),
    path("mapping/uploads/", views.upload_mapping, name="api-mapping-uploads"),
    path("policies/uploads/", views.upload_policies, name="api-policy-uploads"),
    path("policies/<str:document_id>/", views.policy_document, name="api-policy-document"),
    path(
        "policies/<str:document_id>/approver/",
        views.policy_document_approver,
        name="api-policy-document-approver",
    ),
    path("vendors/uploads/", views.upload_vendors, name="api-vendor-uploads"),
    path("risks/", views.risk_register, name="api-risks"),
    path("checklist/", views.checklist_items, name="api-checklist-items"),
    path("checklist/recommended/", views.checklist_recommendations, name="api-checklist-recommendations"),
    path("checklist/<str:checklist_item_id>/", views.checklist_item, name="api-checklist-item"),
    path("state/mapping/", views.mapping_state, name="api-mapping-state"),
    path("state/review/", views.review_state, name="api-review-state"),
    path("state/control/", views.control_state, name="api-control-state"),
]
