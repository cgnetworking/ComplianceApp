from __future__ import annotations

import json
import re
from io import BytesIO
from pathlib import PurePosixPath
from zipfile import ZIP_DEFLATED, ZipFile

from django.utils import timezone

from ..assessment_services import AssessmentValidationError, get_zero_trust_run
from ..models import ZeroTrustAssessmentArtifact, ZeroTrustAssessmentRun, ZeroTrustTenantProfile

SAFE_FILENAME_RE = re.compile(r"[^A-Za-z0-9._-]+")


def normalize_export_string(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def safe_filename_component(value: object, fallback: str) -> str:
    normalized = normalize_export_string(value)
    if not normalized:
        return fallback
    sanitized = SAFE_FILENAME_RE.sub("-", normalized).strip("-.")
    return sanitized or fallback


def safe_zip_relative_path(value: object) -> str:
    normalized = str(PurePosixPath(normalize_export_string(value)))
    path = PurePosixPath(normalized)
    if not normalized or normalized in {".", ".."}:
        raise AssessmentValidationError("Assessment artifact path is invalid.")
    if path.is_absolute() or ".." in path.parts:
        raise AssessmentValidationError("Assessment artifact path is invalid.")
    return normalized


def exportable_run_artifacts(run: ZeroTrustAssessmentRun) -> list[ZeroTrustAssessmentArtifact]:
    if not run.has_report:
        raise AssessmentValidationError("This assessment run does not have a stored report.")
    artifacts = sorted(run.artifacts.all(), key=lambda artifact: artifact.relative_path)
    if not artifacts:
        raise AssessmentValidationError("Stored assessment report artifacts were not found.")
    return artifacts


def exportable_runs(*, profile_id: str = "") -> list[ZeroTrustAssessmentRun]:
    normalized_profile_id = normalize_export_string(profile_id)
    if normalized_profile_id and not ZeroTrustTenantProfile.objects.filter(external_id=normalized_profile_id).exists():
        raise AssessmentValidationError("Assessment profile was not found.")

    queryset = (
        ZeroTrustAssessmentRun.objects.exclude(entrypoint_relative_path="")
        .select_related("profile")
        .prefetch_related("artifacts")
        .order_by("-created_at")
    )
    if normalized_profile_id:
        queryset = queryset.filter(profile__external_id=normalized_profile_id)

    runs = list(queryset)
    if not runs:
        raise AssessmentValidationError("No stored assessment reports are available for export.")
    return runs


def unique_zip_path(path_value: str, used_paths: set[str]) -> str:
    normalized = str(PurePosixPath(path_value))
    if normalized not in used_paths:
        used_paths.add(normalized)
        return normalized

    suffix_counter = 2
    candidate_path = PurePosixPath(normalized)
    while True:
        stem = candidate_path.stem
        suffix = "".join(candidate_path.suffixes)
        replacement_name = f"{stem}-{suffix_counter}{suffix}" if suffix else f"{stem}-{suffix_counter}"
        replacement_path = candidate_path.with_name(replacement_name)
        replacement = str(replacement_path)
        if replacement not in used_paths:
            used_paths.add(replacement)
            return replacement
        suffix_counter += 1


def archive_manifest_bytes(payload: dict[str, object]) -> bytes:
    return (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")


def run_archive_folder(run: ZeroTrustAssessmentRun, *, index: int | None = None) -> str:
    tenant_token = safe_filename_component(run.profile.display_name or run.profile.tenant_id, "tenant")
    run_token = safe_filename_component(run.external_id, "run")
    if index is None:
        return f"{tenant_token}-{run_token}"
    return f"{index:03d}-{tenant_token}-{run_token}"


def run_manifest(run: ZeroTrustAssessmentRun, artifacts: list[ZeroTrustAssessmentArtifact], folder_name: str) -> dict[str, object]:
    return {
        "runId": run.external_id,
        "profileId": run.profile.external_id,
        "profileDisplayName": run.profile.display_name or run.profile.tenant_id,
        "tenantId": run.profile.tenant_id,
        "status": run.status,
        "statusMessage": run.status_message,
        "entrypointRelativePath": run.entrypoint_relative_path,
        "artifactCount": len(artifacts),
        "requestedBy": run.requested_by,
        "createdAt": run.created_at.isoformat(),
        "completedAt": run.completed_at.isoformat() if run.completed_at else "",
        "archiveFolder": folder_name,
    }


def write_run_artifacts(
    archive: ZipFile,
    run: ZeroTrustAssessmentRun,
    *,
    folder_name: str,
    used_paths: set[str],
) -> dict[str, object]:
    artifacts = exportable_run_artifacts(run)
    for artifact in artifacts:
        relative_path = safe_zip_relative_path(artifact.relative_path)
        archive_path = unique_zip_path(str(PurePosixPath(folder_name) / relative_path), used_paths)
        archive.writestr(archive_path, bytes(artifact.content))

    manifest = run_manifest(run, artifacts, folder_name)
    manifest_path = unique_zip_path(str(PurePosixPath(folder_name) / "manifest.json"), used_paths)
    archive.writestr(manifest_path, archive_manifest_bytes(manifest))
    return manifest


def create_assessment_run_report_export(run_id: str) -> tuple[str, bytes]:
    run = get_zero_trust_run(run_id)
    folder_name = run_archive_folder(run)
    file_name = f"assessment-report-{safe_filename_component(run.external_id, 'run')}.zip"

    used_paths: set[str] = set()
    output = BytesIO()
    with ZipFile(output, mode="w", compression=ZIP_DEFLATED) as archive:
        write_run_artifacts(archive, run, folder_name=folder_name, used_paths=used_paths)
    return file_name, output.getvalue()


def create_assessment_reports_export(*, profile_id: str = "") -> tuple[str, bytes]:
    runs = exportable_runs(profile_id=profile_id)
    generated_at = timezone.localtime(timezone.now())
    file_name = f"assessment-reports-{generated_at.strftime('%Y%m%d-%H%M%S')}.zip"

    used_paths: set[str] = set()
    manifests: list[dict[str, object]] = []
    output = BytesIO()
    with ZipFile(output, mode="w", compression=ZIP_DEFLATED) as archive:
        for index, run in enumerate(runs, start=1):
            folder_name = run_archive_folder(run, index=index)
            manifests.append(write_run_artifacts(archive, run, folder_name=folder_name, used_paths=used_paths))
        archive.writestr(
            unique_zip_path("manifest.json", used_paths),
            archive_manifest_bytes(
                {
                    "generatedAt": generated_at.isoformat(),
                    "reportCount": len(manifests),
                    "reports": manifests,
                }
            ),
        )

    return file_name, output.getvalue()
