from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import PurePath
import re
from typing import Iterable
from zipfile import ZIP_DEFLATED, ZipFile

from django.utils import timezone

from ..models import UploadedPolicy
from .common import ValidationError, normalize_string
from .mapping import get_mapping_payload

_POLICY_LIBRARY_ID_PATTERN = re.compile(r"^(POL|GOV|PR|UPL)-\d+$", re.IGNORECASE)
_UNSAFE_FILENAME_CHARS = re.compile(r"[^A-Za-z0-9._-]+")


@dataclass(frozen=True)
class PolicyDownloadArtifact:
    filename: str
    content: bytes
    content_type: str


def _is_policy_library_document(document_id: str, *, is_uploaded: bool) -> bool:
    if is_uploaded:
        return True
    return bool(_POLICY_LIBRARY_ID_PATTERN.fullmatch(document_id))


def _safe_filename(value: object, *, fallback: str, extension: str = "") -> str:
    candidate = normalize_string(value)
    if candidate:
        candidate = PurePath(candidate).name
    if not candidate:
        candidate = fallback

    stem = PurePath(candidate).stem or fallback
    suffix = PurePath(candidate).suffix
    if extension and not suffix:
        suffix = extension

    normalized_stem = _UNSAFE_FILENAME_CHARS.sub("-", stem).strip("-._")
    if not normalized_stem:
        normalized_stem = fallback
    if len(normalized_stem) > 96:
        normalized_stem = normalized_stem[:96].rstrip("-._")

    normalized_suffix = _UNSAFE_FILENAME_CHARS.sub("", suffix).lower() if suffix else ""
    if extension and not normalized_suffix:
        normalized_suffix = extension
    if normalized_suffix and not normalized_suffix.startswith("."):
        normalized_suffix = f".{normalized_suffix}"
    return f"{normalized_stem}{normalized_suffix}"


def _content_type_for_extension(extension: str) -> str:
    normalized = extension.lower().lstrip(".")
    if normalized in {"md", "markdown"}:
        return "text/markdown; charset=utf-8"
    if normalized in {"html", "htm"}:
        return "text/html; charset=utf-8"
    if normalized == "txt":
        return "text/plain; charset=utf-8"
    return "text/plain; charset=utf-8"


def _mapping_policy_payloads() -> list[dict[str, object]]:
    mapping_payload = get_mapping_payload()
    documents = mapping_payload.get("documents")
    if not isinstance(documents, list):
        return []

    policy_documents: list[dict[str, object]] = []
    for item in documents:
        if not isinstance(item, dict):
            continue
        document_id = normalize_string(item.get("id"))
        if not document_id:
            continue
        if not _is_policy_library_document(document_id, is_uploaded=bool(item.get("isUploaded"))):
            continue
        policy_documents.append(item)
    return policy_documents


def _mapping_document_by_id(document_id: str) -> dict[str, object] | None:
    normalized_id = normalize_string(document_id)
    if not normalized_id:
        return None

    for item in _mapping_policy_payloads():
        if normalize_string(item.get("id")) == normalized_id:
            return item
    return None


def _uploaded_document_artifact(policy: UploadedPolicy) -> PolicyDownloadArtifact:
    original_filename = _safe_filename(
        policy.original_filename,
        fallback=policy.document_id.lower(),
    )
    extension = PurePath(original_filename).suffix.lower().lstrip(".")
    content_type = _content_type_for_extension(extension)

    raw_text = policy.raw_text or ""
    if raw_text:
        content = raw_text.encode("utf-8")
    else:
        fallback_html = policy.content_html or "<p>No embedded content is available for this policy document.</p>"
        content = fallback_html.encode("utf-8")
        if not extension:
            original_filename = _safe_filename(
                original_filename,
                fallback=policy.document_id.lower(),
                extension=".html",
            )
            content_type = "text/html; charset=utf-8"
    return PolicyDownloadArtifact(filename=original_filename, content=content, content_type=content_type)


def _mapping_document_artifact(document: dict[str, object]) -> PolicyDownloadArtifact:
    document_id = normalize_string(document.get("id"))
    title = normalize_string(document.get("title"), document_id)
    fallback_name = f"{document_id}-{title}".strip("-").lower() or "policy-document"
    filename = _safe_filename(
        document.get("originalFilename"),
        fallback=fallback_name,
        extension=".html",
    )
    html_content = normalize_string(document.get("contentHtml"))
    if not html_content:
        html_content = "<p>No embedded content is available for this policy document.</p>"
    return PolicyDownloadArtifact(
        filename=filename,
        content=html_content.encode("utf-8"),
        content_type="text/html; charset=utf-8",
    )


def _iter_all_policy_artifacts() -> Iterable[PolicyDownloadArtifact]:
    seen_ids: set[str] = set()
    for uploaded_policy in UploadedPolicy.objects.all():
        document_id = normalize_string(uploaded_policy.document_id)
        if not document_id or document_id in seen_ids:
            continue
        seen_ids.add(document_id)
        yield _uploaded_document_artifact(uploaded_policy)

    for document in _mapping_policy_payloads():
        document_id = normalize_string(document.get("id"))
        if not document_id or document_id in seen_ids:
            continue
        seen_ids.add(document_id)
        yield _mapping_document_artifact(document)


def _deduplicate_entry_name(file_name: str, seen: set[str]) -> str:
    if file_name not in seen:
        seen.add(file_name)
        return file_name

    stem = PurePath(file_name).stem
    suffix = PurePath(file_name).suffix
    counter = 2
    while True:
        candidate = f"{stem}-{counter}{suffix}"
        if candidate not in seen:
            seen.add(candidate)
            return candidate
        counter += 1


def build_policy_document_download(document_id: str) -> PolicyDownloadArtifact:
    normalized_id = normalize_string(document_id)
    if not normalized_id:
        raise ValidationError("Policy id is required.")

    try:
        uploaded_policy = UploadedPolicy.objects.get(document_id=normalized_id)
    except UploadedPolicy.DoesNotExist:
        uploaded_policy = None

    if uploaded_policy is not None:
        return _uploaded_document_artifact(uploaded_policy)

    mapping_document = _mapping_document_by_id(normalized_id)
    if mapping_document is not None:
        return _mapping_document_artifact(mapping_document)

    raise ValidationError("Policy document was not found.")


def build_all_policies_download() -> PolicyDownloadArtifact:
    artifacts = list(_iter_all_policy_artifacts())
    if not artifacts:
        raise ValidationError("No policy documents are available for download.")

    zip_buffer = BytesIO()
    seen_names: set[str] = set()
    with ZipFile(zip_buffer, mode="w", compression=ZIP_DEFLATED) as zip_file:
        for artifact in artifacts:
            entry_name = _deduplicate_entry_name(artifact.filename, seen_names)
            zip_file.writestr(entry_name, artifact.content)

    timestamp = timezone.localtime().strftime("%Y%m%d-%H%M%S")
    archive_name = f"policy-library-{timestamp}.zip"
    return PolicyDownloadArtifact(
        filename=archive_name,
        content=zip_buffer.getvalue(),
        content_type="application/zip",
    )


def build_attachment_content_disposition(file_name: str) -> str:
    safe_name = _safe_filename(file_name, fallback="download")
    return f'attachment; filename="{safe_name}"'


__all__ = [
    "PolicyDownloadArtifact",
    "build_policy_document_download",
    "build_all_policies_download",
    "build_attachment_content_disposition",
    "ValidationError",
]
