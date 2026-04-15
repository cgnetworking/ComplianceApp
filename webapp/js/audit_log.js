  function auditLogEntries() {
    const reviewState = state.reviewState && typeof state.reviewState === "object" ? state.reviewState : {};
    const entries = Array.isArray(reviewState.auditLog) ? reviewState.auditLog : [];

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

  function auditActionLabel(entry) {
    return String(entry.action || "state_changed")
      .split("_")
      .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
      .join(" ");
  }

  function auditRecordLabel(entry) {
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

  function auditMatches(entry, query) {
    if (!query) {
      return true;
    }
    const haystack = [
      entry.id,
      entry.action,
      entry.entityType,
      entry.entityId,
      entry.summary,
      entry.occurredAt,
      auditActorLabel(entry),
      JSON.stringify(entry.metadata || {}),
    ].join(" ").toLowerCase();
    return haystack.includes(query);
  }

  function renderAuditLogPage() {
    const summaryElement = document.getElementById("audit-log-summary");
    const listElement = document.getElementById("audit-log-list");
    if (!listElement) {
      return;
    }

    const entries = auditLogEntries();
    const query = String(state.search || "").trim().toLowerCase();
    const filteredEntries = entries.filter((entry) => auditMatches(entry, query));

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
                <div class="mini-copy">${escapeHtml(auditRecordLabel(entry))}</div>
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
