from __future__ import annotations

from pathlib import Path

from django.db import migrations, models


def copy_certificate_pfx_to_database(apps, schema_editor) -> None:
    ZeroTrustCertificate = apps.get_model("portal", "ZeroTrustCertificate")

    for certificate in ZeroTrustCertificate.objects.all().only("id", "pfx_bytes", "pfx_path"):
        if certificate.pfx_bytes:
            continue
        pfx_path = str(getattr(certificate, "pfx_path", "")).strip()
        if not pfx_path:
            continue

        path = Path(pfx_path)
        if not path.exists() or not path.is_file():
            continue

        try:
            certificate.pfx_bytes = path.read_bytes()
        except OSError:
            continue
        certificate.save(update_fields=["pfx_bytes"])


class Migration(migrations.Migration):

    dependencies = [
        ("portal", "0008_zerotrustassessment"),
    ]

    operations = [
        migrations.AddField(
            model_name="zerotrustcertificate",
            name="pfx_bytes",
            field=models.BinaryField(blank=True, default=b""),
        ),
        migrations.RunPython(copy_certificate_pfx_to_database, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="zerotrustcertificate",
            name="certificate_path",
        ),
        migrations.RemoveField(
            model_name="zerotrustcertificate",
            name="private_key_path",
        ),
        migrations.RemoveField(
            model_name="zerotrustcertificate",
            name="pfx_path",
        ),
        migrations.RemoveField(
            model_name="zerotrustrun",
            name="staged_path",
        ),
        migrations.RemoveField(
            model_name="zerotrustrun",
            name="cleaned_up_at",
        ),
    ]
