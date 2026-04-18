from __future__ import annotations

from collections import defaultdict
from typing import Iterable

from django.db.models import Q, QuerySet

from .models import (
    PortalAction,
    PortalPermissionGrant,
    PortalResource,
    ReviewChecklistItem,
    ReviewChecklistRecommendation,
    RiskRecord,
    UploadedPolicy,
    VendorResponse,
    ZeroTrustAssessmentArtifact,
    ZeroTrustAssessmentRun,
    ZeroTrustAssessmentRunLog,
    ZeroTrustCertificate,
    ZeroTrustTenantProfile,
)

PermissionRequirement = tuple[str, str]

PAGE_PERMISSION_REQUIREMENTS: dict[str, tuple[PermissionRequirement, ...]] = {
    "home": (
        (PortalResource.POLICY_DOCUMENT, PortalAction.VIEW),
        (PortalResource.MAPPING, PortalAction.VIEW),
        (PortalResource.CONTROL_STATE, PortalAction.VIEW),
        (PortalResource.REVIEW_STATE, PortalAction.VIEW),
        (PortalResource.RISK_RECORD, PortalAction.VIEW),
        (PortalResource.VENDOR_RESPONSE, PortalAction.VIEW),
        (PortalResource.ASSESSMENT, PortalAction.VIEW),
        (PortalResource.AUDIT_LOG, PortalAction.VIEW),
    ),
    "controls": (
        (PortalResource.MAPPING, PortalAction.VIEW),
    ),
    "reviews": ((PortalResource.REVIEW_STATE, PortalAction.VIEW),),
    "review-tasks": ((PortalResource.REVIEW_STATE, PortalAction.VIEW),),
    "audit-log": ((PortalResource.AUDIT_LOG, PortalAction.VIEW),),
    "policies": (
        (PortalResource.POLICY_DOCUMENT, PortalAction.VIEW),
        (PortalResource.MAPPING, PortalAction.VIEW),
    ),
    "risks": ((PortalResource.RISK_RECORD, PortalAction.VIEW),),
    "vendors": ((PortalResource.VENDOR_RESPONSE, PortalAction.VIEW),),
    "assessments": ((PortalResource.ASSESSMENT, PortalAction.VIEW),),
}

PORTAL_PERMISSION_CACHE_ATTR = "_portal_permission_index"

MODEL_RESOURCE_MAP = {
    UploadedPolicy: PortalResource.POLICY_DOCUMENT,
    VendorResponse: PortalResource.VENDOR_RESPONSE,
    RiskRecord: PortalResource.RISK_RECORD,
    ReviewChecklistItem: PortalResource.REVIEW_STATE,
    ReviewChecklistRecommendation: PortalResource.REVIEW_STATE,
    ZeroTrustTenantProfile: PortalResource.ASSESSMENT,
    ZeroTrustCertificate: PortalResource.ASSESSMENT,
    ZeroTrustAssessmentRun: PortalResource.ASSESSMENT,
    ZeroTrustAssessmentRunLog: PortalResource.ASSESSMENT,
    ZeroTrustAssessmentArtifact: PortalResource.ASSESSMENT,
}


def clear_portal_permission_cache(user: object | None) -> None:
    if user is not None and hasattr(user, PORTAL_PERMISSION_CACHE_ATTR):
        delattr(user, PORTAL_PERMISSION_CACHE_ATTR)


def normalize_permission_requirement(resource: object, action: object) -> PermissionRequirement:
    normalized_resource = str(resource or "").strip()
    normalized_action = str(action or "").strip()
    if normalized_resource not in PortalResource.values:
        raise ValueError(f"Unsupported portal resource: {resource!r}")
    if normalized_action not in PortalAction.values:
        raise ValueError(f"Unsupported portal action: {action!r}")
    return normalized_resource, normalized_action


