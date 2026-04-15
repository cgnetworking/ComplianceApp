  const probabilityFieldNames = ["risk-probability", "probability", "initial-risk-probability"];
  const impactFieldNames = ["risk-impact", "impact", "initial-risk-impact"];

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
    const highRisks = openRisks.filter((risk) => risk.initialRiskLevel >= 10);

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
        note: highRisks.length
          ? "Open risks with a matrix score of 10 or higher (high or above)."
          : "No open risks are currently at high matrix score or above.",
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
              <th>Probability</th>
              <th>Impact</th>
              <th>Score</th>
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
                <td>${escapeHtml(String(risk.probability))}</td>
                <td>${escapeHtml(String(risk.impact))}</td>
                <td>
                  <span class="risk-level-badge level-${riskBadgeLevel(risk.probability, risk.impact)}">${escapeHtml(String(risk.initialRiskLevel))}</span>
                  <div class="mini-copy">${escapeHtml(`P${risk.probability} x I${risk.impact} / ${riskBandLabel(risk.probability, risk.impact)}`)}</div>
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

    setRiskFormFactorSelections(isEditing ? selectedRisk.probability : 3, isEditing ? selectedRisk.impact : 3);
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
    const legacyRiskLevel = normalizeRiskFactor(formData.get("initial-risk-level"));
    const probability = normalizeRiskFactor(readFirstFormValue(formData, probabilityFieldNames)) || legacyRiskLevel;
    const impact = normalizeRiskFactor(readFirstFormValue(formData, impactFieldNames)) || legacyRiskLevel;
    const initialRiskLevel = probability * impact;
    const raisedDate = normalizeDateInputValue(formData.get("risk-date"));
    const riskOwner = String(formData.get("risk-owner") || "").trim();
    const closedDate = normalizeDateInputValue(formData.get("risk-closed-date"));
    const existingRisk = getSelectedRisk();
    const isEditing = Boolean(existingRisk);

    if (!riskText || !probability || !impact || !raisedDate || !riskOwner) {
      setRiskFormStatus("Complete the risk, probability, impact, date, and risk owner before saving.", "error");
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
      probability,
      impact,
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
  function setRiskFormFactorSelections(probability, impact) {
    setSingleRiskFactorSelection(els.riskProbabilityInput, probability);
    setSingleRiskFactorSelection(els.riskImpactInput, impact);
    setRiskFactorSelection(els.riskProbabilityInputs, probability);
    setRiskFactorSelection(els.riskImpactInputs, impact);
    setRiskFactorSelection(els.riskLevelInputs, Math.max(probability, impact));
  }
  function setSingleRiskFactorSelection(element, factor) {
    if (!element) {
      return;
    }
    if (String(element.type).toLowerCase() === "radio") {
      return;
    }
    element.value = String(factor);
  }
  function setRiskFactorSelection(inputs, factor) {
    inputs.forEach((input) => {
      input.checked = Number(input.value) === factor;
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
          `probability ${risk.probability}`,
          `impact ${risk.impact}`,
          `score ${risk.initialRiskLevel}`,
          `p${risk.probability}`,
          `i${risk.impact}`,
          riskBandLabel(risk.probability, risk.impact),
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
        if (left.impact !== right.impact) {
          return right.impact - left.impact;
        }
        if (left.probability !== right.probability) {
          return right.probability - left.probability;
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
    const legacyRiskScore = normalizeRiskScore(item.initialRiskLevel);
    const { probability, impact } = normalizeRiskFactors(item.probability, item.impact, legacyRiskScore);
    const initialRiskLevel = probability * impact;
    const raisedDate = normalizeDateInputValue(item.date);
    if (!riskText || !probability || !impact || !raisedDate) {
      return null;
    }

    return {
      id: typeof item.id === "string" && item.id ? item.id : createRiskId(),
      risk: riskText,
      probability,
      impact,
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
  function readFirstFormValue(formData, keys) {
    for (const key of keys) {
      const value = formData.get(key);
      if (typeof value === "string" && value.trim()) {
        return value;
      }
      if (value !== null && value !== undefined && String(value).trim()) {
        return String(value);
      }
    }
    return "";
  }
  function normalizeRiskFactor(value) {
    const parsed = Number(value);
    return Number.isInteger(parsed) && parsed >= 1 && parsed <= 5 ? parsed : 0;
  }
  function normalizeRiskScore(value) {
    const parsed = Number(value);
    return Number.isInteger(parsed) && parsed >= 1 && parsed <= 25 ? parsed : 0;
  }
  function normalizeRiskFactors(probabilityValue, impactValue, legacyScoreValue) {
    let probability = normalizeRiskFactor(probabilityValue);
    let impact = normalizeRiskFactor(impactValue);
    const legacyScore = normalizeRiskScore(legacyScoreValue);

    if (probability && impact) {
      return { probability, impact };
    }
    if (!legacyScore) {
      return { probability, impact };
    }

    const fallback = riskFactorsFromLegacyScore(legacyScore);
    if (probability && !impact) {
      impact = inferMissingRiskFactor(probability, legacyScore, fallback.impact);
    } else if (impact && !probability) {
      probability = inferMissingRiskFactor(impact, legacyScore, fallback.probability);
    } else {
      probability = probability || fallback.probability;
      impact = impact || fallback.impact;
    }
    return { probability, impact };
  }
  function inferMissingRiskFactor(knownFactor, score, fallbackFactor) {
    if (knownFactor && score && score % knownFactor === 0) {
      const derived = score / knownFactor;
      if (Number.isInteger(derived) && derived >= 1 && derived <= 5) {
        return derived;
      }
    }
    return normalizeRiskFactor(fallbackFactor);
  }
  function riskFactorsFromLegacyScore(score) {
    if (score <= 5) {
      return { probability: score, impact: score };
    }
    return closestRiskFactorPair(score);
  }
  function closestRiskFactorPair(score) {
    const target = Math.min(Math.max(score, 1), 25);
    let best = null;

    for (let probability = 1; probability <= 5; probability += 1) {
      for (let impact = 1; impact <= 5; impact += 1) {
        const product = probability * impact;
        if (product < target) {
          continue;
        }
        const candidate = {
          delta: product - target,
          spread: Math.abs(probability - impact),
          score: product,
          maxFactor: Math.max(probability, impact),
          probability,
          impact,
        };
        if (!best || compareRiskFactorCandidates(candidate, best) < 0) {
          best = candidate;
        }
      }
    }

    if (!best) {
      return { probability: 5, impact: 5 };
    }
    return { probability: best.probability, impact: best.impact };
  }
  function compareRiskFactorCandidates(left, right) {
    if (left.delta !== right.delta) {
      return left.delta - right.delta;
    }
    if (left.spread !== right.spread) {
      return left.spread - right.spread;
    }
    if (left.score !== right.score) {
      return right.score - left.score;
    }
    if (left.maxFactor !== right.maxFactor) {
      return right.maxFactor - left.maxFactor;
    }
    if (left.probability !== right.probability) {
      return left.probability - right.probability;
    }
    return left.impact - right.impact;
  }
  function riskBadgeLevel(probability, impact) {
    const bandKey = riskBandKey(probability, impact);
    if (bandKey === "extreme" || bandKey === "very-high") {
      return 5;
    }
    if (bandKey === "high") {
      return 4;
    }
    if (bandKey === "medium") {
      return 3;
    }
    if (bandKey === "low") {
      return 2;
    }
    return 1;
  }
  function riskBandLabel(probability, impact) {
    const bandKey = riskBandKey(probability, impact);
    if (bandKey === "very-low") {
      return "Very low";
    }
    if (bandKey === "very-high") {
      return "Very high";
    }
    if (bandKey === "extreme") {
      return "Extreme";
    }
    return bandKey.charAt(0).toUpperCase() + bandKey.slice(1);
  }
  function riskBandKey(probability, impact) {
    const normalizedProbability = normalizeRiskFactor(probability);
    const normalizedImpact = normalizeRiskFactor(impact);
    if (!normalizedProbability || !normalizedImpact) {
      return "very-low";
    }

    const matrix = [
      ["very-low", "very-low", "low", "medium", "medium"],
      ["very-low", "low", "medium", "medium", "high"],
      ["low", "medium", "medium", "high", "very-high"],
      ["medium", "medium", "high", "very-high", "extreme"],
      ["medium", "high", "very-high", "extreme", "extreme"],
    ];
    return matrix[normalizedProbability - 1][normalizedImpact - 1];
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
    return formatDateWithOrdinal(normalizedValue);
  }
