from django.urls import path

from . import views


urlpatterns = [
    path("state/", views.bootstrap_state, name="api-state"),
    path("mapping/uploads/", views.upload_mapping, name="api-mapping-uploads"),
    path("policies/uploads/", views.upload_policies, name="api-policy-uploads"),
    path("vendors/uploads/", views.upload_vendors, name="api-vendor-uploads"),
    path("risks/", views.risk_register, name="api-risks"),
    path("checklist/", views.checklist_items, name="api-checklist-items"),
    path("state/mapping/", views.mapping_state, name="api-mapping-state"),
    path("state/review/", views.review_state, name="api-review-state"),
    path("state/control/", views.control_state, name="api-control-state"),
]
