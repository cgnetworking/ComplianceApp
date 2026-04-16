  let zeroTrustProfiles = [];
  let zeroTrustProfileDetail = null;
  let zeroTrustRuns = [];
  let zeroTrustLogs = [];
  let zeroTrustPollTimer = 0;

  function selectedZeroTrustProfile() {
    const profileId = state.selectedAssessmentProfileId;
    if (!profileId) {
      return zeroTrustProfileDetail;
    }
    if (zeroTrustProfileDetail && zeroTrustProfileDetail.id === profileId) {
      return zeroTrustProfileDetail;
    }
    return zeroTrustProfiles.find((profile) => profile.id === profileId) || null;
  }

  function selectedZeroTrustRun() {
    const runId = state.selectedAssessmentRunId;
    if (!runId) {
      return zeroTrustRuns[0] || null;
    }
    return zeroTrustRuns.find((run) => run.id === runId) || null;
  }

  function zeroTrustRunIsActive(run) {
    return Boolean(run && ["queued", "claimed", "running", "ingesting"].includes(run.status));
  }

  function filteredZeroTrustProfiles() {
    const searchLower = state.search.trim().toLowerCase();
    return zeroTrustProfiles.filter((profile) => {
      if (!searchLower) {
        return true;
      }
      const latestRun = profile.latestRun || {};
      const searchText = [
        profile.displayName,
        profile.tenantId,
        profile.clientId,
        profile.certificateThumbprint,
        latestRun.statusLabel,
        latestRun.statusMessage,
      ].join(" ").toLowerCase();
      return searchText.includes(searchLower);
    });
  }

  function syncZeroTrustSelection() {
    const profiles = filteredZeroTrustProfiles();
    if (!profiles.length) {
      state.selectedAssessmentProfileId = "";
      state.selectedAssessmentRunId = "";
      return;
    }

    if (!state.selectedAssessmentProfileId || !profiles.some((profile) => profile.id === state.selectedAssessmentProfileId)) {
      state.selectedAssessmentProfileId = profiles[0].id;
    }
  }

  function handleZeroTrustSelectionChanged() {
    if (!state.selectedAssessmentProfileId) {
      zeroTrustProfileDetail = null;
      zeroTrustRuns = [];
      zeroTrustLogs = [];
      stopZeroTrustPolling();
      renderZeroTrustPage();
      return;
    }
    if (zeroTrustProfileDetail && zeroTrustProfileDetail.id === state.selectedAssessmentProfileId) {
      renderZeroTrustPage();
      return;
    }
    void loadZeroTrustProfileDetail(state.selectedAssessmentProfileId);
  }

  function replaceZeroTrustProfile(profile) {
    if (!profile || !profile.id) {
      return;
    }
    const index = zeroTrustProfiles.findIndex((item) => item.id === profile.id);
    if (index >= 0) {
      zeroTrustProfiles.splice(index, 1, profile);
    } else {
      zeroTrustProfiles.unshift(profile);
    }
  }

  async function loadZeroTrustProfiles() {
    const payload = await apiRequest("/assessments/");
    zeroTrustProfiles = Array.isArray(payload && payload.profiles) ? payload.profiles : [];
  }

  async function loadZeroTrustProfileDetail(profileId, options) {
    const requestOptions = options || {};
    if (!profileId) {
      zeroTrustProfileDetail = null;
      zeroTrustRuns = [];
      zeroTrustLogs = [];
      state.selectedAssessmentRunId = "";
      renderZeroTrustPage();
      stopZeroTrustPolling();
      return;
    }

    const payload = await apiRequest(`/assessments/${encodeURIComponent(profileId)}/`);
    zeroTrustProfileDetail = payload && payload.profile ? payload.profile : null;
    zeroTrustRuns = Array.isArray(payload && payload.runs) ? payload.runs : [];
    replaceZeroTrustProfile(zeroTrustProfileDetail);

    if (!requestOptions.preserveRun || !zeroTrustRuns.some((run) => run.id === state.selectedAssessmentRunId)) {
      state.selectedAssessmentRunId = zeroTrustRuns[0] ? zeroTrustRuns[0].id : "";
    }

    zeroTrustLogs = [];
    if (state.selectedAssessmentRunId) {
      await refreshSelectedZeroTrustRun();
      return;
    }

    renderZeroTrustPage();
    syncZeroTrustPolling();
  }

  async function loadZeroTrustState() {
    await loadZeroTrustProfiles();
    syncZeroTrustSelection();
    if (state.selectedAssessmentProfileId) {
      await loadZeroTrustProfileDetail(state.selectedAssessmentProfileId);
    } else {
      renderZeroTrustPage();
    }
  }

  function renderZeroTrustPage() {
    renderZeroTrustOverview();
    renderZeroTrustProfileList();
    renderZeroTrustDetail();
    renderZeroTrustReport();
  }

  function renderZeroTrustOverview() {
    if (!els.assessmentOverview) {
      return;
    }

    const latestRuns = zeroTrustProfiles.map((profile) => profile.latestRun).filter(Boolean);
    const activeCount = latestRuns.filter((run) => zeroTrustRunIsActive(run)).length;
    const reportCount = latestRuns.filter((run) => run.hasReport).length;
    const recentRun = latestRuns
      .slice()
      .sort((left, right) => new Date(right.createdAt) - new Date(left.createdAt))[0];

    const cards = [
      {
        label: "Saved tenants",
        value: zeroTrustProfiles.length,
        note: zeroTrustProfiles.length ? "Assessment profiles stored in the shared portal database." : "Save tenant settings to stage the first assessment target.",
      },
      {
        label: "Active runs",
        value: activeCount,
        note: activeCount ? "Queued or running assessments currently managed by the worker service." : "No tenant assessments are currently in flight.",
      },
      {
        label: "Reports stored",
        value: reportCount,
        note: reportCount ? "Latest reports already ingested into PostgreSQL and ready for embedded viewing." : "Run an assessment to capture the first stored report bundle.",
      },
      {
        label: "Most recent run",
        value: recentRun ? recentRun.statusLabel : "None",
        note: recentRun ? `${recentRun.profileId || ""} / ${formatShortDateTime(recentRun.createdAt)}` : "No assessment runs have been recorded yet.",
      },
    ];

    els.assessmentOverview.innerHTML = cards.map((card) => `
      <article class="stat-card">
        <span class="stat-label">${escapeHtml(card.label)}</span>
        <p class="stat-value">${escapeHtml(String(card.value))}</p>
        <p class="stat-note">${escapeHtml(card.note)}</p>
      </article>
    `).join("");
  }

  function renderZeroTrustProfileList() {
    if (!els.assessmentProfiles) {
      return;
    }

    const profiles = filteredZeroTrustProfiles();
    if (!profiles.length) {
      els.assessmentProfiles.innerHTML = `
        <div class="empty-state">
          ${state.search ? "No saved tenant profiles match the current search." : "No tenant assessment profiles have been saved yet."}
        </div>
      `;
      return;
    }

    els.assessmentProfiles.innerHTML = `
      <div class="vendor-list">
        ${profiles.map((profile) => {
          const isActive = profile.id === state.selectedAssessmentProfileId;
          const latestRun = profile.latestRun;
          const statusClass = latestRun
            ? (zeroTrustRunIsActive(latestRun) ? "is-active" : latestRun.status === "failed" ? "is-danger" : "is-success")
            : "";
          return `
            <button class="vendor-card ${isActive ? "is-selected" : ""}" type="button" data-assessment-profile="${escapeHtml(profile.id)}">
              <div class="vendor-card-top">
                <div>
                  <strong>${escapeHtml(profile.displayName || profile.tenantId)}</strong>
                  <div class="mini-copy">${escapeHtml(profile.tenantId)}</div>
                </div>
                <span class="status-pill ${statusClass}">${escapeHtml(latestRun ? latestRun.statusLabel : "Not run")}</span>
              </div>
              <div class="vendor-meta-row">
                <span class="chip">${escapeHtml(profile.clientId)}</span>
                <span class="chip">${escapeHtml(profile.certificateThumbprint || "No cert")}</span>
              </div>
              <p class="mini-copy">${escapeHtml(latestRun ? latestRun.statusMessage || "Latest stored run." : "Save settings and create a certificate to prepare this tenant.")}</p>
            </button>
          `;
        }).join("")}
      </div>
    `;
  }

  function renderZeroTrustDetail() {
    if (!els.assessmentDetail) {
      return;
    }

    const profile = selectedZeroTrustProfile();
    const activeRun = selectedZeroTrustRun();
    const certificate = profile && profile.currentCertificate ? profile.currentCertificate : null;
    const profileId = profile ? profile.id : "";
    const hasCertificate = Boolean(certificate && certificate.thumbprint);
    const runRows = zeroTrustRuns.length
      ? zeroTrustRuns.map((run) => {
          const isSelected = run.id === state.selectedAssessmentRunId;
          const statusClass = zeroTrustRunIsActive(run)
            ? "is-active"
            : run.status === "failed"
              ? "is-danger"
              : "is-success";
          return `
            <tr class="${isSelected ? "is-selected-row" : ""}">
              <td>
                <button class="table-link-button" type="button" data-assessment-run-select="${escapeHtml(run.id)}">${escapeHtml(run.statusLabel)}</button>
              </td>
              <td>${escapeHtml(formatShortDateTime(run.startedAt || run.createdAt))}</td>
              <td>${escapeHtml(run.completedAt ? formatShortDateTime(run.completedAt) : "In progress")}</td>
              <td><span class="status-pill ${statusClass}">${escapeHtml(run.statusLabel)}</span></td>
              <td>${escapeHtml(run.hasReport ? "Stored" : "Pending")}</td>
            </tr>
          `;
        }).join("")
      : '<tr><td colspan="5" class="empty-cell">No assessment runs have been recorded for this tenant.</td></tr>';

    els.assessmentDetail.innerHTML = `
      <article class="detail-panel">
        <div class="detail-header">
          <div>
            <p class="panel-kicker">Tenant configuration</p>
            <h3>${escapeHtml(profile ? (profile.displayName || profile.tenantId) : "Create a tenant assessment profile")}</h3>
          </div>
          <div class="chip-row">
            ${profile ? `<span class="chip">${escapeHtml(profile.tenantId)}</span>` : ""}
            ${profile && profile.latestRun ? `<span class="status-pill ${zeroTrustRunIsActive(profile.latestRun) ? "is-active" : profile.latestRun.status === "failed" ? "is-danger" : "is-success"}">${escapeHtml(profile.latestRun.statusLabel)}</span>` : ""}
          </div>
          <p class="detail-subline">
            Store app-only Graph settings for a tenant, issue a certificate from the Ubuntu server, and launch a background Zero Trust Assessment run when the profile is ready.
          </p>
        </div>

        <div class="form-grid">
          <label class="form-field">
            <span>Display Name</span>
            <input id="assessment-display-name" type="text" value="${escapeHtml(profile ? profile.displayName || "" : "")}" placeholder="Friendly tenant label">
          </label>
          <label class="form-field">
            <span>TenantId</span>
            <input id="assessment-tenant-id" type="text" value="${escapeHtml(profile ? profile.tenantId || "" : "")}" placeholder="YOUR_TENANT_ID">
          </label>
          <label class="form-field">
            <span>ClientId</span>
            <input id="assessment-client-id" type="text" value="${escapeHtml(profile ? profile.clientId || "" : "")}" placeholder="YOUR_APP_ID">
          </label>
          <label class="form-field">
            <span>CertificateThumbprint</span>
            <input id="assessment-thumbprint" type="text" value="${escapeHtml(profile ? profile.certificateThumbprint || "" : "")}" placeholder="Generated thumbprint" readonly>
          </label>
        </div>

        <div class="detail-grid">
          <div class="detail-card">
            <strong>Certificate</strong>
            <div class="mini-copy">${escapeHtml(hasCertificate ? `${certificate.subject} / expires ${formatDateWithOrdinal(certificate.notAfter)}` : "No server-side certificate has been generated for this tenant yet.")}</div>
          </div>
          <div class="detail-card">
            <strong>Report storage</strong>
            <div class="mini-copy">${escapeHtml(activeRun && activeRun.hasReport ? "The selected run has a PostgreSQL-backed embedded report bundle." : "Reports are copied into PostgreSQL after ingestion and removed from the staging folder.")}</div>
          </div>
          <div class="detail-card">
            <strong>Current thumbprint</strong>
            <div class="mini-copy">${escapeHtml(profile && profile.certificateThumbprint ? profile.certificateThumbprint : "Generate a certificate to prefill the thumbprint.")}</div>
          </div>
          <div class="detail-card">
            <strong>Latest run</strong>
            <div class="mini-copy">${escapeHtml(profile && profile.latestRun ? `${profile.latestRun.statusLabel} / ${formatShortDateTime(profile.latestRun.createdAt)}` : "No run has been queued for this tenant yet.")}</div>
          </div>
        </div>

        <div class="button-row button-row-wrap">
          <button class="primary-button" type="button" data-assessment-save-profile="${escapeHtml(profileId)}">Save Settings</button>
          <button class="ghost-button" type="button" data-assessment-create-certificate="${escapeHtml(profileId)}"${profile ? "" : " disabled"}>Create Certificate</button>
          <a class="ghost-button${hasCertificate ? "" : " is-disabled"}" ${hasCertificate ? `href="/api/assessments/${encodeURIComponent(profileId)}/certificate.cer"` : 'aria-disabled="true"'}>Download .cer</a>
          <button class="ghost-button" type="button" data-assessment-run-start="${escapeHtml(profileId)}"${hasCertificate ? "" : " disabled"}>Run Assessment</button>
          <button class="ghost-button" type="button" data-assessment-delete-profile="${escapeHtml(profileId)}"${profile ? "" : " disabled"}>Delete Tenant</button>
        </div>

        <div class="doc-section">
          <strong>Run history</strong>
          <div class="table-shell">
            <table class="assessment-table">
              <thead>
                <tr>
                  <th>Open</th>
                  <th>Started</th>
                  <th>Completed</th>
                  <th>Status</th>
                  <th>Report</th>
                </tr>
              </thead>
              <tbody>${runRows}</tbody>
            </table>
          </div>
        </div>

        <div class="doc-section">
          <strong>Selected run logs</strong>
          <div class="preview-block assessment-log-block">
            ${zeroTrustLogs.length
              ? `<pre class="response-preview">${escapeHtml(zeroTrustLogs.map((entry) => `[${entry.level.toUpperCase()}] ${entry.message}`).join("\n"))}</pre>`
              : '<div class="empty-state">Select or start a run to view worker and PowerShell output.</div>'}
          </div>
        </div>
      </article>
    `;
  }

  function renderZeroTrustReport() {
    if (!els.assessmentReport) {
      return;
    }

    const run = selectedZeroTrustRun();
    if (!run) {
      els.assessmentReport.innerHTML = `
        <div class="detail-stack">
          <div class="detail-header">
            <div>
              <p class="panel-kicker">Embedded report</p>
              <h3>Stored report viewer</h3>
            </div>
            <p class="detail-subline">
              The selected assessment report opens here after the worker stores its HTML bundle in PostgreSQL.
            </p>
          </div>
        </div>
      `;
      return;
    }

    if (!run.reportUrl) {
      els.assessmentReport.innerHTML = `
        <div class="detail-stack">
          <div class="detail-header">
            <div>
              <p class="panel-kicker">Embedded report</p>
              <h3>${escapeHtml(run.statusLabel)}</h3>
            </div>
            <p class="detail-subline">${escapeHtml(run.statusMessage || "The selected run does not have a stored report bundle yet.")}</p>
          </div>
        </div>
      `;
      return;
    }

    els.assessmentReport.innerHTML = `
      <div class="detail-header">
        <div>
          <p class="panel-kicker">Embedded report</p>
          <h3>Run ${escapeHtml(run.id)}</h3>
        </div>
        <div class="chip-row">
          <span class="status-pill ${zeroTrustRunIsActive(run) ? "is-active" : run.status === "failed" ? "is-danger" : "is-success"}">${escapeHtml(run.statusLabel)}</span>
          <a class="ghost-button" href="${escapeHtml(run.reportUrl)}" target="_blank" rel="noopener">Open Full Report</a>
        </div>
      </div>
      <iframe class="assessment-report-frame" src="${escapeHtml(run.reportUrl)}" title="Zero Trust Assessment report"></iframe>
    `;
  }

  function collectZeroTrustProfileForm() {
    return {
      id: state.selectedAssessmentProfileId,
      displayName: document.getElementById("assessment-display-name") ? document.getElementById("assessment-display-name").value.trim() : "",
      tenantId: document.getElementById("assessment-tenant-id") ? document.getElementById("assessment-tenant-id").value.trim() : "",
      clientId: document.getElementById("assessment-client-id") ? document.getElementById("assessment-client-id").value.trim() : "",
      certificateThumbprint: document.getElementById("assessment-thumbprint") ? document.getElementById("assessment-thumbprint").value.trim() : "",
    };
  }

  async function handleZeroTrustProfileSave() {
    setUploadStatus(els.assessmentStatus, "Saving tenant assessment settings...", "info");
    try {
      const payload = await apiRequest("/assessments/", {
        method: "POST",
        body: JSON.stringify({ profile: collectZeroTrustProfileForm() }),
      });
      replaceZeroTrustProfile(payload.profile);
      state.selectedAssessmentProfileId = payload.profile.id;
      await loadZeroTrustProfileDetail(payload.profile.id);
      syncUrl();
      setUploadStatus(els.assessmentStatus, "Tenant assessment settings saved to the shared database.", "success");
    } catch (error) {
      setUploadStatus(els.assessmentStatus, error instanceof Error ? error.message : "Unable to save the tenant profile.", "error");
    }
  }

  async function handleZeroTrustCertificateCreate(profileId) {
    if (!profileId) {
      setUploadStatus(els.assessmentStatus, "Save the tenant settings before generating a certificate.", "error");
      return;
    }
    setUploadStatus(els.assessmentStatus, "Generating a certificate on the Ubuntu server...", "info");
    try {
      const payload = await apiRequest(`/assessments/${encodeURIComponent(profileId)}/certificate/`, {
        method: "POST",
      });
      replaceZeroTrustProfile(payload.profile);
      await loadZeroTrustProfileDetail(profileId, { preserveRun: true });
      setUploadStatus(els.assessmentStatus, "Certificate created. Download the .cer file and upload it to the Entra app registration before running the assessment.", "success");
    } catch (error) {
      setUploadStatus(els.assessmentStatus, error instanceof Error ? error.message : "Unable to generate the certificate.", "error");
    }
  }

  async function handleZeroTrustRunStart(profileId) {
    if (!profileId) {
      setUploadStatus(els.assessmentStatus, "Select or save a tenant profile before starting a run.", "error");
      return;
    }
    setUploadStatus(els.assessmentStatus, "Queueing a background Zero Trust Assessment run...", "info");
    try {
      const payload = await apiRequest(`/assessments/${encodeURIComponent(profileId)}/runs/`, {
        method: "POST",
      });
      state.selectedAssessmentRunId = payload.run.id;
      await loadZeroTrustProfileDetail(profileId, { preserveRun: true });
      setUploadStatus(els.assessmentStatus, "Assessment run queued for the Ubuntu worker service.", "success");
    } catch (error) {
      setUploadStatus(els.assessmentStatus, error instanceof Error ? error.message : "Unable to queue the assessment run.", "error");
    }
  }

  async function handleZeroTrustProfileDelete(profileId) {
    if (!profileId) {
      setUploadStatus(els.assessmentStatus, "Select a saved tenant profile before deleting it.", "error");
      return;
    }
    const profile = zeroTrustProfiles.find((item) => item.id === profileId) || zeroTrustProfileDetail;
    const label = profile ? (profile.displayName || profile.tenantId) : "this tenant";
    if (!window.confirm(`Delete ${label} and all stored assessment history for it? This cannot be undone.`)) {
      return;
    }

    setUploadStatus(els.assessmentStatus, "Deleting the saved tenant profile...", "info");
    try {
      await apiRequest(`/assessments/${encodeURIComponent(profileId)}/`, {
        method: "DELETE",
      });
      stopZeroTrustPolling();
      zeroTrustProfiles = zeroTrustProfiles.filter((item) => item.id !== profileId);
      zeroTrustProfileDetail = null;
      zeroTrustRuns = [];
      zeroTrustLogs = [];
      state.selectedAssessmentProfileId = "";
      state.selectedAssessmentRunId = "";
      syncZeroTrustSelection();
      syncUrl();
      if (state.selectedAssessmentProfileId) {
        await loadZeroTrustProfileDetail(state.selectedAssessmentProfileId);
      } else {
        renderZeroTrustPage();
      }
      setUploadStatus(els.assessmentStatus, "Tenant profile and stored assessment history deleted.", "success");
    } catch (error) {
      setUploadStatus(els.assessmentStatus, error instanceof Error ? error.message : "Unable to delete the tenant profile.", "error");
    }
  }

  async function refreshSelectedZeroTrustRun() {
    const run = selectedZeroTrustRun();
    if (!run) {
      stopZeroTrustPolling();
      return;
    }

    try {
      const payload = await apiRequest(`/assessments/runs/${encodeURIComponent(run.id)}/`);
      const refreshedRun = payload && payload.run ? payload.run : null;
      zeroTrustLogs = Array.isArray(payload && payload.logs) ? payload.logs : [];
      if (refreshedRun) {
        zeroTrustRuns = zeroTrustRuns.map((item) => (item.id === refreshedRun.id ? refreshedRun : item));
        const profile = selectedZeroTrustProfile();
        if (profile && zeroTrustProfileDetail) {
          zeroTrustProfileDetail.latestRun = refreshedRun;
          replaceZeroTrustProfile(zeroTrustProfileDetail);
        }
      }
      renderZeroTrustPage();
      if (!zeroTrustRunIsActive(refreshedRun)) {
        stopZeroTrustPolling();
        await loadZeroTrustProfiles();
        replaceZeroTrustProfile(zeroTrustProfileDetail);
        renderZeroTrustPage();
      }
    } catch (error) {
      stopZeroTrustPolling();
      setUploadStatus(els.assessmentStatus, error instanceof Error ? error.message : "Unable to refresh the selected run.", "error");
    }
  }

  function stopZeroTrustPolling() {
    if (zeroTrustPollTimer) {
      window.clearInterval(zeroTrustPollTimer);
      zeroTrustPollTimer = 0;
    }
  }

  function syncZeroTrustPolling() {
    stopZeroTrustPolling();
    const run = selectedZeroTrustRun();
    if (!zeroTrustRunIsActive(run)) {
      return;
    }

    zeroTrustPollTimer = window.setInterval(() => {
      void refreshSelectedZeroTrustRun();
    }, 5000);
  }

  function bindZeroTrustEvents() {
    if (els.assessmentNewProfile) {
      els.assessmentNewProfile.addEventListener("click", () => {
        stopZeroTrustPolling();
        state.selectedAssessmentProfileId = "";
        state.selectedAssessmentRunId = "";
        zeroTrustProfileDetail = null;
        zeroTrustRuns = [];
        zeroTrustLogs = [];
        syncUrlAndRender(renderZeroTrustPage);
      });
    }

    if (els.assessmentProfiles) {
      els.assessmentProfiles.addEventListener("click", (event) => {
        const target = event.target.closest("[data-assessment-profile]");
        if (!target) {
          return;
        }
        state.selectedAssessmentProfileId = target.dataset.assessmentProfile || "";
        state.selectedAssessmentRunId = "";
        syncUrl();
        void loadZeroTrustProfileDetail(state.selectedAssessmentProfileId);
      });
    }

    if (els.assessmentDetail) {
      els.assessmentDetail.addEventListener("click", (event) => {
        const saveProfile = event.target.closest("[data-assessment-save-profile]");
        if (saveProfile) {
          void handleZeroTrustProfileSave();
          return;
        }

        const createCertificate = event.target.closest("[data-assessment-create-certificate]");
        if (createCertificate) {
          void handleZeroTrustCertificateCreate(createCertificate.dataset.assessmentCreateCertificate || "");
          return;
        }

        const startRun = event.target.closest("[data-assessment-run-start]");
        if (startRun) {
          void handleZeroTrustRunStart(startRun.dataset.assessmentRunStart || "");
          return;
        }

        const deleteProfile = event.target.closest("[data-assessment-delete-profile]");
        if (deleteProfile) {
          void handleZeroTrustProfileDelete(deleteProfile.dataset.assessmentDeleteProfile || "");
          return;
        }

        const selectRun = event.target.closest("[data-assessment-run-select]");
        if (selectRun && selectRun.dataset.assessmentRunSelect) {
          state.selectedAssessmentRunId = selectRun.dataset.assessmentRunSelect;
          syncUrlAndRender(renderZeroTrustPage);
          void refreshSelectedZeroTrustRun();
          return;
        }
      });
    }
  }
