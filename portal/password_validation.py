from __future__ import annotations

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _


class AlphanumericPasswordValidator:
    """Require a mixed-character password similar to NetBox's local-account defaults."""

    def validate(self, password: str, user=None) -> None:
        if not any(char.isdigit() for char in password):
            raise ValidationError(_("Password must have at least one numeral."))

        if not any(char.isupper() for char in password):
            raise ValidationError(_("Password must have at least one uppercase letter."))

        if not any(char.islower() for char in password):
            raise ValidationError(_("Password must have at least one lowercase letter."))

    def get_help_text(self) -> str:
        return _(
            "Your password must contain at least one numeral, one uppercase letter and one lowercase letter."
        )
