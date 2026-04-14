  const DEFAULT_REVIEW_FREQUENCIES = [
    "Annual",
    "Quarterly",
    "Monthly",
    "Per event",
    "After significant change",
  ];

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
          <td colspan="4"><div class="empty-state">No controls match the current filters.</div></td>
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

    const applicabilityOptions = renderSelectOptions(
      ["", "Applicable", "Excluded"],
      control.effectiveApplicability
    );
    const reviewFrequencyOptions = renderSelectOptions(
      buildReviewFrequencyOptions(control.effectiveReviewFrequency),
      control.effectiveReviewFrequency
    );

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
          <label class="form-field">
            <select data-control-review-frequency="${escapeHtml(control.id)}">
              ${reviewFrequencyOptions}
            </select>
          </label>
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
          <strong>Applicability</strong>
          <label class="form-field">
            <select
              data-control-applicability="${escapeHtml(control.id)}"
              ${control.isBaseExcluded ? "disabled" : ""}
            >
              ${applicabilityOptions}
            </select>
          </label>
          ${control.isBaseExcluded ? '<p class="mini-copy">This control is already excluded in the current mapping data.</p>' : ""}
          ${control.effectiveApplicability === "Excluded" ? `
            <div class="text-area-field">
              <label for="exclusion-reason-${escapeHtml(control.id)}">Exclusion Reason</label>
              <textarea
                id="exclusion-reason-${escapeHtml(control.id)}"
                data-exclusion-reason="${escapeHtml(control.id)}"
                placeholder="Document why this control is excluded."
                ${control.isBaseExcluded ? "readonly" : ""}
              >${escapeHtml(control.exclusionReason)}</textarea>
              ${!control.isBaseExcluded && !control.exclusionReason.trim() ? '<p class="helper-note is-warning">Add an exclusion reason for this excluded control.</p>' : ""}
            </div>
          ` : ""}
        </div>
      </div>
    `;
  }
  function renderSelectOptions(values, selectedValue) {
    return values.map((value) => {
      const selected = value === selectedValue ? " selected" : "";
      return `<option value="${escapeHtml(value)}"${selected}>${escapeHtml(value)}</option>`;
    }).join("");
  }
  function buildReviewFrequencyOptions(selectedValue) {
    const options = [""].concat(DEFAULT_REVIEW_FREQUENCIES);
    if (selectedValue && !options.includes(selectedValue)) {
      options.push(selectedValue);
    }
    return options;
  }
  function normalizeControlApplicability(value) {
    const normalized = typeof value === "string" ? value.trim() : "";
    return normalized === "Applicable" || normalized === "Excluded" ? normalized : "";
  }
  function normalizeControlReviewFrequency(value) {
    return typeof value === "string" ? value.trim() : "";
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
    const storedApplicability = normalizeControlApplicability(stored.applicability);
    const baseApplicability = normalizeControlApplicability(control.applicability);
    const storedReviewFrequency = normalizeControlReviewFrequency(stored.reviewFrequency);
    const baseReviewFrequency = normalizeControlReviewFrequency(control.reviewFrequency);
    const baseExcluded = isBaseExcluded(control);
    const legacyLocalExcluded = Boolean(stored.excluded) && !baseExcluded && storedApplicability !== "Applicable";
    const effectiveApplicability = (baseExcluded || storedApplicability === "Excluded" || legacyLocalExcluded)
      ? "Excluded"
      : (storedApplicability || baseApplicability);
    const effectiveExcluded = effectiveApplicability === "Excluded";
    const effectiveReviewFrequency = storedReviewFrequency || baseReviewFrequency;
    const exclusionReason = effectiveExcluded
      ? (typeof stored.reason === "string" ? stored.reason : "") || (baseExcluded ? control.rationale : "")
      : "";

    return {
      ...control,
      applicability: effectiveApplicability,
      reviewFrequency: effectiveReviewFrequency,
      isBaseExcluded: baseExcluded,
      isLocallyExcluded: legacyLocalExcluded,
      isExcluded: effectiveExcluded,
      effectiveApplicability: effectiveApplicability,
      effectiveReviewFrequency: effectiveReviewFrequency,
      effectiveImplementationModel: effectiveExcluded ? "Excluded" : control.implementationModel,
      exclusionReason: exclusionReason,
    };
  }
  function isBaseExcluded(control) {
    return control.implementationModel === "Excluded" || normalizeControlApplicability(control.applicability) === "Excluded";
  }
  function saveControlStateEntry(controlId, nextState) {
    const applicability = normalizeControlApplicability(nextState.applicability);
    const reason = typeof nextState.reason === "string" ? nextState.reason : "";
    const reviewFrequency = normalizeControlReviewFrequency(nextState.reviewFrequency);

    const entry = {};
    if (applicability) {
      entry.applicability = applicability;
    }
    if (reason) {
      entry.reason = reason;
    }
    if (reviewFrequency) {
      entry.reviewFrequency = reviewFrequency;
    }

    if (!Object.keys(entry).length) {
      delete state.controlState[controlId];
    } else {
      state.controlState[controlId] = entry;
    }
    saveControlState();
  }
  function setControlApplicability(controlId, applicability) {
    const control = controlsById.get(controlId);
    if (!control || isBaseExcluded(control)) {
      return;
    }

    const existing = state.controlState[controlId] || {};
    const nextState = {
      ...existing,
      applicability: normalizeControlApplicability(applicability),
    };
    if (nextState.applicability !== "Excluded") {
      nextState.reason = "";
    }
    saveControlStateEntry(controlId, nextState);
  }
  function setControlExclusion(controlId, excluded) {
    setControlApplicability(controlId, excluded ? "Excluded" : "");
  }
  function updateControlReviewFrequency(controlId, reviewFrequency) {
    const control = controlsById.get(controlId);
    if (!control) {
      return;
    }

    const existing = state.controlState[controlId] || {};
    const normalizedFrequency = normalizeControlReviewFrequency(reviewFrequency);
    const baseReviewFrequency = normalizeControlReviewFrequency(control.reviewFrequency);
    const nextState = {
      ...existing,
      reviewFrequency: normalizedFrequency === baseReviewFrequency ? "" : normalizedFrequency,
    };
    saveControlStateEntry(controlId, nextState);
  }
  function updateControlReason(controlId, reason) {
    const control = controlsById.get(controlId);
    if (!control || isBaseExcluded(control)) {
      return;
    }

    const existing = state.controlState[controlId] || {};
    const nextState = {
      ...existing,
      applicability: "Excluded",
      reason,
    };
    saveControlStateEntry(controlId, nextState);
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
      if (page !== "policies" && state.frequency !== "All" && view.effectiveReviewFrequency !== state.frequency) {
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
        view.effectiveReviewFrequency,
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
    const value = String(reviewFrequency || "").toLowerCase();
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
