from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from zipfile import ZipFile

BASE_DIR = Path(__file__).resolve().parent
ISMS_DIR = BASE_DIR / "ISO27001-2022-ISMS"
WEBAPP_DIR = BASE_DIR / "webapp"
DATA_FILE = WEBAPP_DIR / "data.js"

XML_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
DOC_ID_RE = re.compile(r"\b([A-Z]{2,4}-\d{2})\b")
MONTHS = [
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
]
MONTH_INDEX = {month: index for index, month in enumerate(MONTHS)}


def column_number(label: str) -> int:
    total = 0
    for char in label:
        total = total * 26 + (ord(char) - 64)
    return total


def cell_value(cell: ET.Element, shared_strings: list[str]) -> str:
    cell_type = cell.attrib.get("t")
    if cell_type == "inlineStr":
        text_node = cell.find(f"{XML_NS}is/{XML_NS}t")
        return text_node.text if text_node is not None and text_node.text else ""
    value_node = cell.find(f"{XML_NS}v")
    if value_node is None or value_node.text is None:
        return ""
    if cell_type == "s":
        return shared_strings[int(value_node.text)]
    if cell_type == "b":
        return "TRUE" if value_node.text == "1" else "FALSE"
    return value_node.text


def read_sheet_rows(zip_file: ZipFile, target: str) -> list[list[str]]:
    shared_strings: list[str] = []
    if "xl/sharedStrings.xml" in zip_file.namelist():
        shared_root = ET.fromstring(zip_file.read("xl/sharedStrings.xml"))
        for item in shared_root.findall(f"{XML_NS}si"):
            text = "".join(node.text or "" for node in item.iter(f"{XML_NS}t"))
            shared_strings.append(text)

    worksheet = ET.fromstring(zip_file.read(target))
    sheet_data = worksheet.find(f"{XML_NS}sheetData")
    if sheet_data is None:
        return []

    rows: list[list[str]] = []
    for row in sheet_data.findall(f"{XML_NS}row"):
        values: dict[int, str] = {}
        highest_column = 0
        for cell in row.findall(f"{XML_NS}c"):
            reference = cell.attrib.get("r", "A1")
            column_label = "".join(char for char in reference if char.isalpha())
            column = column_number(column_label)
            highest_column = max(highest_column, column)
            values[column] = cell_value(cell, shared_strings).strip()
        rows.append([values.get(index, "") for index in range(1, highest_column + 1)])
    return rows


def read_workbook(path: Path) -> dict[str, list[list[str]]]:
    with ZipFile(path) as zip_file:
        workbook = ET.fromstring(zip_file.read("xl/workbook.xml"))
        relationships = ET.fromstring(zip_file.read("xl/_rels/workbook.xml.rels"))
        rel_map = {
            rel.attrib["Id"]: rel.attrib["Target"]
            for rel in relationships
        }
        sheets: dict[str, list[list[str]]] = {}
        for sheet in workbook.findall(f"{XML_NS}sheets/{XML_NS}sheet"):
            rel_id = sheet.attrib["{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"]
            target = "xl/" + rel_map[rel_id].lstrip("/")
            sheets[sheet.attrib["name"]] = read_sheet_rows(zip_file, target)
        return sheets


def rows_to_dicts(rows: list[list[str]]) -> list[dict[str, str]]:
    if not rows:
        return []
    headers = rows[0]
    output: list[dict[str, str]] = []
    for row in rows[1:]:
        if not any(cell.strip() for cell in row):
            continue
        padded = row + [""] * (len(headers) - len(row))
        output.append({headers[index]: padded[index].strip() for index in range(len(headers))})
    return output


def inline_markup(text: str) -> str:
    rendered = escape(text)
    rendered = re.sub(r"`([^`]+)`", r"<code>\1</code>", rendered)
    rendered = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", rendered)
    rendered = re.sub(r"\*([^*]+)\*", r"<em>\1</em>", rendered)
    return rendered


