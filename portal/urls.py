from django.urls import path

from . import (
    assessment_report_export_views,
    assessment_views,
    audit_log_export_views,
    policy_download_views,
    risk_csv_views,
    vendor_download_views,
    views,
)


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
    path(
        "assessments/runs/<str:run_id>/export/",
        assessment_report_export_views.assessment_run_report_export,
        name="api-assessment-run-export",
    ),
    path(
        "assessments/reports/export/",
        assessment_report_export_views.assessment_reports_export,
        name="api-assessment-reports-export",
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
    path(
        "policies/<str:document_id>/download/",
        policy_download_views.policy_document_download,
        name="api-policy-document-download",
    ),
    path(
        "policies/downloads/all/",
        policy_download_views.policy_documents_download_all,
        name="api-policy-documents-download-all",
    ),
    path("vendors/uploads/", views.upload_vendors, name="api-vendor-uploads"),
    path("vendors/responses/<str:response_id>/", views.vendor_response, name="api-vendor-response"),
    path(
        "vendors/downloads/",
        vendor_download_views.vendor_response_downloads,
        name="api-vendor-response-downloads",
    ),
    path(
        "vendors/<str:response_id>/download/",
        vendor_download_views.vendor_response_download,
        name="api-vendor-response-download",
    ),
    path(
        "vendors/downloads/all/",
        vendor_download_views.vendor_response_download_all,
        name="api-vendor-response-download-all",
    ),
    path("risks/", views.risk_register, name="api-risks"),
    path(
        "risks/export.csv",
        risk_csv_views.risk_register_csv_export,
        name="api-risk-register-export-csv",
    ),
    path(
        "risks/import.csv",
        risk_csv_views.risk_register_csv_import,
        name="api-risk-register-import-csv",
    ),
    path("risks/<str:risk_id>/", views.risk_record, name="api-risk-record"),
    path(
        "audit-log/export.csv",
        audit_log_export_views.audit_log_export_csv,
        name="api-audit-log-export-csv",
    ),
    path("checklist/", views.checklist_items, name="api-checklist-items"),
    path("checklist/<str:checklist_item_id>/", views.checklist_item, name="api-checklist-item"),
    path("state/mapping/", views.mapping_state, name="api-mapping-state"),
    path("state/review/", views.review_state, name="api-review-state"),
    path("state/control/", views.control_state, name="api-control-state"),
]
