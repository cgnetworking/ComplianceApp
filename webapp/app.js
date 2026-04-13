(function () {
  const data = window.ISMS_DATA;
  if (!data) {
    return;
  }

  const monthNames = [
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
  ];
  const shortMonths = monthNames.map((month) => month.slice(0, 3));
  const cadenceLabels = ["Annual", "Quarterly", "Monthly", "Event", "Change"];
  const domainColors = {
    Organizational: "#7442b8",
    People: "#9d3f9d",
    Physical: "#d05ad4",
    Technological: "#4e92e6",
  };
  const storageKey = "isms-policy-portal-review-state-v1";
  const controlStateKey = "isms-policy-portal-control-state-v1";
  const controlsById = new Map(data.controls.map((control) => [control.id, control]));
  const documentsById = new Map(data.documents.map((documentItem) => [documentItem.id, documentItem]));
  const today = new Date();
  const page = document.body.dataset.page || "home";
  const params = new URLSearchParams(window.location.search);

  const state = {
    search: params.get("q") || "",
    domain: params.get("domain") || "All",
    applicability: params.get("applicability") || "All",
    frequency: params.get("frequency") || "All",
    monthIndex: parseMonth(params.get("month")),
    selectedControlId: params.get("control"),
    activeDocumentId: params.get("doc"),
    reviewState: loadReviewState(),
    controlState: loadControlState(),
  };

  const els = {
    runtimeMode: document.getElementById("runtime-mode"),
    generatedAt: document.getElementById("generated-at"),
    searchInput: document.getElementById("search-input"),
    domainFilter: document.getElementById("domain-filter"),
    applicabilityFilter: document.getElementById("applicability-filter"),
    frequencyFilter: document.getElementById("frequency-filter"),
    clearFilters: document.getElementById("clear-filters"),
    overview: document.getElementById("overview"),
    frameworkChart: document.getElementById("framework-chart"),
    timelineChart: document.getElementById("timeline-chart"),
    reportDomains: document.getElementById("report-domains"),
    controlsBody: document.getElementById("controls-body"),
    controlDetail: document.getElementById("control-detail"),
    selectedControlBanner: document.getElementById("selected-control-banner"),
    policyCoverage: document.getElementById("policy-coverage"),
    documentViewer: document.getElementById("document-viewer"),
    monthTabs: document.getElementById("month-tabs"),
    activities: document.getElementById("activities"),
    checklistSummary: document.getElementById("checklist-summary"),
    checklist: document.getElementById("checklist"),
    homeUpcoming: document.getElementById("home-upcoming"),
    homeDomains: document.getElementById("home-domains"),
    homePolicies: document.getElementById("home-policies"),
  };

  init();

  function init() {
    if (els.runtimeMode) {
      els.runtimeMode.textContent = data.sourceSnapshot.runtimeDependency ? "Workbook dependent" : "Embedded snapshot";
    }
    if (els.generatedAt) {
      els.generatedAt.textContent = formatDateTime(data.generatedAt);
    }
    if (els.searchInput) {
      els.searchInput.value = state.search;
    }

    populateFilters();
    initializeSelection();
    bindEvents();
    renderPage();
  }

  function populateFilters() {
    if (els.domainFilter) {
      populateSelect(els.domainFilter, ["All"].concat(uniqueValues(data.controls, "domain")));
      els.domainFilter.value = valueOrFallback(els.domainFilter, state.domain);
      state.domain = els.domainFilter.value;
    }
    if (els.applicabilityFilter) {
      populateSelect(els.applicabilityFilter, ["All"].concat(uniqueValues(data.controls, "applicability")));
      els.applicabilityFilter.value = valueOrFallback(els.applicabilityFilter, state.applicability);
      state.applicability = els.applicabilityFilter.value;
    }
    if (els.frequencyFilter) {
      populateSelect(els.frequencyFilter, ["All"].concat(uniqueValues(data.controls, "reviewFrequency")));
      els.frequencyFilter.value = valueOrFallback(els.frequencyFilter, state.frequency);
      state.frequency = els.frequencyFilter.value;
    }
  }

  function initializeSelection() {
    if (page === "controls" || page === "reports") {
      syncSelectionToVisibleControls();
    }
    if (page === "policies") {
      initializePolicySelection();
    }
  }

  function bindEvents() {
    if (els.searchInput) {
      if (page === "controls" || page === "reports" || page === "policies") {
        els.searchInput.addEventListener("input", (event) => {
          state.search = event.target.value.trim();
          if (page === "policies") {
            initializePolicySelection();
          } else {
            syncSelectionToVisibleControls();
          }
          syncUrl();
          renderPage();
        });
      } else {
        els.searchInput.addEventListener("keydown", (event) => {
          if (event.key !== "Enter") {
            return;
          }
          const query = els.searchInput.value.trim();
          const target = query ? `./controls.html?q=${encodeURIComponent(query)}` : "./controls.html";
          window.location.href = target;
        });
      }
    }

    if (els.domainFilter) {
      els.domainFilter.addEventListener("change", (event) => {
        state.domain = event.target.value;
        syncSelectionToVisibleControls();
        syncUrl();
        renderPage();
      });
    }

    if (els.applicabilityFilter) {
      els.applicabilityFilter.addEventListener("change", (event) => {
        state.applicability = event.target.value;
        syncSelectionToVisibleControls();
        syncUrl();
        renderPage();
      });
    }

    if (els.frequencyFilter) {
      els.frequencyFilter.addEventListener("change", (event) => {
        state.frequency = event.target.value;
        syncSelectionToVisibleControls();
        syncUrl();
        renderPage();
      });
    }

    if (els.clearFilters) {
      els.clearFilters.addEventListener("click", () => {
        state.search = "";
        state.domain = "All";
        state.applicability = "All";
        state.frequency = "All";
        if (els.searchInput) {
          els.searchInput.value = "";
        }
        if (els.domainFilter) {
          els.domainFilter.value = "All";
        }
        if (els.applicabilityFilter) {
          els.applicabilityFilter.value = "All";
        }
        if (els.frequencyFilter) {
          els.frequencyFilter.value = "All";
        }
        if (page === "policies") {
          initializePolicySelection();
        } else {
          syncSelectionToVisibleControls();
        }
        syncUrl();
        renderPage();
      });
    }

    if (els.controlsBody) {
      els.controlsBody.addEventListener("click", (event) => {
        const policyLink = event.target.closest("a[data-policy-link]");
        if (policyLink) {
          return;
        }
        const row = event.target.closest("[data-control-row]");
        if (!row) {
          return;
        }
        state.selectedControlId = row.dataset.controlRow;
        syncUrl();
        renderControlsPage();
      });
    }

    if (els.controlDetail) {
      els.controlDetail.addEventListener("change", (event) => {
        const toggle = event.target.closest("[data-control-excluded]");
        if (!toggle) {
          return;
        }
        const controlId = toggle.dataset.controlExcluded;
        setControlExclusion(controlId, toggle.checked);
        renderControlsPage();
      });

      els.controlDetail.addEventListener("input", (event) => {
        const reason = event.target.closest("[data-exclusion-reason]");
        if (!reason) {
          return;
        }
        updateControlReason(reason.dataset.exclusionReason, reason.value);
      });
    }

    if (els.policyCoverage) {
      els.policyCoverage.addEventListener("click", (event) => {
        const target = event.target.closest("[data-policy-doc]");
        if (!target) {
          return;
        }
        state.activeDocumentId = target.dataset.policyDoc;
        if (target.dataset.policyControl) {
          state.selectedControlId = target.dataset.policyControl;
        }
        syncUrl();
        renderPoliciesPage();
      });
    }

    if (els.selectedControlBanner) {
      els.selectedControlBanner.addEventListener("click", (event) => {
        const target = event.target.closest("[data-policy-doc]");
        if (!target) {
          return;
        }
        state.activeDocumentId = target.dataset.policyDoc;
        syncUrl();
        renderPoliciesPage();
      });
    }

    if (els.monthTabs) {
      els.monthTabs.addEventListener("click", (event) => {
        const target = event.target.closest("[data-month-index]");
        if (!target) {
          return;
        }
        state.monthIndex = Number(target.dataset.monthIndex);
        syncUrl();
        renderReviewsPage();
      });
    }

    if (els.activities) {
      els.activities.addEventListener("change", (event) => {
        const target = event.target.closest("[data-activity-id]");
        if (!target) {
          return;
        }
        state.reviewState.activities[target.dataset.activityId] = target.checked;
        saveReviewState();
        renderReviewsPage();
      });
    }

    if (els.checklist) {
      els.checklist.addEventListener("change", (event) => {
        const target = event.target.closest("[data-check-id]");
        if (!target) {
          return;
        }
        state.reviewState.checklist[target.dataset.checkId] = target.checked;
        saveReviewState();
        renderReviewsPage();
      });
    }
  }

  function renderPage() {
    switch (page) {
      case "home":
        renderHomePage();
        break;
      case "reports":
        renderReportsPage();
        break;
      case "controls":
        renderControlsPage();
        break;
      case "reviews":
        renderReviewsPage();
        break;
      case "policies":
        renderPoliciesPage();
        break;
      default:
        renderHomePage();
        break;
    }
  }

  function renderHomePage() {
    renderGlobalOverview(data.controls, {
      mode: "home",
      currentMonthActivities: monthlyActivities(state.monthIndex),
    });
    renderHomeUpcoming();
    renderHomeDomains();
    renderHomePolicies();
  }

  function renderReportsPage() {
    const controls = filteredControls();
    renderGlobalOverview(controls, {
      mode: "reports",
      currentMonthActivities: monthlyActivities(state.monthIndex),
    });
    renderFrameworkChart(controls);
    renderTimelineChart();
    renderReportDomains(controls);
    renderPolicyCoverageList(visiblePoliciesForControls(controls), false);
  }

  function renderControlsPage() {
    const controls = filteredControls();
    renderControlsTable(controls);
    renderControlDetail();
  }

  function renderReviewsPage() {
    renderReviewOverview();
    renderMonthTabs();
    renderActivities();
    renderChecklist();
  }

  function renderPoliciesPage() {
    initializePolicySelection();
    renderSelectedControlBanner();
    renderPolicyCoverageList(filteredPolicyCoverage(), true);
    renderDocumentViewer();
  }

  function renderGlobalOverview(controls, options) {
    if (!els.overview) {
      return;
    }

    const checklistDone = data.checklist.filter((item) => state.reviewState.checklist[item.id]).length;
    const activityDone = options.currentMonthActivities.filter((item) => state.reviewState.activities[item.id]).length;
    const mappedPolicies = new Set(controls.flatMap((control) => control.policyDocumentIds)).size;

    const cards = options.mode === "reports"
      ? [
          {
            label: "Controls in view",
            value: controls.length,
            note: controls.length === data.controls.length ? "All controls included in the report." : "Filtered control population for this report.",
          },
          {
            label: "Applicable controls",
            value: controls.filter((control) => control.applicability === "Applicable").length,
            note: "Applicable controls in the currently filtered set.",
          },
          {
            label: "Mapped policies",
            value: mappedPolicies,
            note: "Unique policies referenced by the visible controls.",
          },
          {
            label: "Current month queue",
            value: `${activityDone}/${options.currentMonthActivities.length}`,
            note: "Review activities completed in this browser.",
          },
        ]
      : [
          {
            label: "Total controls",
            value: data.controls.length,
            note: "Embedded Annex A register available locally.",
          },
          {
            label: "Policies embedded",
            value: data.summary.policyCount,
            note: "Policy pages remain available without the workbook.",
          },
          {
            label: `${monthNames[state.monthIndex]} queue`,
            value: `${activityDone}/${options.currentMonthActivities.length}`,
            note: "Current month review completion.",
          },
          {
            label: "Checklist progress",
            value: `${checklistDone}/${data.checklist.length}`,
            note: "Recurring review checks marked complete.",
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

  function renderReviewOverview() {
    if (!els.overview) {
      return;
    }

    const monthItems = monthlyActivities(state.monthIndex);
    const completedMonthItems = monthItems.filter((item) => state.reviewState.activities[item.id]).length;
    const completedChecklist = data.checklist.filter((item) => state.reviewState.checklist[item.id]).length;

    const cards = [
      {
        label: `${monthNames[state.monthIndex]} queue`,
        value: `${completedMonthItems}/${monthItems.length}`,
        note: "Scheduled activities completed this month.",
      },
      {
        label: "Annual activities",
        value: data.activities.length,
        note: "Review tasks loaded from the annual schedule snapshot.",
      },
      {
        label: "Checklist progress",
        value: `${completedChecklist}/${data.checklist.length}`,
        note: "Recurring checks completed in this browser.",
      },
      {
        label: "Quarterly checks",
        value: data.checklist.filter((item) => item.frequency === "Quarterly").length,
        note: "Recurring quarterly checks in the embedded checklist.",
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

  function renderHomeUpcoming() {
    if (!els.homeUpcoming) {
      return;
    }

    const upcoming = orderedActivitiesFromCurrentMonth().slice(0, 5);
    els.homeUpcoming.innerHTML = `
      <div class="stack-list">
        ${upcoming.map((activity) => `
          <article class="list-card">
            <strong>${escapeHtml(activity.activity)}</strong>
            <div class="mini-copy">${escapeHtml(activity.month)} / ${escapeHtml(activity.frequency)} / ${escapeHtml(activity.owner)}</div>
            <div class="mini-copy">Evidence: ${escapeHtml(activity.evidence)}</div>
          </article>
        `).join("")}
      </div>
    `;
  }

  function renderHomeDomains() {
    if (!els.homeDomains) {
      return;
    }

    const total = data.controls.length || 1;
    const rows = uniqueValues(data.controls, "domain").map((domain) => {
      const count = data.controls.filter((control) => control.domain === domain).length;
      return { domain, count, width: (count / total) * 100 };
    });

    els.homeDomains.innerHTML = `
      <div class="stack-list">
        ${rows.map((row) => `
          <article class="metric-row">
            <div class="metric-head">
              <strong>${escapeHtml(row.domain)}</strong>
              <span>${row.count}</span>
            </div>
            <div class="metric-bar">
              <span style="width:${row.width}%;background:${domainColors[row.domain] || "#7442b8"}"></span>
            </div>
          </article>
        `).join("")}
      </div>
    `;
  }

  function renderHomePolicies() {
    if (!els.homePolicies) {
      return;
    }

    const topPolicies = data.policyCoverage.slice(0, 6);
    els.homePolicies.innerHTML = `
      <div class="coverage-list">
        ${topPolicies.map((item) => `
          <a class="coverage-card coverage-link" href="${policyUrl(null, item.id)}">
            <div>
              <strong>${escapeHtml(item.id)} / ${escapeHtml(item.title)}</strong>
              <div class="mini-copy">${item.controlCount} mapped controls / ${escapeHtml(item.reviewFrequency)}</div>
            </div>
            <span class="doc-type">${item.controlCount}</span>
          </a>
        `).join("")}
      </div>
    `;
  }

  function renderFrameworkChart(controls) {
    if (!els.frameworkChart) {
      return;
    }
    if (!controls.length) {
      els.frameworkChart.innerHTML = '<div class="empty-state">No controls are available for the current filter set.</div>';
      return;
    }

    const visibleDomains = uniqueValues(controls, "domain");
    const series = visibleDomains.map((domain) => {
      const scopedControls = controls.filter((control) => control.domain === domain);
      return {
        name: domain,
        color: domainColors[domain] || "#7442b8",
        values: cadenceLabels.map((label) => scopedControls.filter((control) => reviewCadence(control.reviewFrequency) === label).length),
      };
    });

    const width = 760;
    const height = 240;
    const padding = { top: 16, right: 20, bottom: 42, left: 36 };
    const plotWidth = width - padding.left - padding.right;
    const plotHeight = height - padding.top - padding.bottom;
    const maxValue = Math.max(1, ...series.flatMap((item) => item.values));
    const stepX = plotWidth / Math.max(1, cadenceLabels.length - 1);

    const gridLines = [];
    for (let index = 0; index <= 4; index += 1) {
      const y = padding.top + (plotHeight * index) / 4;
      const label = Math.round(maxValue - (maxValue * index) / 4);
      gridLines.push(`
        <line class="chart-grid-line" x1="${padding.left}" y1="${y}" x2="${width - padding.right}" y2="${y}"></line>
        <text class="axis-label" x="${padding.left - 10}" y="${y + 4}" text-anchor="end">${label}</text>
      `);
    }

    const paths = series.map((item) => {
      const points = item.values.map((value, index) => ({
        x: padding.left + stepX * index,
        y: padding.top + plotHeight - (value / maxValue) * plotHeight,
      }));

      return `
        <path d="${buildSmoothPath(points)}" fill="none" stroke="${item.color}" stroke-width="3.5" stroke-linecap="round"></path>
        ${points.map((point) => `<circle class="chart-point" cx="${point.x}" cy="${point.y}" r="4.5" fill="${item.color}"></circle>`).join("")}
      `;
    }).join("");

    const axisLabels = cadenceLabels.map((label, index) => {
      const x = padding.left + stepX * index;
      return `<text class="axis-label" x="${x}" y="${height - 10}" text-anchor="middle">${escapeHtml(label)}</text>`;
    }).join("");

    els.frameworkChart.innerHTML = `
      <div class="chart-wrap">
        <svg class="chart-svg" viewBox="0 0 ${width} ${height}" role="img" aria-label="Coverage by review cadence">
          ${gridLines.join("")}
          <line class="chart-axis-line" x1="${padding.left}" y1="${height - padding.bottom}" x2="${width - padding.right}" y2="${height - padding.bottom}"></line>
          ${paths}
          ${axisLabels}
        </svg>
        <div class="legend-row">
          ${series.map((item) => `
            <span class="legend-item">
              <span class="legend-swatch" style="background:${item.color}"></span>
              ${escapeHtml(item.name)}
            </span>
          `).join("")}
        </div>
      </div>
    `;
  }

  function renderTimelineChart() {
    if (!els.timelineChart) {
      return;
    }

    const windows = buildAuditWindows();
    if (!windows.length) {
      els.timelineChart.innerHTML = '<div class="empty-state">No annual review windows are available.</div>';
      return;
    }

    els.timelineChart.innerHTML = `
      <div class="timeline-grid">
        <div class="timeline-head">
          <div class="timeline-label-slot"></div>
          <div class="timeline-month-row">
            ${shortMonths.map((month, index) => `
              <span class="timeline-month ${index === today.getMonth() ? "is-current" : ""}">${escapeHtml(month)}</span>
            `).join("")}
          </div>
        </div>
        ${windows.map((windowItem) => {
          const left = `${(windowItem.start / 12) * 100}%`;
          const width = `${((windowItem.end - windowItem.start + 1) / 12) * 100}%`;
          return `
            <div class="timeline-row">
              <div class="timeline-label-block">
                <strong>${escapeHtml(windowItem.label)}</strong>
                <span>${windowItem.count} activities</span>
              </div>
              <div class="timeline-track">
                <div class="timeline-columns">
                  ${shortMonths.map((_, index) => `<span class="${index === today.getMonth() ? "is-current" : ""}"></span>`).join("")}
                </div>
                <div class="timeline-bar" style="left:${left};width:${width};background:${windowItem.color}"></div>
              </div>
            </div>
          `;
        }).join("")}
      </div>
    `;
  }

  function renderReportDomains(controls) {
    if (!els.reportDomains) {
      return;
    }
    if (!controls.length) {
      els.reportDomains.innerHTML = '<div class="empty-state">No control counts are available for the current filter set.</div>';
      return;
    }

    const total = controls.length;
    const rows = uniqueValues(controls, "domain").map((domain) => {
      const count = controls.filter((control) => control.domain === domain).length;
      return { domain, count, width: (count / total) * 100 };
    });

    els.reportDomains.innerHTML = `
      <div class="stack-list">
        ${rows.map((row) => `
          <article class="metric-row">
            <div class="metric-head">
              <strong>${escapeHtml(row.domain)}</strong>
              <span>${row.count} controls</span>
            </div>
            <div class="metric-bar">
              <span style="width:${row.width}%;background:${domainColors[row.domain] || "#7442b8"}"></span>
            </div>
          </article>
        `).join("")}
      </div>
    `;
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
      const view = getControlView(control);
      return `
      <tr class="${view.id === state.selectedControlId ? "is-selected" : ""}" data-control-row="${escapeHtml(view.id)}">
        <td><a class="control-link" data-policy-link="true" href="${policyUrl(view.id, view.preferredDocumentId)}">${escapeHtml(view.id)}</a></td>
        <td>${escapeHtml(view.name)}</td>
        <td>${escapeHtml(view.domain)}</td>
        <td>${escapeHtml(view.effectiveImplementationModel)}</td>
        <td>${escapeHtml(view.reviewFrequency)}</td>
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
          <span class="chip">${escapeHtml(control.applicability)}</span>
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
            ${escapeHtml(control.isBaseExcluded ? "This control is already excluded in the embedded source data." : "Locally excluded controls display as Excluded in this portal and retain a required exclusion rationale in browser storage.")}
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

  function renderSelectedControlBanner() {
    if (!els.selectedControlBanner) {
      return;
    }
    const control = controlsById.get(state.selectedControlId);
    if (!control) {
      els.selectedControlBanner.innerHTML = `
        <article class="panel">
          <div class="empty-state">Open this page from a control number or choose a policy below.</div>
        </article>
      `;
      return;
    }

    const docButtons = control.documentIds.map((documentId) => {
      const documentItem = documentsById.get(documentId);
      if (!documentItem) {
        return "";
      }
      return `
        <button class="doc-button ${documentId === state.activeDocumentId ? "is-active" : ""}" type="button" data-policy-doc="${escapeHtml(documentId)}" data-policy-control="${escapeHtml(control.id)}">
          ${escapeHtml(documentItem.id)} / ${escapeHtml(documentItem.title)}
          <small>${escapeHtml(documentItem.type)} / ${escapeHtml(documentItem.reviewFrequency)}</small>
        </button>
      `;
    }).join("");

    els.selectedControlBanner.innerHTML = `
      <article class="panel">
        <div class="detail-header">
          <div>
            <p class="panel-kicker">Opened from control</p>
            <h3>${escapeHtml(control.id)} / ${escapeHtml(control.name)}</h3>
          </div>
          <div class="chip-row">
            <span class="chip">${escapeHtml(control.domain)}</span>
            <span class="chip">${escapeHtml(control.reviewFrequency)}</span>
          </div>
          <p class="detail-subline">${escapeHtml(control.rationale)}</p>
        </div>
        <div class="doc-section">
          <strong>Mapped documents</strong>
          <div class="doc-list">
            ${docButtons || '<div class="empty-state">No embedded documents are mapped to this control.</div>'}
          </div>
        </div>
      </article>
    `;
  }

  function renderPolicyCoverageList(rows, interactive) {
    if (!els.policyCoverage) {
      return;
    }
    if (!rows.length) {
      els.policyCoverage.innerHTML = '<div class="empty-state">No policies match the current selection.</div>';
      return;
    }

    els.policyCoverage.innerHTML = `
      <div class="coverage-list">
        ${rows.map((item) => {
          const documentItem = documentsById.get(item.id);
          const controlId = firstControlIdForDocument(item.id);
          const active = state.activeDocumentId === item.id;
          const href = policyUrl(controlId, item.id);
          if (!interactive) {
            return `
              <a class="coverage-card coverage-link" href="${href}">
                <div>
                  <strong>${escapeHtml(item.id)} / ${escapeHtml(item.title)}</strong>
                  <div class="mini-copy">${item.controlCount} mapped controls / ${escapeHtml(item.reviewFrequency)}</div>
                </div>
                <span class="doc-type">${item.controlCount}</span>
              </a>
            `;
          }
          return `
            <button class="coverage-card coverage-button ${active ? "is-selected" : ""}" type="button" data-policy-doc="${escapeHtml(item.id)}" data-policy-control="${escapeHtml(controlId || "")}">
              <div>
                <strong>${escapeHtml(item.id)} / ${escapeHtml(item.title)}</strong>
                <div class="mini-copy">${item.controlCount} mapped controls / ${escapeHtml(item.reviewFrequency)}</div>
                <div class="mini-copy">${escapeHtml(documentItem ? documentItem.type : "Document")}</div>
              </div>
              <span class="doc-type">${item.controlCount}</span>
            </button>
          `;
        }).join("")}
      </div>
    `;
  }

  function renderDocumentViewer() {
    if (!els.documentViewer) {
      return;
    }
    const documentItem = documentsById.get(state.activeDocumentId);
    if (!documentItem) {
      els.documentViewer.innerHTML = '<div class="empty-state">Choose a policy to display its embedded content.</div>';
      return;
    }

    const relatedControls = data.controls
      .filter((control) => control.documentIds.includes(documentItem.id))
      .slice(0, 8)
      .map((control) => `<a class="chip" href="./controls.html?control=${encodeURIComponent(control.id)}">${escapeHtml(control.id)}</a>`)
      .join("");

    els.documentViewer.innerHTML = `
      <div class="document-heading">
        <div>
          <p class="panel-kicker">Mapped document</p>
          <h3>${escapeHtml(documentItem.id)} / ${escapeHtml(documentItem.title)}</h3>
        </div>
        <div class="chip-row">
          <span class="doc-type">${escapeHtml(documentItem.type)}</span>
          <span class="chip">${escapeHtml(documentItem.reviewFrequency)}</span>
          <span class="chip">${escapeHtml(documentItem.owner)}</span>
        </div>
        <p class="doc-purpose">${escapeHtml(documentItem.purpose || "No purpose summary found.")}</p>
        <div class="document-meta">
          <span>Approver: ${escapeHtml(documentItem.approver)}</span>
          <span>Source: ${escapeHtml(documentItem.path)}</span>
        </div>
        <div class="chip-row">${relatedControls}</div>
      </div>
      <div class="content-frame">${documentItem.contentHtml}</div>
    `;
  }

  function renderMonthTabs() {
    if (!els.monthTabs) {
      return;
    }
    els.monthTabs.innerHTML = monthNames.map((month, index) => `
      <button class="month-tab ${index === state.monthIndex ? "is-active" : ""}" type="button" data-month-index="${index}">
        ${escapeHtml(month)}
      </button>
    `).join("");
  }

  function renderActivities() {
    if (!els.activities) {
      return;
    }
    const activities = monthlyActivities(state.monthIndex);
    if (!activities.length) {
      els.activities.innerHTML = `<div class="empty-state">No scheduled activities for ${escapeHtml(monthNames[state.monthIndex])}.</div>`;
      return;
    }

    els.activities.innerHTML = `
      <div class="activity-list">
        ${activities.map((activity) => {
          const isDone = Boolean(state.reviewState.activities[activity.id]);
          return `
            <article class="activity-card ${isDone ? "is-done" : ""}">
              <div class="activity-top">
                <div>
                  <strong>${escapeHtml(activity.activity)}</strong>
                  <div class="mini-copy">${escapeHtml(activity.owner)} / ${escapeHtml(activity.frequency)}</div>
                </div>
                <span class="status-pill ${isDone ? "is-success" : "is-active"}">${isDone ? "Done" : "Open"}</span>
              </div>
              <p class="activity-evidence">Evidence: ${escapeHtml(activity.evidence)}</p>
              <label>
                <input type="checkbox" data-activity-id="${escapeHtml(activity.id)}" ${isDone ? "checked" : ""}>
                Mark this review activity complete
              </label>
            </article>
          `;
        }).join("")}
      </div>
    `;
  }

  function renderChecklist() {
    if (!els.checklist || !els.checklistSummary) {
      return;
    }

    const completedCount = data.checklist.filter((item) => state.reviewState.checklist[item.id]).length;
    const grouped = groupBy(data.checklist, "category");

    els.checklistSummary.innerHTML = [
      `<span class="chip">${completedCount}/${data.checklist.length} complete</span>`,
      ...Object.entries(data.summary.checklistFrequencies).map(([frequency, count]) => `<span class="chip">${escapeHtml(frequency)} / ${count}</span>`),
    ].join("");

    els.checklist.innerHTML = Object.entries(grouped).map(([category, items]) => `
      <section class="checklist-section">
        <h3>${escapeHtml(category)}</h3>
        ${items.map((item) => {
          const isDone = Boolean(state.reviewState.checklist[item.id]);
          return `
            <article class="check-item ${isDone ? "is-done" : ""}">
              <div class="check-top">
                <div>
                  <strong>${escapeHtml(item.item)}</strong>
                  <div class="mini-copy">${escapeHtml(item.frequency)} / ${escapeHtml(item.owner)}</div>
                </div>
                <span class="status-pill ${isDone ? "is-success" : ""}">${isDone ? "Done" : "Track"}</span>
              </div>
              <label>
                <input type="checkbox" data-check-id="${escapeHtml(item.id)}" ${isDone ? "checked" : ""}>
                Mark this checklist item complete
              </label>
            </article>
          `;
        }).join("")}
      </section>
    `).join("");
  }

  function getControlView(controlOrId) {
    const control = typeof controlOrId === "string" ? controlsById.get(controlOrId) : controlOrId;
    if (!control) {
      return null;
    }
    const stored = state.controlState[control.id] || {};
    const baseExcluded = isBaseExcluded(control);
    const localExcluded = Boolean(stored.excluded) && !baseExcluded;
    const effectiveExcluded = baseExcluded || localExcluded;
    return {
      ...control,
      isBaseExcluded: baseExcluded,
      isLocallyExcluded: localExcluded,
      isExcluded: effectiveExcluded,
      effectiveImplementationModel: effectiveExcluded ? "Excluded" : control.implementationModel,
      exclusionReason: localExcluded ? (stored.reason || "") : (baseExcluded ? control.rationale : ""),
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

    if (excluded) {
      const existing = state.controlState[controlId] || {};
      state.controlState[controlId] = {
        excluded: true,
        reason: existing.reason || "",
      };
    } else {
      delete state.controlState[controlId];
    }
    saveControlState();
  }

  function updateControlReason(controlId, reason) {
    const control = controlsById.get(controlId);
    if (!control || isBaseExcluded(control)) {
      return;
    }
    const existing = state.controlState[controlId] || { excluded: true, reason: "" };
    state.controlState[controlId] = {
      excluded: existing.excluded !== false,
      reason,
    };
    saveControlState();
  }

  function filteredControls() {
    const searchLower = state.search.trim().toLowerCase();

    return data.controls.filter((control) => {
      if (page !== "policies" && state.domain !== "All" && control.domain !== state.domain) {
        return false;
      }
      if (page !== "policies" && state.applicability !== "All" && control.applicability !== state.applicability) {
        return false;
      }
      if (page !== "policies" && state.frequency !== "All" && control.reviewFrequency !== state.frequency) {
        return false;
      }
      if (!searchLower || (page !== "controls" && page !== "reports")) {
        return true;
      }

      const searchableText = [
        control.id,
        control.name,
        control.domain,
        control.rationale,
        control.evidence,
        ...control.documentIds.map((documentId) => {
          const documentItem = documentsById.get(documentId);
          return documentItem ? `${documentItem.id} ${documentItem.title}` : documentId;
        }),
      ].join(" ").toLowerCase();

      return searchableText.includes(searchLower);
    });
  }

  function filteredPolicyCoverage() {
    const searchLower = state.search.trim().toLowerCase();
    return data.policyCoverage.filter((item) => {
      if (!searchLower) {
        return true;
      }
      const documentItem = documentsById.get(item.id);
      const text = [
        item.id,
        item.title,
        item.reviewFrequency,
        documentItem ? documentItem.type : "",
      ].join(" ").toLowerCase();
      return text.includes(searchLower);
    });
  }

  function visiblePoliciesForControls(controls) {
    const visibleIds = new Set(controls.flatMap((control) => control.policyDocumentIds));
    return data.policyCoverage.filter((item) => visibleIds.has(item.id));
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

  function initializePolicySelection() {
    const coverageRows = filteredPolicyCoverage();
    const hasSelectedControl = state.selectedControlId && controlsById.has(state.selectedControlId);

    if (hasSelectedControl) {
      const control = controlsById.get(state.selectedControlId);
      if (!state.activeDocumentId || !control.documentIds.includes(state.activeDocumentId)) {
        state.activeDocumentId = control.preferredDocumentId;
      }
      return;
    }

    if (state.activeDocumentId && documentsById.has(state.activeDocumentId)) {
      state.selectedControlId = firstControlIdForDocument(state.activeDocumentId);
      return;
    }

    if (coverageRows.length) {
      state.activeDocumentId = coverageRows[0].id;
      state.selectedControlId = firstControlIdForDocument(state.activeDocumentId);
    }
  }

  function monthlyActivities(monthIndex) {
    return data.activities.filter((activity) => activity.monthIndex === monthIndex);
  }

  function orderedActivitiesFromCurrentMonth() {
    return data.activities
      .slice()
      .sort((left, right) => {
        const deltaLeft = (left.monthIndex - today.getMonth() + 12) % 12;
        const deltaRight = (right.monthIndex - today.getMonth() + 12) % 12;
        if (deltaLeft !== deltaRight) {
          return deltaLeft - deltaRight;
        }
        return left.activity.localeCompare(right.activity);
      });
  }

  function buildAuditWindows() {
    const definitions = [
      {
        label: "Governance",
        color: "#7442b8",
        matchers: ["policy", "objectives", "statement of applicability", "internal audit", "management review", "compliance", "training"],
      },
      {
        label: "Access reviews",
        color: "#4e92e6",
        matchers: ["access", "privileged"],
      },
      {
        label: "Risk and suppliers",
        color: "#d05ad4",
        matchers: ["risk", "supplier", "vulnerability"],
      },
      {
        label: "Resilience",
        color: "#71cadb",
        matchers: ["backup", "restore", "recovery", "continuity", "physical"],
      },
    ];

    return definitions.map((definition) => {
      const matchingActivities = data.activities.filter((activity) => {
        const text = activity.activity.toLowerCase();
        return definition.matchers.some((matcher) => text.includes(matcher));
      });
      if (!matchingActivities.length) {
        return null;
      }
      return {
        label: definition.label,
        color: definition.color,
        start: Math.min(...matchingActivities.map((activity) => activity.monthIndex)),
        end: Math.max(...matchingActivities.map((activity) => activity.monthIndex)),
        count: matchingActivities.length,
      };
    }).filter(Boolean);
  }

  function firstControlIdForDocument(documentId) {
    const match = data.controls.find((control) => control.documentIds.includes(documentId));
    return match ? match.id : "";
  }

  function policyUrl(controlId, documentId) {
    const query = new URLSearchParams();
    if (controlId) {
      query.set("control", controlId);
    }
    if (documentId) {
      query.set("doc", documentId);
    }
    const suffix = query.toString();
    return `./policies.html${suffix ? `?${suffix}` : ""}`;
  }

  function syncUrl() {
    const query = new URLSearchParams();

    if (page === "controls" || page === "reports" || page === "policies") {
      if (state.search) {
        query.set("q", state.search);
      }
    }
    if ((page === "controls" || page === "reports") && state.domain !== "All") {
      query.set("domain", state.domain);
    }
    if ((page === "controls" || page === "reports") && state.applicability !== "All") {
      query.set("applicability", state.applicability);
    }
    if ((page === "controls" || page === "reports") && state.frequency !== "All") {
      query.set("frequency", state.frequency);
    }
    if (page === "controls" && state.selectedControlId) {
      query.set("control", state.selectedControlId);
    }
    if (page === "policies" && state.selectedControlId) {
      query.set("control", state.selectedControlId);
    }
    if (page === "policies" && state.activeDocumentId) {
      query.set("doc", state.activeDocumentId);
    }
    if (page === "reviews" && state.monthIndex !== today.getMonth()) {
      query.set("month", String(state.monthIndex));
    }

    const next = query.toString();
    const url = `${window.location.pathname}${next ? `?${next}` : ""}`;
    window.history.replaceState(null, "", url);
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

  function populateSelect(select, values) {
    select.innerHTML = values.map((value) => `<option value="${escapeHtml(value)}">${escapeHtml(value)}</option>`).join("");
  }

  function valueOrFallback(select, value) {
    const exists = Array.from(select.options).some((option) => option.value === value);
    return exists ? value : select.options[0].value;
  }

  function uniqueValues(items, key) {
    return Array.from(new Set(items.map((item) => item[key]))).sort((left, right) => left.localeCompare(right, undefined, { numeric: true }));
  }

  function parseMonth(rawValue) {
    const parsed = Number(rawValue);
    return Number.isInteger(parsed) && parsed >= 0 && parsed <= 11 ? parsed : today.getMonth();
  }

  function groupBy(items, key) {
    return items.reduce((groups, item) => {
      const group = item[key];
      groups[group] = groups[group] || [];
      groups[group].push(item);
      return groups;
    }, {});
  }

  function loadReviewState() {
    try {
      const saved = JSON.parse(window.localStorage.getItem(storageKey) || "{}");
      return {
        activities: saved.activities || {},
        checklist: saved.checklist || {},
      };
    } catch (error) {
      return { activities: {}, checklist: {} };
    }
  }

  function saveReviewState() {
    window.localStorage.setItem(storageKey, JSON.stringify(state.reviewState));
  }

  function formatDateTime(value) {
    return new Intl.DateTimeFormat(undefined, {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
      timeZoneName: "short",
    }).format(new Date(value));
  }

  function escapeHtml(value) {
    return String(value)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#39;");
  }
})();