def table_cells(line: str) -> list[str]:
    raw = line.strip().strip("|")
    return [cell.strip() for cell in raw.split("|")]


def is_table_separator(line: str) -> bool:
    stripped = line.strip()
    if not stripped.startswith("|"):
        return False
    cells = table_cells(stripped)
    return bool(cells) and all(cell and set(cell) <= {"-", ":"} for cell in cells)


def markdown_to_html(markdown: str) -> str:
    lines = markdown.splitlines()
    blocks: list[str] = []
    index = 0

    while index < len(lines):
        line = lines[index].rstrip()
        stripped = line.strip()

        if not stripped:
            index += 1
            continue

        if stripped.startswith("|") and index + 1 < len(lines) and is_table_separator(lines[index + 1]):
            header = table_cells(lines[index])
            index += 2
            body: list[list[str]] = []
            while index < len(lines) and lines[index].strip().startswith("|"):
                body.append(table_cells(lines[index]))
                index += 1
            header_html = "".join(f"<th>{inline_markup(cell)}</th>" for cell in header)
            body_html = []
            for row in body:
                row_html = "".join(f"<td>{inline_markup(cell)}</td>" for cell in row)
                body_html.append(f"<tr>{row_html}</tr>")
            blocks.append(
                "<table><thead><tr>"
                + header_html
                + "</tr></thead><tbody>"
                + "".join(body_html)
                + "</tbody></table>"
            )
            continue

        if stripped.startswith("- "):
            items: list[str] = []
            while index < len(lines) and lines[index].strip().startswith("- "):
                items.append(lines[index].strip()[2:])
                index += 1
            blocks.append(
                "<ul>" + "".join(f"<li>{inline_markup(item)}</li>" for item in items) + "</ul>"
            )
            continue

        if stripped.startswith("#"):
            level = len(stripped) - len(stripped.lstrip("#"))
            content = stripped[level:].strip()
            level = min(level, 6)
            blocks.append(f"<h{level}>{inline_markup(content)}</h{level}>")
            index += 1
            continue

        paragraph_lines = [stripped]
        index += 1
        while index < len(lines):
            candidate = lines[index].strip()
            if not candidate:
                index += 1
                break
            if candidate.startswith("#") or candidate.startswith("- "):
                break
            if candidate.startswith("|") and index + 1 < len(lines) and is_table_separator(lines[index + 1]):
                break
            paragraph_lines.append(candidate)
            index += 1
        blocks.append(f"<p>{inline_markup(' '.join(paragraph_lines))}</p>")

    return "\n".join(blocks)


def extract_purpose(markdown: str) -> str:
    match = re.search(r"^## 1\. Purpose\s+(.*?)\s+## ", markdown, re.MULTILINE | re.DOTALL)
    if match:
        return " ".join(line.strip() for line in match.group(1).splitlines() if line.strip())
    return ""


def normalize_documents(raw_documents: str) -> list[str]:
    return DOC_ID_RE.findall(raw_documents)


