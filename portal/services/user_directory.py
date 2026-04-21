from __future__ import annotations

from django.contrib.auth import get_user_model

OWNER_ASSIGNABLE_PAGES = frozenset({"controls", "reviews", "risks"})


def normalize_user_identifier(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def serialize_assignable_user(user: object) -> dict[str, str] | None:
    user_model = get_user_model()
    username_field = getattr(user_model, "USERNAME_FIELD", "username")
    username = normalize_user_identifier(getattr(user, username_field, ""))
    if not username:
        return None
    first_name = normalize_user_identifier(getattr(user, "first_name", ""))
    last_name = normalize_user_identifier(getattr(user, "last_name", ""))
    full_name = " ".join(part for part in [first_name, last_name] if part).strip()
    email = normalize_user_identifier(getattr(user, "email", ""))
    return {"username": username, "displayName": full_name or email or username}


def list_assignable_users() -> list[dict[str, str]]:
    user_model = get_user_model()
    username_field = getattr(user_model, "USERNAME_FIELD", "username")
    assignable_users: list[dict[str, str]] = []
    for user in user_model.objects.filter(is_active=True).order_by(username_field):
        serialized_user = serialize_assignable_user(user)
        if serialized_user is None:
            continue
        assignable_users.append(serialized_user)
    return assignable_users


def list_assignable_users_for_viewer(viewer: object | None, *, page: str = "") -> list[dict[str, str]]:
    if not getattr(viewer, "is_authenticated", False):
        return []
    if bool(getattr(viewer, "is_staff", False)):
        return list_assignable_users()
    if page not in OWNER_ASSIGNABLE_PAGES:
        return []

    serialized_user = serialize_assignable_user(viewer)
    return [serialized_user] if serialized_user is not None else []


def viewer_can_assign_username(viewer: object | None, username: object, *, page: str = "") -> bool:
    normalized_username = normalize_user_identifier(username)
    if not normalized_username:
        return False
    if viewer is None or not getattr(viewer, "is_authenticated", False):
        return True
    if bool(getattr(viewer, "is_staff", False)):
        return True
    if page not in OWNER_ASSIGNABLE_PAGES:
        return True

    serialized_user = serialize_assignable_user(viewer)
    if serialized_user is None:
        return False
    return normalize_user_identifier(serialized_user.get("username")).lower() == normalized_username.lower()


def resolve_assignable_username(identifier: object, *, viewer: object | None = None, page: str = "") -> str:
    normalized_identifier = normalize_user_identifier(identifier)
    if not normalized_identifier:
        return ""

    user_model = get_user_model()
    username_field = getattr(user_model, "USERNAME_FIELD", "username")
    user = user_model.objects.filter(is_active=True).filter(**{f"{username_field}__iexact": normalized_identifier}).first()
    if user is None:
        has_email_field = any(getattr(field, "name", "") == "email" for field in user_model._meta.get_fields())
        if has_email_field:
            user = user_model.objects.filter(is_active=True, email__iexact=normalized_identifier).first()
    if user is None:
        return ""

    resolved_username = normalize_user_identifier(getattr(user, username_field, ""))
    if not viewer_can_assign_username(viewer, resolved_username, page=page):
        return ""

    return resolved_username


__all__ = [
    "OWNER_ASSIGNABLE_PAGES",
    "normalize_user_identifier",
    "serialize_assignable_user",
    "list_assignable_users",
    "list_assignable_users_for_viewer",
    "viewer_can_assign_username",
    "resolve_assignable_username",
]
