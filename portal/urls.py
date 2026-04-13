from django.urls import path

from . import views


urlpatterns = [
    path("state/", views.bootstrap_state, name="api-state"),
    path("policies/uploads/", views.upload_policies, name="api-policy-uploads"),
    path("vendors/uploads/", views.upload_vendors, name="api-vendor-uploads"),
    path("risks/", views.risk_register, name="api-risks"),
    path("state/review/", views.review_state, name="api-review-state"),
    path("state/control/", views.control_state, name="api-control-state"),
]