def _build_permission_index(user: object) -> dict[str, set[str]]:
    index: dict[str, set[str]] = defaultdict(set)
    if not getattr(user, "is_authenticated", False) or not getattr(user, "is_active", True):
        return index
    if bool(getattr(user, "is_staff", False) or getattr(user, "is_superuser", False)):
        for resource in PortalResource.values:
            index[resource].update(PortalAction.values)
        return index

    grants = PortalPermissionGrant.objects.filter(enabled=True).filter(
        Q(user=user) | Q(group__in=user.groups.all())
    )
    for resource, action in grants.values_list("resource", "action"):
        index[str(resource)].add(str(action))
    return index


def user_portal_permissions(user: object) -> dict[str, set[str]]:
    cached = getattr(user, PORTAL_PERMISSION_CACHE_ATTR, None)
    if isinstance(cached, dict):
        return cached
    index = _build_permission_index(user)
    if user is not None:
        setattr(user, PORTAL_PERMISSION_CACHE_ATTR, index)
    return index


def portal_permissions_for_context(user: object) -> dict[str, list[str]]:
    return {
        resource: sorted(actions)
        for resource, actions in user_portal_permissions(user).items()
        if actions
    }


def has_portal_permission(user: object, resource: object, action: object, obj: object | None = None) -> bool:
    normalized_resource, normalized_action = normalize_permission_requirement(resource, action)
    permission_index = user_portal_permissions(user)
    allowed_actions = permission_index.get(normalized_resource, set())
    if normalized_action not in allowed_actions:
        return False
    # Reserved for future object-scoped constraints.
    _ = obj
    return True


def has_any_portal_permission(user: object, requirements: Iterable[PermissionRequirement]) -> bool:
    return any(has_portal_permission(user, resource, action) for resource, action in requirements)


def portal_resource_for_queryset(queryset: QuerySet[object]) -> str | None:
    model = getattr(queryset, "model", None)
    if model is None:
        return None
    for model_class, resource in MODEL_RESOURCE_MAP.items():
        if issubclass(model, model_class):
            return str(resource)
    return None


def restrict_queryset(
    queryset: QuerySet[object],
    user: object,
    action: object = PortalAction.VIEW,
    *,
    resource: object | None = None,
) -> QuerySet[object]:
    if user is None:
        return queryset
    normalized_resource = str(resource or portal_resource_for_queryset(queryset) or "").strip()
    if not normalized_resource:
        raise ValueError("Portal resource is required to restrict this queryset.")
    if has_portal_permission(user, normalized_resource, action):
        return queryset
    return queryset.none()


def grant_user_portal_permission(
    user: object,
    resource: object,
    action: object,
    *,
    name: str = "",
    description: str = "",
    constraints: dict[str, object] | None = None,
) -> PortalPermissionGrant:
    normalized_resource, normalized_action = normalize_permission_requirement(resource, action)
    grant, _ = PortalPermissionGrant.objects.update_or_create(
        user=user,
        resource=normalized_resource,
        action=normalized_action,
        defaults={
            "name": name,
            "description": description,
            "constraints": constraints or {},
            "enabled": True,
            "group": None,
        },
    )
    clear_portal_permission_cache(user)
    return grant


def grant_group_portal_permission(
    group: object,
    resource: object,
    action: object,
    *,
    name: str = "",
    description: str = "",
    constraints: dict[str, object] | None = None,
) -> PortalPermissionGrant:
    normalized_resource, normalized_action = normalize_permission_requirement(resource, action)
    return PortalPermissionGrant.objects.update_or_create(
        group=group,
        resource=normalized_resource,
        action=normalized_action,
        defaults={
            "name": name,
            "description": description,
            "constraints": constraints or {},
            "enabled": True,
            "user": None,
        },
    )[0]


__all__ = [
    "PAGE_PERMISSION_REQUIREMENTS",
    "PermissionRequirement",
    "PortalAction",
    "PortalResource",
    "clear_portal_permission_cache",
    "grant_group_portal_permission",
    "grant_user_portal_permission",
    "has_any_portal_permission",
    "has_portal_permission",
    "portal_permissions_for_context",
    "portal_resource_for_queryset",
    "restrict_queryset",
    "user_portal_permissions",
]
