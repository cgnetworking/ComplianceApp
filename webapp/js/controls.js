  function renderControlsPage() {
    const controls = filteredControls();
    renderControlsTable(controls);
    renderControlDetail();
  }
  function renderControlsTable(controls) {
    if (!els.controlsBody) {
      return;
    }
    if (!controls.length) {
      els.controlsBody.innerHTML = `
        <tr>
          <td colspan="5"><div class="empty-state">No controls match the current filters.</div></td>
        </tr>
      `;
      return;
    }

    els.controlsBody.innerHTML = controls.map((control) => {
      return `
      <tr class="${control.id === state.selectedControlId ? "is-selected" : ""}" data-control-row="${escapeHtml(control.id)}">
        <td><a class="control-link" data-policy-link="true" href="${policyUrl(control.id, control.preferredDocumentId)}">${escapeHtml(control.id)}</a></td>
        <td>${escapeHtml(control.name)}</td>
        <td>${escapeHtml(control.domain)}</td>
        <td>${escapeHtml(control.effectiveImplementationModel)}</td>
        <td>${escapeHtml(control.reviewFrequency)}</td>
      </tr>
    `;
    }).join("");
  }
  function renderControlDetail() {
    if (!els.controlDetail) {
      return;
    }
    const control = getControlView(state.selectedControlId);
    if (!control) {
      els.controlDetail.innerHTML = '<div class="empty-state">Select a control row to inspect its mapping and linked policies.</div>';
      return;
    }

    const mappedDocuments = control.documentIds.map((documentId) => {
      const documentItem = documentsById.get(documentId);
      if (!documentItem) {
        return "";
      }
      return `
        <a class="doc-button ${documentId === control.preferredDocumentId ? "is-active" : ""}" href="${policyUrl(control.id, documentId)}">
          ${escapeHtml(documentItem.id)} / ${escapeHtml(documentItem.title)}
          <small>${escapeHtml(documentItem.type)} / ${escapeHtml(documentItem.reviewFrequency)}</small>
        </a>
      `;
    }).join("");

    els.controlDetail.innerHTML = `
      <div class="detail-header">
        <div>
          <p class="panel-kicker">Selected control</p>
          <h3>${escapeHtml(control.id)} / ${escapeHtml(control.name)}</h3>
        </div>
        <div class="chip-row">
          <span class="chip">${escapeHtml(control.domain)}</span>
          <span class="chip">${escapeHtml(control.effectiveApplicability)}</span>
          <span class="chip">${escapeHtml(control.effectiveImplementationModel)}</span>
          <span class="status-pill ${control.policyDocumentIds.length ? "is-active" : ""}">${control.policyDocumentIds.length} mapped policies</span>
        </div>
      </div>

      <div class="detail-grid">
        <article class="detail-card">
          <strong>Rationale</strong>
          <div class="mini-copy">${escapeHtml(control.rationale)}</div>
        </article>
        <article class="detail-card">
          <strong>Evidence</strong>
          <div class="mini-copy">${escapeHtml(control.evidence)}</div>
        </article>
        <article class="detail-card">
          <strong>Owner</strong>
          <div class="mini-copy">${escapeHtml(control.owner)}</div>
        </article>
        <article class="detail-card">
          <strong>Review frequency</strong>
          <div class="mini-copy">${escapeHtml(control.reviewFrequency)}</div>
        </article>
      </div>

      <div class="doc-section">
        <strong>Open mapped policy page</strong>
        <div class="doc-list">
          ${mappedDocuments || '<div class="empty-state">No embedded documents are mapped to this control.</div>'}
        </div>
      </div>

      <div class="doc-section">
        <div class="detail-card exclusion-card">
          <strong>Exclusion status</strong>
          <label class="toggle-row ${control.isBaseExcluded ? "is-disabled" : ""}">
            <input
              type="checkbox"
              data-control-excluded="${escapeHtml(control.id)}"
              ${control.isExcluded ? "checked" : ""}
              ${control.isBaseExcluded ? "disabled" : ""}
            >
            <span>${control.isBaseExcluded ? "Excluded in source snapshot" : "Mark control as excluded"}</span>
          </label>
          <p class="mini-copy">
            ${escapeHtml(control.isBaseExcluded ? "This control is already excluded in the embedded source data." : "Locally excluded controls display as Excluded in this portal and retain an exclusion rationale in browser storage.")}
          </p>
          ${control.isExcluded ? `
            <div class="text-area-field">
              <label for="exclusion-reason-${escapeHtml(control.id)}">Exclusion Reason</label>
              <textarea
                id="exclusion-reason-${escapeHtml(control.id)}"
                data-exclusion-reason="${escapeHtml(control.id)}"
                placeholder="Document why this control is excluded."
                ${control.isBaseExcluded ? "readonly" : ""}
              >${escapeHtml(control.exclusionReason)}</textarea>
              ${!control.isBaseExcluded && !control.exclusionReason.trim() ? '<p class="helper-note is-warning">Add an exclusion reason for this locally excluded control.</p>' : ""}
            </div>
          ` : ""}
        </div>
      </div>
    `;
  }
  function getAllControlViews() {
    return data.controls.map((control) => getControlView(control)).filter(Boolean);
  }
  function getControlView(controlOrId) {
    const control = typeof controlOrId === "string" ? controlsById.get(controlOrId) : controlOrId;
    if (!control) {
      return null;
    }
    const stored = state.controlState[control.id] || {};
    const storedApplicability = typeof stored.applicability === "string" && stored.applicability.trim()
      ? stored.applicability.trim()
      : control.applicability;
    const baseExcluded = isBaseExcluded(control);
    const applicabilityExcluded = storedApplicability === "Excluded";
    const localExcluded = Boolean(stored.excluded) && !baseExcluded && !applicabilityExcluded;
    const effectiveExcluded = baseExcluded || applicabilityExcluded || localExcluded;
    return {
      ...control,
      isBaseExcluded: baseExcluded,
      isLocallyExcluded: localExcluded,
      isExcluded: effectiveExcluded,
      effectiveApplicability: effectiveExcluded ? "Excluded" : storedApplicability,
      effectiveImplementationModel: effectiveExcluded ? "Excluded" : control.implementationModel,
      exclusionReason: (localExcluded || applicabilityExcluded)
        ? (stored.reason || "")
        : (baseExcluded ? control.rationale : ""),
    };
  }
  function isBaseExcluded(control) {
    return control.implementationModel === "Excluded" || control.applicability === "Excluded";
  }
  function setControlExclusion(controlId, excluded) {
    const control = controlsById.get(controlId);
    if (!control || isBaseExcluded(control)) {
      return;
    }

    const existing = state.controlState[controlId] || {};
    if (excluded) {
      state.controlState[controlId] = {
        ...existing,
        excluded: true,
        reason: existing.reason || "",
      };
    } else {
      const nextState = {
        ...existing,
        excluded: false,
      };
      if (!nextState.reason && !nextState.applicability) {
        delete state.controlState[controlId];
      } else {
        state.controlState[controlId] = nextState;
      }
    }
    saveControlState();
  }
  function updateControlReason(controlId, reason) {
    const control = controlsById.get(controlId);
    if (!control || isBaseExcluded(control)) {
      return;
    }
    const existing = state.controlState[controlId] || { excluded: true, reason: "" };
    const nextState = {
      ...existing,
      excluded: existing.excluded !== false,
      reason,
    };
    if (!nextState.excluded && !nextState.reason && !nextState.applicability) {
      delete state.controlState[controlId];
    } else {
      state.controlState[controlId] = nextState;
    }
    saveControlState();
  }
  function filteredControls() {
    const searchLower = state.search.trim().toLowerCase();

    return getAllControlViews().filter((view) => {
      if (page !== "policies" && state.domain !== "All" && view.domain !== state.domain) {
        return false;
      }
      if (page !== "policies" && state.applicability !== "All" && view.effectiveApplicability !== state.applicability) {
        return false;
      }
      if (page !== "policies" && state.frequency !== "All" && view.reviewFrequency !== state.frequency) {
        return false;
      }
      if (!searchLower || (page !== "controls" && page !== "reports")) {
        return true;
      }

      const searchableText = [
        view.id,
        view.name,
        view.domain,
        view.rationale,
        view.evidence,
        view.effectiveImplementationModel,
        view.effectiveApplicability,
        view.exclusionReason,
        ...view.documentIds.map((documentId) => {
          const documentItem = documentsById.get(documentId);
          return documentItem ? `${documentItem.id} ${documentItem.title}` : documentId;
        }),
      ].join(" ").toLowerCase();

      return searchableText.includes(searchLower);
    });
  }
  function syncSelectionToVisibleControls() {
    const controls = filteredControls();
    if (!controls.length) {
      state.selectedControlId = null;
      return;
    }
    if (!state.selectedControlId || !controls.some((control) => control.id === state.selectedControlId)) {
      state.selectedControlId = controls[0].id;
    }
  }
  function reviewCadence(reviewFrequency) {
    const value = reviewFrequency.toLowerCase();
    if (value.includes("monthly")) {
      return "Monthly";
    }
    if (value.includes("quarterly")) {
      return "Quarterly";
    }
    if (value.includes("significant change")) {
      return "Change";
    }
    if (value.includes("per event") || value.includes("after incidents")) {
      return "Event";
    }
    return "Annual";
  }
  function buildSmoothPath(points) {
    if (!points.length) {
      return "";
    }
    if (points.length === 1) {
      return `M ${points[0].x} ${points[0].y}`;
    }

    let path = `M ${points[0].x} ${points[0].y}`;
    for (let index = 0; index < points.length - 1; index += 1) {
      const current = points[index];
      const next = points[index + 1];
      const midX = (current.x + next.x) / 2;
      path += ` C ${midX} ${current.y}, ${midX} ${next.y}, ${next.x} ${next.y}`;
    }
    return path;
  }