def build_payload() -> dict[str, object]:
    control_workbook = read_workbook(ISMS_DIR / "ISO27001_2022_Control_Mapping.xlsx")
    schedule_workbook = read_workbook(ISMS_DIR / "ISO27001_2022_Review_Schedule.xlsx")

    control_rows = rows_to_dicts(control_workbook["Control Mapping"])
    document_rows = rows_to_dicts(control_workbook["Document Register"])
    schedule_rows = rows_to_dicts(schedule_workbook["Annual Schedule"])
    checklist_rows = rows_to_dicts(schedule_workbook["Review Checklist"])

    documents: list[dict[str, object]] = []
    documents_by_id: dict[str, dict[str, object]] = {}

    for row in document_rows:
        relative_path = row["Path"]
        absolute_path = ISMS_DIR / relative_path
        markdown = absolute_path.read_text(encoding="utf-8")
        document = {
            "id": row["Document ID"],
            "title": row["Title"],
            "type": row["Type"],
            "owner": row["Owner"],
            "approver": row["Approver"],
            "reviewFrequency": row["Review Frequency"],
            "path": relative_path.replace("\\", "/"),
            "folder": relative_path.split("/")[0],
            "purpose": extract_purpose(markdown),
            "contentHtml": markdown_to_html(markdown),
        }
        documents.append(document)
        documents_by_id[row["Document ID"]] = document

    controls: list[dict[str, object]] = []
    for row in control_rows:
        document_ids = normalize_documents(row["Primary Documents"])
        available_document_ids = [doc_id for doc_id in document_ids if doc_id in documents_by_id]
        policy_document_ids = [
            doc_id
            for doc_id in available_document_ids
            if documents_by_id[doc_id]["type"] == "Policy"
        ]
        preferred_document_id = policy_document_ids[0] if policy_document_ids else (
            available_document_ids[0] if available_document_ids else None
        )
        controls.append(
            {
                "id": row["Control ID"],
                "name": row["Control Name"],
                "domain": row["Domain"],
                "applicability": row["Applicability"],
                "implementationModel": row["Implementation Model"],
                "owner": row["Owner"],
                "reviewFrequency": row["Review Frequency"],
                "rationale": row["Rationale"],
                "evidence": row["Evidence"],
                "documentIds": available_document_ids,
                "policyDocumentIds": policy_document_ids,
                "preferredDocumentId": preferred_document_id,
            }
        )

    activities: list[dict[str, object]] = []
    for index, row in enumerate(schedule_rows, start=1):
        month = row["Month"]
        activities.append(
            {
                "id": f"activity-{index:02d}",
                "month": month,
                "monthIndex": MONTH_INDEX[month],
                "frequency": row["Frequency"],
                "activity": row["Activity"],
                "owner": row["Owner"],
                "evidence": row["Evidence"],
            }
        )

    checklist: list[dict[str, object]] = []
    for index, row in enumerate(checklist_rows, start=1):
        checklist.append(
            {
                "id": f"checklist-{index:02d}",
                "category": row["Category"],
                "item": row["Review Item"],
                "frequency": row["Frequency"],
                "owner": row["Owner"],
            }
        )

    frequency_counts = Counter(document["reviewFrequency"] for document in documents)
    domain_counts = Counter(control["domain"] for control in controls)
    mapped_policy_counts = Counter()
    for control in controls:
        for document_id in control["policyDocumentIds"]:
            mapped_policy_counts[document_id] += 1

    policy_coverage = []
    for document in documents:
        if document["type"] != "Policy":
            continue
        policy_coverage.append(
            {
                "id": document["id"],
                "title": document["title"],
                "controlCount": mapped_policy_counts[document["id"]],
                "reviewFrequency": document["reviewFrequency"],
            }
        )

    checklist_by_frequency = defaultdict(int)
    for item in checklist:
        checklist_by_frequency[item["frequency"]] += 1

    return {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "sourceSnapshot": {
            "controlRegister": "ISO27001_2022_Control_Mapping.xlsx",
            "reviewSchedule": "ISO27001_2022_Review_Schedule.xlsx",
            "runtimeDependency": False,
        },
        "summary": {
            "controlCount": len(controls),
            "documentCount": len(documents),
            "policyCount": sum(1 for document in documents if document["type"] == "Policy"),
            "activityCount": len(activities),
            "checklistCount": len(checklist),
            "domainCounts": dict(domain_counts),
            "documentReviewFrequencies": dict(frequency_counts),
            "checklistFrequencies": dict(checklist_by_frequency),
        },
        "controls": controls,
        "documents": documents,
        "activities": activities,
        "checklist": checklist,
        "policyCoverage": sorted(policy_coverage, key=lambda item: (-item["controlCount"], item["id"])),
    }


def main() -> None:
    WEBAPP_DIR.mkdir(parents=True, exist_ok=True)
    payload = build_payload()
    DATA_FILE.write_text(
        "window.ISMS_DATA = " + json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + ";\n",
        encoding="utf-8",
    )
    print(f"Wrote {DATA_FILE}")


if __name__ == "__main__":
    main()
