  function normalizeAuditLogEntries(entries) {
    return entries
      .filter((entry) => entry && typeof entry === "object")
      .map((entry) => ({
        id: typeof entry.id === "string" ? entry.id : "",
        action: typeof entry.action === "string" && entry.action.trim() ? entry.action.trim() : "state_changed",
        entityType: typeof entry.entityType === "string" && entry.entityType.trim() ? entry.entityType.trim() : "record",
        entityId: typeof entry.entityId === "string" ? entry.entityId.trim() : "",
        summary: typeof entry.summary === "string" && entry.summary.trim() ? entry.summary.trim() : "State updated.",
        occurredAt: typeof entry.occurredAt === "string" ? entry.occurredAt : "",
        actor: entry.actor && typeof entry.actor === "object" ? entry.actor : {},
        metadata: entry.metadata && typeof entry.metadata === "object" ? entry.metadata : {},
      }))
      .sort((left, right) => {
        const leftTime = Date.parse(left.occurredAt) || 0;
        const rightTime = Date.parse(right.occurredAt) || 0;
        return rightTime - leftTime;
      });
  }

  function auditLogEntries() {
    const reviewState = state.reviewState && typeof state.reviewState === "object" ? state.reviewState : {};
    const entries = Array.isArray(reviewState.auditLog) ? reviewState.auditLog : [];
    return normalizeAuditLogEntries(entries);
  }

  function auditActionLabel(entry) {
    return String(entry.action || "state_changed")
      .split("_")
      .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
      .join(" ");
  }

  function auditChecklistLookup() {
    const checklistItems = typeof getAllChecklistItems === "function"
      ? getAllChecklistItems()
      : (Array.isArray(state.checklistItems) ? state.checklistItems : []);
    const checklistById = new Map();
    checklistItems.forEach((item) => {
      if (!item || typeof item !== "object") {
        return;
      }
      const itemId = typeof item.id === "string" ? item.id.trim() : "";
      if (!itemId || checklistById.has(itemId)) {
        return;
      }
      checklistById.set(itemId, item);
    });
    return checklistById;
  }

  function auditChecklistId(entry) {
    const entityId = typeof entry.entityId === "string" ? entry.entityId.trim() : "";
    if (!entityId) {
      return "";
    }
    const scopedSeparator = entityId.indexOf("::");
    if (scopedSeparator === -1) {
      return entityId;
    }
    return entityId.slice(scopedSeparator + 2).trim();
  }

  function auditChecklistCreatedMonth(checklistItem) {
    const checklistCreatedAt = checklistItem && typeof checklistItem.createdAt === "string"
      ? checklistItem.createdAt.trim()
      : "";
    if (!checklistCreatedAt) {
      return "";
    }
    const parsed = typeof parseDisplayDateValue === "function"
      ? parseDisplayDateValue(checklistCreatedAt)
      : new Date(checklistCreatedAt);
    if (!parsed || Number.isNaN(parsed.getTime())) {
      return "";
    }
    return new Intl.DateTimeFormat(undefined, { month: "long", year: "numeric" }).format(parsed);
  }

  function auditRecordLabel(entry, checklistById = null) {
    const checklistId = auditChecklistId(entry);
    if (checklistId && checklistId.startsWith("checklist-")) {
      const checklistItem = checklistById instanceof Map ? checklistById.get(checklistId) : null;
      if (!checklistItem || typeof checklistItem.item !== "string") {
        return "";
      }
      const checklistName = checklistItem.item.trim();
      const createdMonth = auditChecklistCreatedMonth(checklistItem);
      return `${checklistName} / Created ${createdMonth}`;
    }
    const entityType = String(entry.entityType || "record").replaceAll("_", " ");
    const normalizedEntityType = entityType.charAt(0).toUpperCase() + entityType.slice(1);
    if (entry.entityId) {
      return `${normalizedEntityType} / ${entry.entityId}`;
    }
    return normalizedEntityType;
  }

  function auditActorLabel(entry) {
    const actor = entry.actor && typeof entry.actor === "object" ? entry.actor : {};
    const displayName = typeof actor.displayName === "string" ? actor.displayName.trim() : "";
    const username = typeof actor.username === "string" ? actor.username.trim() : "";
    return displayName || username || "Unknown user";
  }

  function auditMatches(entry, query, checklistById = null) {
    if (!query) {
      return true;
    }
    const haystack = [
      entry.id,
      entry.action,
      entry.entityType,
      entry.entityId,
      auditRecordLabel(entry, checklistById),
      entry.summary,
      entry.occurredAt,
      auditActorLabel(entry),
      JSON.stringify(entry.metadata || {}),
    ].join(" ").toLowerCase();
    return haystack.includes(query);
  }

  function setAuditExportStatus(message, tone) {
    const statusElement = document.getElementById("audit-log-export-status");
    if (!statusElement) {
      return;
    }
    if (typeof setUploadStatus === "function") {
      setUploadStatus(statusElement, message, tone || "");
      return;
    }
    statusElement.textContent = message;
  }

  function auditMetadataCsvValue(metadata) {
    if (!metadata || typeof metadata !== "object") {
      return "{}";
    }
    try {
      return JSON.stringify(metadata);
    } catch (error) {
      return "{}";
    }
  }

  function auditCsvEscape(value) {
    const normalizedValue = value === null || value === undefined ? "" : String(value);
    if (!/[",\r\n]/.test(normalizedValue)) {
      return normalizedValue;
    }
    return `"${normalizedValue.replaceAll('"', '""')}"`;
  }

  function buildAuditLogCsv(entries, checklistById = null) {
    const headers = [
      "id",
      "action",
      "action_label",
      "entity_type",
      "entity_id",
      "record",
      "summary",
      "actor_display_name",
      "actor_username",
      "occurred_at",
      "occurred_at_display",
      "metadata_json",
    ];
    const rows = entries.map((entry) => {
      const actor = entry.actor && typeof entry.actor === "object" ? entry.actor : {};
      const actorUsername = typeof actor.username === "string" ? actor.username.trim() : "";
      return [
        entry.id,
        entry.action,
        auditActionLabel(entry),
        entry.entityType,
        entry.entityId,
        auditRecordLabel(entry, checklistById),
        entry.summary,
        auditActorLabel(entry),
        actorUsername,
        entry.occurredAt,
        formatDateTime(entry.occurredAt),
        auditMetadataCsvValue(entry.metadata),
      ];
    });

    return [headers]
      .concat(rows)
      .map((row) => row.map((value) => auditCsvEscape(value)).join(","))
      .join("\r\n");
  }

  function auditExportFileName(now = new Date()) {
    const parsed = now instanceof Date && !Number.isNaN(now.getTime()) ? now : new Date();
    const year = String(parsed.getFullYear()).padStart(4, "0");
    const month = String(parsed.getMonth() + 1).padStart(2, "0");
    const day = String(parsed.getDate()).padStart(2, "0");
    const hour = String(parsed.getHours()).padStart(2, "0");
    const minute = String(parsed.getMinutes()).padStart(2, "0");
    const second = String(parsed.getSeconds()).padStart(2, "0");
    return `audit_log_export_${year}${month}${day}_${hour}${minute}${second}.csv`;
  }

  function triggerAuditLogCsvDownload(csvText, fileName) {
    const blob = new Blob([csvText], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = fileName;
    document.body.append(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  }
  function parseAuditExportFilename(dispositionHeader, fallbackName) {
    if (typeof dispositionHeader !== "string" || !dispositionHeader.trim()) {
      return fallbackName;
    }
    const utf8Match = dispositionHeader.match(/filename\*=UTF-8''([^;]+)/i);
    if (utf8Match && utf8Match[1]) {
      try {
        return decodeURIComponent(utf8Match[1]);
      } catch (error) {
        // Ignore malformed filenames and use fallback handling below.
      }
    }
    const plainMatch = dispositionHeader.match(/filename=\"?([^\";]+)\"?/i);
    if (plainMatch && plainMatch[1]) {
      return plainMatch[1];
    }
    return fallbackName;
  }

  async function loadAuditEntriesForExport() {
    try {
      const payload = await apiRequest("/state/?page=audit-log");
      const reviewState = payload && typeof payload.reviewState === "object" ? payload.reviewState : {};
      const auditLog = Array.isArray(reviewState.auditLog) ? reviewState.auditLog : [];
      return normalizeAuditLogEntries(auditLog);
    } catch (error) {
      return auditLogEntries();
    }
  }

  function bindAuditLogExportTrigger() {
    const exportTrigger = document.getElementById("audit-log-export-trigger");
    if (!exportTrigger || exportTrigger.dataset.auditExportBound === "true") {
      return;
    }

    exportTrigger.dataset.auditExportBound = "true";
    exportTrigger.addEventListener("click", async () => {
      const originalLabel = exportTrigger.textContent;
      exportTrigger.disabled = true;
      exportTrigger.textContent = "Exporting...";
      setAuditExportStatus("Building CSV export from the review state audit log...", "info");

      try {
        const response = await fetch(`${resolveApiBaseUrl()}/audit-log/export.csv`, {
          method: "GET",
          headers: { Accept: "text/csv" },
          credentials: "same-origin",
        });
        if (!response.ok) {
          let detail = `Unable to export the audit log (${response.status}).`;
          try {
            const errorPayload = await response.json();
            if (errorPayload && typeof errorPayload.detail === "string" && errorPayload.detail.trim()) {
              detail = errorPayload.detail;
            }
          } catch (error) {
            // Ignore non-JSON errors and keep fallback detail.
          }
          throw new Error(detail);
        }

        const csvBlob = await response.blob();
        const fileName = parseAuditExportFilename(
          response.headers.get("Content-Disposition"),
          auditExportFileName(),
        );
        const downloadUrl = URL.createObjectURL(csvBlob);
        const link = document.createElement("a");
        link.href = downloadUrl;
        link.download = fileName;
        document.body.append(link);
        link.click();
        link.remove();
        URL.revokeObjectURL(downloadUrl);
        setAuditExportStatus("Audit log CSV exported.", "success");
      } catch (error) {
        const detail = error instanceof Error ? error.message : "Unable to export the audit log.";
        setAuditExportStatus(detail, "error");
      } finally {
        exportTrigger.disabled = false;
        exportTrigger.textContent = originalLabel;
      }
    });
  }

  function renderAuditLogPage() {
    const summaryElement = document.getElementById("audit-log-summary");
    const listElement = document.getElementById("audit-log-list");
    bindAuditLogExportTrigger();
    if (!listElement) {
      return;
    }

    const entries = auditLogEntries();
    const checklistById = auditChecklistLookup();
    const query = String(state.search || "").trim().toLowerCase();
    const filteredEntries = entries.filter((entry) => auditMatches(entry, query, checklistById));

    if (summaryElement) {
      const latestEntry = filteredEntries[0] || entries[0] || null;
      const summaryParts = [
        `<span class="chip">${filteredEntries.length}/${entries.length} visible</span>`,
      ];
      if (latestEntry && latestEntry.occurredAt) {
        summaryParts.push(`<span class="chip">Latest / ${escapeHtml(formatDateTime(latestEntry.occurredAt))}</span>`);
      }
      summaryElement.innerHTML = summaryParts.join("");
    }

    if (!entries.length) {
      listElement.innerHTML = '<div class="empty-state">No audit entries have been recorded yet.</div>';
      return;
    }

    if (!filteredEntries.length) {
      listElement.innerHTML = '<div class="empty-state">No audit entries match the current search.</div>';
      return;
    }

    listElement.innerHTML = `
      <div class="activity-list">
        ${filteredEntries.map((entry) => `
          <article class="activity-card">
            <div class="activity-top">
              <div>
                <strong>${escapeHtml(auditActionLabel(entry))}</strong>
                <div class="mini-copy">${escapeHtml(auditRecordLabel(entry, checklistById))}</div>
              </div>
              <span class="status-pill is-active">${escapeHtml(formatDateTime(entry.occurredAt))}</span>
            </div>
            <p class="activity-evidence">User: ${escapeHtml(auditActorLabel(entry))}</p>
            <p class="activity-evidence">Details: ${escapeHtml(entry.summary)}</p>
          </article>
        `).join("")}
      </div>
    `;
  }
