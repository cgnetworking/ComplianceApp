from __future__ import annotations

from portal.authorization import grant_group_portal_permission, grant_user_portal_permission


def grant_user_permissions(user: object, *requirements: tuple[str, str]) -> None:
    for resource, action in requirements:
        grant_user_portal_permission(user, resource, action)


def grant_group_permissions(group: object, *requirements: tuple[str, str]) -> None:
    for resource, action in requirements:
        grant_group_portal_permission(group, resource, action)
