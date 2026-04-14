  function renderRisksPage() {
    const risks = filteredRisks();
    syncSelectionToVisibleRisks(risks);
    renderRiskOverview();
    renderRiskList(risks);
    renderRiskForm();
  }
  function renderRiskOverview() {
    if (!els.overview) {
      return;
    }

    const openRisks = state.riskRegister.filter((risk) => !isRiskClosed(risk));
    const closedRisks = state.riskRegister.filter((risk) => isRiskClosed(risk));
    const highRisks = openRisks.filter((risk) => risk.initialRiskLevel >= 4);

    const cards = [
      {
        label: "Total risks",
        value: state.riskRegister.length,
        note: state.riskRegister.length ? `Business risks currently stored in the ${riskRegisterLabel()}.` : "No business risks have been captured yet.",
      },
      {
        label: "Open risks",
        value: openRisks.length,
        note: openRisks.length ? "Risks without a closure date." : "All captured risks are currently closed.",
      },
      {
        label: "High risks",
        value: highRisks.length,
        note: highRisks.length ? "Open risks with an initial risk level of 4 or 5." : "No open risks are currently rated at level 4 or 5.",
      },
      {
        label: "Closed risks",
        value: closedRisks.length,
        note: closedRisks.length ? "Risks with a recorded closure date." : "No risks have been marked closed yet.",
      },
    ];

    els.overview.innerHTML = cards.map((card) => `
      <article class="stat-card">
        <span class="stat-label">${escapeHtml(card.label)}</span>
        <p class="stat-value">${escapeHtml(String(card.value))}</p>
        <p class="stat-note">${escapeHtml(card.note)}</p>
      </article>
    `).join("");
  }
  function renderRiskList(risks) {
    if (!els.riskList) {
      return;
    }

    if (!state.riskRegister.length) {
      els.riskList.innerHTML = '<div class="empty-state">No risks are in the register yet. Use <strong>Add New Risk</strong> to create the first entry.</div>';
      return;
    }

    if (!risks.length) {
      els.riskList.innerHTML = '<div class="empty-state">No risks match the current search.</div>';
      return;
    }

    const activeRiskId = state.isAddingRisk ? "" : state.selectedRiskId;
    els.riskList.innerHTML = `
      <div class="table-shell risk-table-shell">
        <table>
          <thead>
            <tr>
              <th>Risk</th>
              <th>Level</th>
              <th>Date</th>
              <th>Risk Owner</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            ${risks.map((risk) => `
              <tr class="${risk.id === activeRiskId ? "is-selected" : ""}" data-risk-row="${escapeHtml(risk.id)}">
                <td class="risk-title-cell">
                  <strong>${escapeHtml(risk.risk)}</strong>
                  <div class="mini-copy">${escapeHtml(isRiskClosed(risk) ? `Closed on ${formatDate(risk.closedDate)}` : "Open risk")}</div>
                </td>
                <td>
                  <span class="risk-level-badge level-${risk.initialRiskLevel}">Level ${escapeHtml(String(risk.initialRiskLevel))}</span>
                </td>
                <td>${escapeHtml(formatDate(risk.date))}</td>
                <td>${escapeHtml(risk.owner)}</td>
                <td>
                  <span class="status-pill ${isRiskClosed(risk) ? "is-closed" : "is-active"}">
                    ${escapeHtml(isRiskClosed(risk) ? `Closed ${formatDate(risk.closedDate)}` : "Open")}
                  </span>
                </td>
              </tr>
            `).join("")}
          </tbody>
        </table>
      </div>
    `;
  }
  function renderRiskForm() {
    const selectedRisk = getSelectedRisk();
    const isEditing = Boolean(selectedRisk);

    if (els.riskFormKicker) {
      els.riskFormKicker.textContent = isEditing ? "Selected risk" : "New risk";
    }
    if (els.riskFormTitle) {
      els.riskFormTitle.textContent = isEditing ? "Update risk register entry" : "Capture a new risk";
    }
    if (els.riskFormCopy) {
      els.riskFormCopy.textContent = isEditing
        ? `Update the selected risk and save changes to keep the ${riskRegisterLabel()} current.`
        : `Use this form to add a new risk entry to the ${riskRegisterLabel()}.`;
    }
    if (els.riskNameInput) {
      els.riskNameInput.value = isEditing ? selectedRisk.risk : "";
    }
    if (els.riskDateInput) {
      els.riskDateInput.value = isEditing ? selectedRisk.date : todayDateValue();
    }
    if (els.riskOwnerInput) {
      els.riskOwnerInput.value = isEditing ? selectedRisk.owner : "";
    }
    if (els.riskClosedDateInput) {
      els.riskClosedDateInput.value = isEditing ? selectedRisk.closedDate : "";
    }
    if (els.riskSubmitButton) {
      els.riskSubmitButton.textContent = isEditing ? "Save Changes" : "Save Risk";
    }

    setRiskLevelSelection(isEditing ? selectedRisk.initialRiskLevel : 3);
    renderRiskFormStatus();
  }
  function renderRiskFormStatus() {
    if (!els.riskFormStatus) {
      return;
    }

    const { message, tone } = state.riskFormStatus;
    els.riskFormStatus.textContent = message || `Risk entries are ${storageSentence()}`;
    els.riskFormStatus.className = "helper-note risk-form-status";
    if (tone === "success") {
      els.riskFormStatus.classList.add("is-success");
    }
    if (tone === "error") {
      els.riskFormStatus.classList.add("is-error");
    }
  }
  async function handleRiskFormSubmit(event) {
    event.preventDefault();

    const formData = new FormData(event.currentTarget);
    const riskText = String(formData.get("risk") || "").trim();
    const initialRiskLevel = normalizeRiskLevel(formData.get("initial-risk-level"));
    const raisedDate = normalizeDateInputValue(formData.get("risk-date"));
    const riskOwner = String(formData.get("risk-owner") || "").trim();
    const closedDate = normalizeDateInputValue(formData.get("risk-closed-date"));
    const existingRisk = getSelectedRisk();
    const isEditing = Boolean(existingRisk);

    if (!riskText || !initialRiskLevel || !raisedDate || !riskOwner) {
      setRiskFormStatus("Complete the risk, initial risk level, date, and risk owner before saving.", "error");
      renderRiskFormStatus();
      return;
    }

    if (closedDate && closedDate < raisedDate) {
      setRiskFormStatus("Risk Closed Date cannot be earlier than the Date raised.", "error");
      renderRiskFormStatus();
      return;
    }

    const now = new Date().toISOString();
    const riskId = isEditing ? existingRisk.id : createRiskId();
    const nextRisk = {
      id: riskId,
      risk: riskText,
      initialRiskLevel,
      date: raisedDate,
      owner: riskOwner,
      closedDate,
      createdAt: isEditing ? existingRisk.createdAt || now : now,
      updatedAt: now,
    };

    const previousRiskRegister = state.riskRegister.slice();
    state.riskRegister = isEditing
      ? state.riskRegister.map((risk) => (risk.id === riskId ? nextRisk : risk))
      : [nextRisk].concat(state.riskRegister);

    try {
      await saveRiskRegister();
    } catch (error) {
      state.riskRegister = previousRiskRegister;
      setRiskFormStatus(error.message || "Unable to save the risk register entry.", "error");
      renderRiskFormStatus();
      return;
    }

    state.selectedRiskId = riskId;
    state.isAddingRisk = false;
    setRiskFormStatus(
      isEditing ? `Risk updated in the ${riskRegisterLabel()}.` : `Risk added to the ${riskRegisterLabel()}.`,
      "success"
    );
    syncUrl();
    renderRisksPage();
  }
  function setRiskFormStatus(message, tone) {
    state.riskFormStatus = {
      message: message || "",
      tone: tone || "",
    };
  }
  function clearRiskFormStatus() {
    setRiskFormStatus("", "");
  }
  function setRiskLevelSelection(level) {
    els.riskLevelInputs.forEach((input) => {
      input.checked = Number(input.value) === level;
    });
  }
  function filteredRisks() {
    const searchLower = state.search.trim().toLowerCase();
    return state.riskRegister
      .slice()
      .filter((risk) => {
        if (!searchLower) {
          return true;
        }
        const searchableText = [
          risk.risk,
          risk.owner,
          risk.date,
          risk.closedDate,
          `level ${risk.initialRiskLevel}`,
          isRiskClosed(risk) ? "closed" : "open",
        ].join(" ").toLowerCase();
        return searchableText.includes(searchLower);
      })
      .sort((left, right) => {
        const closedDelta = Number(isRiskClosed(left)) - Number(isRiskClosed(right));
        if (closedDelta !== 0) {
          return closedDelta;
        }
        if (left.initialRiskLevel !== right.initialRiskLevel) {
          return right.initialRiskLevel - left.initialRiskLevel;
        }
        if (left.date !== right.date) {
          return right.date.localeCompare(left.date);
        }
        return (right.updatedAt || right.createdAt || "").localeCompare(left.updatedAt || left.createdAt || "");
      });
  }
  function getSelectedRisk() {
    if (state.isAddingRisk || !state.selectedRiskId) {
      return null;
    }
    return state.riskRegister.find((risk) => risk.id === state.selectedRiskId) || null;
  }
  function syncSelectionToVisibleRisks(risks) {
    if (state.isAddingRisk) {
      return;
    }

    const visibleRisks = Array.isArray(risks) ? risks : filteredRisks();
    const selectionExists = state.riskRegister.some((risk) => risk.id === state.selectedRiskId);
    if (selectionExists) {
      return;
    }
    state.selectedRiskId = visibleRisks[0] ? visibleRisks[0].id : "";
  }
  function isRiskClosed(risk) {
    return Boolean(risk.closedDate);
  }
  async function saveRiskRegister() {
    if (!isApiPersistence()) {
      window.localStorage.setItem(riskRegisterKey, JSON.stringify(state.riskRegister));
      return;
    }

    const payload = await apiRequest("/risks/", {
      method: "PUT",
      body: JSON.stringify({ riskRegister: state.riskRegister }),
    });

    if (payload && Array.isArray(payload.riskRegister)) {
      state.riskRegister = payload.riskRegister.map((item) => normalizeRiskRecord(item)).filter(Boolean);
    }
  }
  function loadRiskRegister() {
    try {
      const saved = JSON.parse(window.localStorage.getItem(riskRegisterKey) || "[]");
      if (!Array.isArray(saved)) {
        return [];
      }
      return saved
        .map((item) => normalizeRiskRecord(item))
        .filter(Boolean);
    } catch (error) {
      return [];
    }
  }
  function normalizeRiskRecord(item) {
    if (!item || typeof item !== "object") {
      return null;
    }

    const riskText = typeof item.risk === "string" ? item.risk.trim() : "";
    const initialRiskLevel = normalizeRiskLevel(item.initialRiskLevel);
    const raisedDate = normalizeDateInputValue(item.date);
    if (!riskText || !initialRiskLevel || !raisedDate) {
      return null;
    }

    return {
      id: typeof item.id === "string" && item.id ? item.id : createRiskId(),
      risk: riskText,
      initialRiskLevel,
      date: raisedDate,
      owner: typeof item.owner === "string" ? item.owner.trim() : "",
      closedDate: normalizeDateInputValue(item.closedDate),
      createdAt: typeof item.createdAt === "string" ? item.createdAt : "",
      updatedAt: typeof item.updatedAt === "string" ? item.updatedAt : "",
    };
  }
  function createRiskId() {
    return `risk-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
  }
  function riskRegisterLabel() {
    return isApiPersistence() ? "shared portal register" : "browser register";
  }
  function normalizeRiskLevel(value) {
    const parsed = Number(value);
    return Number.isInteger(parsed) && parsed >= 1 && parsed <= 5 ? parsed : 0;
  }
  function normalizeDateInputValue(value) {
    if (typeof value === "string" && /^\d{4}-\d{2}-\d{2}$/.test(value.trim())) {
      return value.trim();
    }

    if (typeof value !== "string" || !value.trim()) {
      return "";
    }

    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) {
      return "";
    }
    return formatDateInputValue(parsed);
  }
  function formatDateInputValue(date) {
    const normalizedDate = date instanceof Date ? date : new Date(date);
    if (Number.isNaN(normalizedDate.getTime())) {
      return "";
    }
    const year = normalizedDate.getFullYear();
    const month = String(normalizedDate.getMonth() + 1).padStart(2, "0");
    const day = String(normalizedDate.getDate()).padStart(2, "0");
    return `${year}-${month}-${day}`;
  }
  function todayDateValue() {
    return formatDateInputValue(new Date());
  }
  function formatDate(value) {
    const normalizedValue = normalizeDateInputValue(value);
    if (!normalizedValue) {
      return "-";
    }

    const [year, month, day] = normalizedValue.split("-").map(Number);
    return new Intl.DateTimeFormat(undefined, {
      year: "numeric",
      month: "short",
      day: "numeric",
    }).format(new Date(year, month - 1, day));
  }
