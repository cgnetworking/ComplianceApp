  const zeroTrustViewState = {
    activeTab: "prerequisites",
    hasBoundEvents: false,
    hasLoaded: false,
    isLoading: false,
    pollTimer: 0,
    reportToken: "",
    actionMessage: "",
    actionTone: "info",
  };

  function defaultZeroTrustAssessmentState() {
    return {
      ubuntuOnly: true,
      platform: {
        supported: false,
        system: "",
        distribution: "",
        version: "",
        reason: "",
      },
      prerequisites: {
        powerShell: {
          installed: false,
          version: "",
        },
        zeroTrustModule: {
          installed: false,
          version: "",
        },
      },
      authentication: {
        mode: "delegated",
        useDeviceCode: false,
        appOnly: {
          tenantId: "",
          clientId: "",
          certificateReference: "",
          generatedCertificate: {
            available: false,
            subject: "",
            thumbprint: "",
            publicKeyPath: "",
            generatedAt: "",
            expiresAt: "",
            downloadName: "ZeroTrustAssessmentPublicKey.cer",
          },
        },
        ready: true,
        statusMessage: "",
      },
      run: {
        status: "not_started",
        message: "Run the assessment to generate your first report.",
        runId: "",
        trigger: "",
        startedAt: "",
        finishedAt: "",
        runDirectory: "",
        logPath: "",
      },
      schedule: {
        intervalDays: 7,
        autoRunEnabled: true,
        firstRunAt: "",
        lastRunAt: "",
        lastSuccessfulRunAt: "",
        nextRunAt: "",
      },
      latestResult: {
        runId: "",
        status: "",
        message: "",
        reportPath: "",
        reportSizeBytes: 0,
        reportGeneratedAt: "",
        logPath: "",
        returnCode: null,
        summary: {},
      },
      history: [],
      docs: {
        zeroTrust: "",
        powerShellUbuntu: "",
        graphAppOnlyAuth: "",
      },
      installInstructions: {
        ubuntuPowerShell: {
          source: "",
          commands: [],
        },
        zeroTrustAssessment: {
          source: "",
          commands: [],
        },
        graphAppOnlyAuth: {
          source: "",
          commands: [],
        },
      },
      entraSetupDirections: [],
      updatedAt: "",
    };
  }

  function normalizeZeroTrustAssessmentPayload(payload) {
    const defaults = defaultZeroTrustAssessmentState();
    const value = payload && typeof payload === "object" ? payload : {};

    const run = value.run && typeof value.run === "object" ? value.run : {};
    const schedule = value.schedule && typeof value.schedule === "object" ? value.schedule : {};
    const latestResult = value.latestResult && typeof value.latestResult === "object" ? value.latestResult : {};
    const platformPayload = value.platform && typeof value.platform === "object" ? value.platform : {};
    const prerequisites = value.prerequisites && typeof value.prerequisites === "object" ? value.prerequisites : {};
    const authentication = value.authentication && typeof value.authentication === "object"
      ? value.authentication
      : {};
    const appOnly = authentication.appOnly && typeof authentication.appOnly === "object"
      ? authentication.appOnly
      : {};
    const generatedCertificate = appOnly.generatedCertificate && typeof appOnly.generatedCertificate === "object"
      ? appOnly.generatedCertificate
      : {};
    const powerShell = prerequisites.powerShell && typeof prerequisites.powerShell === "object"
      ? prerequisites.powerShell
      : {};
    const zeroTrustModule = prerequisites.zeroTrustModule && typeof prerequisites.zeroTrustModule === "object"
      ? prerequisites.zeroTrustModule
      : {};

    const history = Array.isArray(value.history)
      ? value.history
          .filter((item) => item && typeof item === "object")
          .map((item) => ({
            runId: typeof item.runId === "string" ? item.runId : "",
            status: typeof item.status === "string" ? item.status : "failed",
            message: typeof item.message === "string" ? item.message : "",
            trigger: typeof item.trigger === "string" ? item.trigger : "",
            startedAt: typeof item.startedAt === "string" ? item.startedAt : "",
            finishedAt: typeof item.finishedAt === "string" ? item.finishedAt : "",
            runDirectory: typeof item.runDirectory === "string" ? item.runDirectory : "",
            reportPath: typeof item.reportPath === "string" ? item.reportPath : "",
            reportSizeBytes: Number(item.reportSizeBytes) || 0,
            reportGeneratedAt: typeof item.reportGeneratedAt === "string" ? item.reportGeneratedAt : "",
            logPath: typeof item.logPath === "string" ? item.logPath : "",
            returnCode: Number.isInteger(item.returnCode) ? item.returnCode : null,
            summary: item.summary && typeof item.summary === "object" ? item.summary : {},
          }))
      : [];

    return {
      ubuntuOnly: Boolean(value.ubuntuOnly),
      platform: {
        supported: Boolean(platformPayload.supported),
        system: typeof platformPayload.system === "string" ? platformPayload.system : "",
        distribution: typeof platformPayload.distribution === "string" ? platformPayload.distribution : "",
        version: typeof platformPayload.version === "string" ? platformPayload.version : "",
        reason: typeof platformPayload.reason === "string" ? platformPayload.reason : "",
      },
      prerequisites: {
        powerShell: {
          installed: Boolean(powerShell.installed),
          version: typeof powerShell.version === "string" ? powerShell.version : "",
        },
        zeroTrustModule: {
          installed: Boolean(zeroTrustModule.installed),
          version: typeof zeroTrustModule.version === "string" ? zeroTrustModule.version : "",
        },
      },
      authentication: {
        mode: typeof authentication.mode === "string" ? authentication.mode : "delegated",
        useDeviceCode: Boolean(authentication.useDeviceCode),
        appOnly: {
          tenantId: typeof appOnly.tenantId === "string" ? appOnly.tenantId : "",
          clientId: typeof appOnly.clientId === "string" ? appOnly.clientId : "",
          certificateReference: typeof appOnly.certificateReference === "string" ? appOnly.certificateReference : "",
          generatedCertificate: {
            available: Boolean(generatedCertificate.available),
            subject: typeof generatedCertificate.subject === "string" ? generatedCertificate.subject : "",
            thumbprint: typeof generatedCertificate.thumbprint === "string" ? generatedCertificate.thumbprint : "",
            publicKeyPath: typeof generatedCertificate.publicKeyPath === "string" ? generatedCertificate.publicKeyPath : "",
            generatedAt: typeof generatedCertificate.generatedAt === "string" ? generatedCertificate.generatedAt : "",
            expiresAt: typeof generatedCertificate.expiresAt === "string" ? generatedCertificate.expiresAt : "",
            downloadName: typeof generatedCertificate.downloadName === "string" && generatedCertificate.downloadName.trim()
              ? generatedCertificate.downloadName.trim()
              : "ZeroTrustAssessmentPublicKey.cer",
          },
        },
        ready: typeof authentication.ready === "boolean" ? authentication.ready : true,
        statusMessage: typeof authentication.statusMessage === "string" ? authentication.statusMessage : "",
      },
      run: {
        status: typeof run.status === "string" ? run.status : defaults.run.status,
        message: typeof run.message === "string" ? run.message : defaults.run.message,
        runId: typeof run.runId === "string" ? run.runId : "",
        trigger: typeof run.trigger === "string" ? run.trigger : "",
        startedAt: typeof run.startedAt === "string" ? run.startedAt : "",
        finishedAt: typeof run.finishedAt === "string" ? run.finishedAt : "",
        runDirectory: typeof run.runDirectory === "string" ? run.runDirectory : "",
        logPath: typeof run.logPath === "string" ? run.logPath : "",
      },
      schedule: {
        intervalDays: Math.max(1, Number(schedule.intervalDays) || defaults.schedule.intervalDays),
        autoRunEnabled: typeof schedule.autoRunEnabled === "boolean"
          ? schedule.autoRunEnabled
          : defaults.schedule.autoRunEnabled,
        firstRunAt: typeof schedule.firstRunAt === "string" ? schedule.firstRunAt : "",
        lastRunAt: typeof schedule.lastRunAt === "string" ? schedule.lastRunAt : "",
        lastSuccessfulRunAt: typeof schedule.lastSuccessfulRunAt === "string" ? schedule.lastSuccessfulRunAt : "",
        nextRunAt: typeof schedule.nextRunAt === "string" ? schedule.nextRunAt : "",
      },
      latestResult: {
        runId: typeof latestResult.runId === "string" ? latestResult.runId : "",
        status: typeof latestResult.status === "string" ? latestResult.status : "",
        message: typeof latestResult.message === "string" ? latestResult.message : "",
        reportPath: typeof latestResult.reportPath === "string" ? latestResult.reportPath : "",
        reportSizeBytes: Number(latestResult.reportSizeBytes) || 0,
        reportGeneratedAt: typeof latestResult.reportGeneratedAt === "string" ? latestResult.reportGeneratedAt : "",
        logPath: typeof latestResult.logPath === "string" ? latestResult.logPath : "",
        returnCode: Number.isInteger(latestResult.returnCode) ? latestResult.returnCode : null,
        summary: latestResult.summary && typeof latestResult.summary === "object" ? latestResult.summary : {},
      },
      history,
      docs: value.docs && typeof value.docs === "object" ? value.docs : defaults.docs,
      installInstructions:
        value.installInstructions && typeof value.installInstructions === "object"
          ? value.installInstructions
          : defaults.installInstructions,
      entraSetupDirections: Array.isArray(value.entraSetupDirections) ? value.entraSetupDirections : [],
      updatedAt: typeof value.updatedAt === "string" ? value.updatedAt : "",
    };
  }

  function getZeroTrustAssessmentState() {
    if (!state.zeroTrustAssessment || typeof state.zeroTrustAssessment !== "object") {
      state.zeroTrustAssessment = defaultZeroTrustAssessmentState();
    }
    return state.zeroTrustAssessment;
  }

  function setZeroTrustAssessmentState(payload) {
    state.zeroTrustAssessment = normalizeZeroTrustAssessmentPayload(payload);
    return state.zeroTrustAssessment;
  }

  function zeroTrustStatusLabel(status) {
    switch (String(status || "").trim().toLowerCase()) {
      case "running":
        return "Running";
      case "succeeded":
        return "Succeeded";
      case "failed":
        return "Failed";
      case "unsupported":
        return "Unsupported";
      case "not_started":
      default:
        return "Not started";
    }
  }

  function zeroTrustStatusClass(status) {
    switch (String(status || "").trim().toLowerCase()) {
      case "succeeded":
        return "is-success";
      case "failed":
        return "is-closed";
      default:
        return "is-active";
    }
  }

  function zeroTrustAuthModeLabel(mode) {
    return String(mode || "").trim().toLowerCase() === "app_only"
      ? "App-only"
      : "Delegated";
  }

  function formatZeroTrustDate(value) {
    if (!value) {
      return "Not set";
    }
    if (typeof formatDateTime === "function") {
      return formatDateTime(value);
    }
    return String(value);
  }

  function formatZeroTrustFileSize(value) {
    const size = Number(value) || 0;
    if (!size) {
      return "0 B";
    }
    if (size < 1024) {
      return `${size} B`;
    }
    if (size < 1024 * 1024) {
      return `${(size / 1024).toFixed(1)} KB`;
    }
    return `${(size / (1024 * 1024)).toFixed(1)} MB`;
  }

  function clearZeroTrustPolling() {
    if (!zeroTrustViewState.pollTimer) {
      return;
    }
    window.clearTimeout(zeroTrustViewState.pollTimer);
    zeroTrustViewState.pollTimer = 0;
  }

  function scheduleZeroTrustPolling(delayMs = 15000) {
    clearZeroTrustPolling();
    zeroTrustViewState.pollTimer = window.setTimeout(() => {
      void refreshZeroTrustAssessmentStatus(true);
    }, delayMs);
  }

  function updateZeroTrustTabState() {
    const tabButtons = Array.from(document.querySelectorAll("[data-zero-trust-tab]"));
    const tabPanels = Array.from(document.querySelectorAll("[data-zero-trust-panel]"));

    tabButtons.forEach((button) => {
      const tabKey = button.dataset.zeroTrustTab;
      const isActive = tabKey === zeroTrustViewState.activeTab;
      button.classList.toggle("is-active", isActive);
    });

    tabPanels.forEach((panel) => {
      const tabKey = panel.dataset.zeroTrustPanel;
      panel.hidden = tabKey !== zeroTrustViewState.activeTab;
    });
  }

  function renderZeroTrustOverviewCards(assessment) {
    const overview = document.getElementById("zero-trust-overview");
    if (!overview) {
      return;
    }

    const platform = assessment.platform || {};
    const prerequisites = assessment.prerequisites || {};
    const authentication = assessment.authentication || {};
    const powerShell = prerequisites.powerShell || {};
    const run = assessment.run || {};
    const schedule = assessment.schedule || {};

    const cards = [
      {
        label: "Platform",
        value: platform.supported ? "Ubuntu ready" : "Unsupported",
        note: platform.supported
          ? `${platform.distribution || "Ubuntu"}${platform.version ? ` ${platform.version}` : ""}`
          : (platform.reason || "Ubuntu is required for this assessment workflow."),
      },
      {
        label: "PowerShell 7",
        value: powerShell.installed ? `Installed (${powerShell.version || "version unknown"})` : "Not installed",
        note: powerShell.installed
          ? "Ubuntu prerequisites are available."
          : "Install PowerShell 7 from Microsoft's Ubuntu package repository.",
      },
      {
        label: "Authentication",
        value: zeroTrustAuthModeLabel(authentication.mode),
        note: authentication.statusMessage || "Authentication settings are not available.",
      },
      {
        label: "Next scheduled run",
        value: schedule.nextRunAt ? formatZeroTrustDate(schedule.nextRunAt) : "After first run",
        note: `Run status: ${zeroTrustStatusLabel(run.status)}.`,
      },
    ];

    overview.innerHTML = cards.map((card) => `
      <article class="stat-card">
        <span class="stat-label">${escapeHtml(card.label)}</span>
        <p class="stat-value">${escapeHtml(String(card.value))}</p>
        <p class="stat-note">${escapeHtml(card.note)}</p>
      </article>
    `).join("");
  }

  function renderZeroTrustPrerequisites(assessment) {
    const platformStatus = document.getElementById("zero-trust-platform-status");
    const pwshStatus = document.getElementById("zero-trust-pwsh-status");
    const moduleStatus = document.getElementById("zero-trust-module-status");
    const health = document.getElementById("zero-trust-prereq-health");
    const entraDirections = document.getElementById("zero-trust-entra-directions");

    const platformInfo = assessment.platform || {};
    const prerequisites = assessment.prerequisites || {};
    const powerShell = prerequisites.powerShell || {};
    const moduleState = prerequisites.zeroTrustModule || {};

    if (platformStatus) {
      platformStatus.textContent = platformInfo.supported
        ? `Supported: ${platformInfo.distribution || "Ubuntu"}${platformInfo.version ? ` ${platformInfo.version}` : ""}.`
        : (platformInfo.reason || "Ubuntu is required.");
    }

    if (pwshStatus) {
      pwshStatus.textContent = powerShell.installed
        ? `Installed (${powerShell.version || "version unknown"}).`
        : "Not installed. Use the Ubuntu prerequisites commands above.";
    }

    if (moduleStatus) {
      moduleStatus.textContent = moduleState.installed
        ? `Installed (${moduleState.version || "version unknown"}).`
        : "Not installed. Run Install-Module ZeroTrustAssessment -Scope CurrentUser in PowerShell 7.";
    }

    if (health) {
      const chips = [
        `<span class="chip">Platform / ${escapeHtml(platformInfo.supported ? "Ready" : "Not ready")}</span>`,
        `<span class="chip">PowerShell / ${escapeHtml(powerShell.installed ? "Installed" : "Missing")}</span>`,
        `<span class="chip">Module / ${escapeHtml(moduleState.installed ? "Installed" : "Missing")}</span>`,
      ];
      health.innerHTML = chips.join("");
    }

    if (entraDirections) {
      const steps = Array.isArray(assessment.entraSetupDirections) ? assessment.entraSetupDirections : [];
      if (!steps.length) {
        entraDirections.innerHTML = "<div class=\"empty-state\">No Entra setup directions are available.</div>";
      } else {
        entraDirections.innerHTML = `
          <ol class="zero-trust-directions">
            ${steps.map((step) => {
              const title = step && typeof step.title === "string" ? step.title : "Step";
              const details = Array.isArray(step && step.details) ? step.details : [];
              const referenceUrl = step && typeof step.referenceUrl === "string" ? step.referenceUrl.trim() : "";
              const referenceLabel = step && typeof step.referenceLabel === "string"
                ? step.referenceLabel.trim()
                : "";
              const permissions = Array.isArray(step && step.permissions) ? step.permissions : [];
              return `
                <li>
                  <strong>${escapeHtml(title)}</strong>
                  ${referenceUrl
                    ? `<p class="mini-copy"><a class="zero-trust-doc-link" href="${escapeHtml(referenceUrl)}" target="_blank" rel="noopener noreferrer">${escapeHtml(referenceLabel || referenceUrl)}</a></p>`
                    : ""}
                  ${details.length
                    ? `<ul>${details.map((detail) => `<li>${escapeHtml(String(detail))}</li>`).join("")}</ul>`
                    : ""}
                  ${permissions.length
                    ? `<ul class="zero-trust-permission-list">${permissions.map((permission) => `<li>${escapeHtml(String(permission))}</li>`).join("")}</ul>`
                    : ""}
                </li>
              `;
            }).join("")}
          </ol>
        `;
      }
    }

    renderZeroTrustCertificateControls(assessment);
  }

  function renderZeroTrustCertificateControls(assessment) {
    const authentication = assessment.authentication || {};
    const appOnly = authentication.appOnly || {};
    const generatedCertificate = appOnly.generatedCertificate || {};
    const generateButton = document.getElementById("zero-trust-certificate-generate");
    const downloadLink = document.getElementById("zero-trust-certificate-download");
    const status = document.getElementById("zero-trust-certificate-status");
    const metadata = document.getElementById("zero-trust-certificate-meta");

    const hasDownload = Boolean(generatedCertificate.available && generatedCertificate.publicKeyPath);
    const subject = typeof generatedCertificate.subject === "string" ? generatedCertificate.subject : "";
    const thumbprint = typeof generatedCertificate.thumbprint === "string" ? generatedCertificate.thumbprint : "";
    const expiresAt = typeof generatedCertificate.expiresAt === "string" ? generatedCertificate.expiresAt : "";
    const generatedAt = typeof generatedCertificate.generatedAt === "string" ? generatedCertificate.generatedAt : "";
    const downloadName = typeof generatedCertificate.downloadName === "string" && generatedCertificate.downloadName.trim()
      ? generatedCertificate.downloadName.trim()
      : "ZeroTrustAssessmentPublicKey.cer";

    if (generateButton) {
      generateButton.disabled = zeroTrustViewState.isLoading;
    }

    if (downloadLink) {
      if (hasDownload) {
        downloadLink.href = `${apiBaseUrl}/zero-trust/certificate/public-key/?_=${encodeURIComponent(thumbprint || generatedAt || "1")}`;
        downloadLink.setAttribute("download", downloadName);
        downloadLink.setAttribute("aria-disabled", "false");
        downloadLink.classList.remove("is-disabled");
      } else {
        downloadLink.removeAttribute("href");
        downloadLink.removeAttribute("download");
        downloadLink.setAttribute("aria-disabled", "true");
        downloadLink.classList.add("is-disabled");
      }
    }

    if (status) {
      status.classList.remove("is-info", "is-success", "is-error", "is-warning");
      if (hasDownload) {
        status.textContent = subject
          ? `Certificate ready and trusted on this server: ${subject}`
          : "Certificate ready and trusted on this server.";
        status.classList.add("is-success");
      } else {
        status.textContent = "No app-only certificate has been generated from this page yet.";
        status.classList.add("is-info");
      }
    }

    if (metadata) {
      if (!hasDownload) {
        metadata.textContent = "Generate a certificate first, then download the `.cer` file and upload it in Entra app registration.";
      } else {
        const certificateReference = typeof appOnly.certificateReference === "string" ? appOnly.certificateReference : "";
        metadata.textContent = [
          `Thumbprint: ${thumbprint || "n/a"}`,
          `Generated: ${generatedAt ? formatZeroTrustDate(generatedAt) : "n/a"}`,
          `Expires: ${expiresAt ? formatZeroTrustDate(expiresAt) : "n/a"}`,
          `Reference: ${certificateReference || "n/a"}`,
        ].join(" / ");
      }
    }
  }

  function renderZeroTrustAuthenticationForm(assessment) {
    const authentication = assessment.authentication || {};
    const appOnly = authentication.appOnly || {};

    const authMode = document.getElementById("zero-trust-auth-mode");
    const useDeviceCode = document.getElementById("zero-trust-use-device-code");
    const appOnlyFields = document.getElementById("zero-trust-app-only-fields");
    const tenantId = document.getElementById("zero-trust-tenant-id");
    const clientId = document.getElementById("zero-trust-client-id");
    const certificateReference = document.getElementById("zero-trust-certificate-reference");
    const status = document.getElementById("zero-trust-auth-status");
    const saveButton = document.getElementById("zero-trust-auth-save");

    if (authMode) {
      authMode.value = authentication.mode === "app_only" ? "app_only" : "delegated";
    }
    if (useDeviceCode) {
      useDeviceCode.checked = Boolean(authentication.useDeviceCode);
      useDeviceCode.disabled = authMode && authMode.value === "app_only";
    }
    if (appOnlyFields) {
      appOnlyFields.hidden = !(authMode && authMode.value === "app_only");
    }
    if (tenantId) {
      tenantId.value = typeof appOnly.tenantId === "string" ? appOnly.tenantId : "";
    }
    if (clientId) {
      clientId.value = typeof appOnly.clientId === "string" ? appOnly.clientId : "";
    }
    if (certificateReference) {
      certificateReference.value = typeof appOnly.certificateReference === "string" ? appOnly.certificateReference : "";
    }

    if (status) {
      status.textContent = authentication.statusMessage || "Save settings before starting a run.";
      status.classList.remove("is-info", "is-success", "is-error", "is-warning");
      status.classList.add(authentication.ready ? "is-success" : "is-warning");
    }

    if (saveButton) {
      saveButton.disabled = zeroTrustViewState.isLoading;
    }
  }

  function collectZeroTrustAuthenticationForm() {
    const authMode = document.getElementById("zero-trust-auth-mode");
    const useDeviceCode = document.getElementById("zero-trust-use-device-code");
    const tenantId = document.getElementById("zero-trust-tenant-id");
    const clientId = document.getElementById("zero-trust-client-id");
    const certificateReference = document.getElementById("zero-trust-certificate-reference");

    return {
      mode: authMode && authMode.value === "app_only" ? "app_only" : "delegated",
      useDeviceCode: Boolean(useDeviceCode && useDeviceCode.checked),
      appOnly: {
        tenantId: tenantId ? tenantId.value.trim() : "",
        clientId: clientId ? clientId.value.trim() : "",
        certificateReference: certificateReference ? certificateReference.value.trim() : "",
      },
    };
  }

  async function saveZeroTrustAuthentication(event) {
    event.preventDefault();

    zeroTrustViewState.isLoading = true;
    setZeroTrustActionStatus("Saving authentication settings...", "info");
    renderZeroTrustPage();

    try {
      const payload = await apiRequest("/zero-trust/authentication/", {
        method: "PUT",
        body: JSON.stringify({
          authentication: collectZeroTrustAuthenticationForm(),
        }),
      });
      if (payload && payload.zeroTrustAssessment) {
        setZeroTrustAssessmentState(payload.zeroTrustAssessment);
      }
      zeroTrustViewState.hasLoaded = true;
      setZeroTrustActionStatus("Authentication settings saved.", "success");
    } catch (error) {
      const message = error instanceof Error ? error.message : "Unable to save authentication settings.";
      setZeroTrustActionStatus(message, "error");
    } finally {
      zeroTrustViewState.isLoading = false;
      renderZeroTrustPage();
    }
  }

  async function generateZeroTrustCertificate() {
    const assessment = getZeroTrustAssessmentState();
    if (!assessment.platform || !assessment.platform.supported) {
      setZeroTrustActionStatus("This feature only runs on Ubuntu.", "warning");
      renderZeroTrustPage();
      return;
    }

    zeroTrustViewState.isLoading = true;
    setZeroTrustActionStatus("Generating and trusting X.509 certificate on this server...", "info");
    renderZeroTrustPage();

    try {
      const payload = await apiRequest("/zero-trust/certificate/", { method: "POST" });
      if (payload && payload.zeroTrustAssessment) {
        setZeroTrustAssessmentState(payload.zeroTrustAssessment);
      }
      zeroTrustViewState.hasLoaded = true;
      setZeroTrustActionStatus(
        "Certificate generated. Download the `.cer` public key and upload it to your Entra app registration.",
        "success"
      );
    } catch (error) {
      const message = error instanceof Error ? error.message : "Unable to generate certificate.";
      setZeroTrustActionStatus(message, "error");
    } finally {
      zeroTrustViewState.isLoading = false;
      renderZeroTrustPage();
    }
  }

  function renderZeroTrustHistory(assessment) {
    const historyContainer = document.getElementById("zero-trust-history");
    if (!historyContainer) {
      return;
    }

    const history = Array.isArray(assessment.history) ? assessment.history : [];
    if (!history.length) {
      historyContainer.innerHTML = "<div class=\"empty-state\">No runs recorded yet.</div>";
      return;
    }

    historyContainer.innerHTML = history.slice(0, 8).map((entry) => {
      const status = zeroTrustStatusLabel(entry.status);
      const statusClass = zeroTrustStatusClass(entry.status);
      const summary = entry.message || "No details available.";
      const startedAt = entry.startedAt ? formatZeroTrustDate(entry.startedAt) : "-";
      const finishedAt = entry.finishedAt ? formatZeroTrustDate(entry.finishedAt) : "In progress";
      const trigger = entry.trigger ? entry.trigger : "manual";
      return `
        <article class="activity-card">
          <div class="activity-top">
            <div>
              <strong>${escapeHtml(entry.runId || "Run")}</strong>
              <div class="mini-copy">Trigger: ${escapeHtml(trigger)} / Started: ${escapeHtml(startedAt)}</div>
            </div>
            <span class="status-pill ${statusClass}">${escapeHtml(status)}</span>
          </div>
          <p class="activity-evidence">Finished: ${escapeHtml(finishedAt)}</p>
          <p class="activity-evidence">${escapeHtml(summary)}</p>
        </article>
      `;
    }).join("");
  }

  function renderZeroTrustReportViewer(assessment) {
    const frame = document.getElementById("zero-trust-report-frame");
    const emptyState = document.getElementById("zero-trust-report-empty");
    const note = document.getElementById("zero-trust-report-note");
    if (!frame || !emptyState || !note) {
      return;
    }

    const latestResult = assessment.latestResult || {};
    const reportPath = typeof latestResult.reportPath === "string" ? latestResult.reportPath.trim() : "";
    const reportStatus = typeof latestResult.status === "string" ? latestResult.status.trim().toLowerCase() : "";

    if (!reportPath || reportStatus !== "succeeded") {
      frame.hidden = true;
      if (frame.src) {
        frame.src = "";
      }
      zeroTrustViewState.reportToken = "";
      emptyState.hidden = false;
      note.textContent = "No report to display yet. Run the assessment first.";
      return;
    }

    const reportToken = latestResult.runId || reportPath;
    const reportUrl = `${apiBaseUrl}/zero-trust/report/?run=${encodeURIComponent(reportToken)}`;
    if (zeroTrustViewState.reportToken !== reportToken) {
      frame.src = reportUrl;
      zeroTrustViewState.reportToken = reportToken;
    }

    frame.hidden = false;
    emptyState.hidden = true;
    note.textContent = `Loaded from ${reportPath}.`;
  }

  function renderZeroTrustAssessmentPanel(assessment) {
    const run = assessment.run || {};
    const schedule = assessment.schedule || {};
    const latestResult = assessment.latestResult || {};
    const authentication = assessment.authentication || {};

    const runStatus = document.getElementById("zero-trust-run-status");
    const scheduleStatus = document.getElementById("zero-trust-schedule-status");
    const reportStatus = document.getElementById("zero-trust-report-status");
    const logStatus = document.getElementById("zero-trust-log-status");
    const actionStatus = document.getElementById("zero-trust-action-status");
    const runButton = document.getElementById("zero-trust-run-trigger");
    const refreshButton = document.getElementById("zero-trust-refresh-trigger");

    if (runStatus) {
      const startedAt = run.startedAt ? formatZeroTrustDate(run.startedAt) : "Not started";
      const finishedAt = run.finishedAt ? formatZeroTrustDate(run.finishedAt) : "In progress";
      runStatus.textContent = `${zeroTrustStatusLabel(run.status)} / Started: ${startedAt} / Finished: ${finishedAt}`;
    }

    if (scheduleStatus) {
      const intervalDays = Math.max(1, Number(schedule.intervalDays) || 7);
      const nextRun = schedule.nextRunAt ? formatZeroTrustDate(schedule.nextRunAt) : "After first run";
      const firstRun = schedule.firstRunAt ? formatZeroTrustDate(schedule.firstRunAt) : "Not yet run";
      scheduleStatus.textContent = `Interval: every ${intervalDays} day(s) / First run: ${firstRun} / Next run: ${nextRun}`;
    }

    if (reportStatus) {
      const generatedAt = latestResult.reportGeneratedAt ? formatZeroTrustDate(latestResult.reportGeneratedAt) : "Not available";
      const sizeText = latestResult.reportSizeBytes ? formatZeroTrustFileSize(latestResult.reportSizeBytes) : "0 B";
      const pathText = latestResult.reportPath || "No report path available";
      reportStatus.textContent = `${pathText} / ${sizeText} / Generated: ${generatedAt}`;
    }

    if (logStatus) {
      logStatus.textContent = latestResult.logPath || run.logPath || "Log path appears after the first run.";
    }

    if (actionStatus) {
      const message = zeroTrustViewState.actionMessage || run.message || "Weekly scheduling starts automatically after the first run.";
      actionStatus.textContent = message;
      actionStatus.classList.remove("is-info", "is-success", "is-error", "is-warning");
      actionStatus.classList.add(`is-${zeroTrustViewState.actionTone || "info"}`);
    }

    const platformSupported = Boolean(assessment.platform && assessment.platform.supported);
    const authenticationReady = typeof authentication.ready === "boolean" ? authentication.ready : true;
    const running = String(run.status || "").trim().toLowerCase() === "running";

    if (runButton) {
      runButton.disabled = !platformSupported || !authenticationReady || running || zeroTrustViewState.isLoading;
    }
    if (refreshButton) {
      refreshButton.disabled = zeroTrustViewState.isLoading;
    }

    renderZeroTrustAuthenticationForm(assessment);
    renderZeroTrustHistory(assessment);
    renderZeroTrustReportViewer(assessment);
  }

  function setZeroTrustActionStatus(message, tone = "info") {
    zeroTrustViewState.actionMessage = String(message || "").trim();
    zeroTrustViewState.actionTone = tone;
  }

  async function refreshZeroTrustAssessmentStatus(autoRun = false) {
    if (page !== "zero-trust") {
      return;
    }

    if (zeroTrustViewState.isLoading) {
      return;
    }

    zeroTrustViewState.isLoading = true;
    try {
      const path = autoRun ? "/zero-trust/status/?autoRun=1" : "/zero-trust/status/";
      const payload = await apiRequest(path);
      if (payload && payload.zeroTrustAssessment) {
        setZeroTrustAssessmentState(payload.zeroTrustAssessment);
      }
      zeroTrustViewState.hasLoaded = true;
      zeroTrustViewState.actionMessage = "";
      zeroTrustViewState.actionTone = "info";
    } catch (error) {
      const message = error instanceof Error ? error.message : "Unable to refresh Zero Trust status.";
      setZeroTrustActionStatus(message, "error");
    } finally {
      zeroTrustViewState.isLoading = false;
      renderZeroTrustPage();
    }
  }

  async function runZeroTrustAssessmentNow() {
    const assessment = getZeroTrustAssessmentState();
    if (!assessment.platform || !assessment.platform.supported) {
      setZeroTrustActionStatus("This feature only runs on Ubuntu.", "warning");
      renderZeroTrustPage();
      return;
    }
    if (assessment.authentication && assessment.authentication.ready === false) {
      setZeroTrustActionStatus(
        assessment.authentication.statusMessage || "Authentication settings are incomplete.",
        "warning"
      );
      renderZeroTrustPage();
      return;
    }

    zeroTrustViewState.isLoading = true;
    setZeroTrustActionStatus("Starting assessment run...", "info");
    renderZeroTrustPage();

    try {
      const payload = await apiRequest("/zero-trust/run/", { method: "POST" });
      if (payload && payload.zeroTrustAssessment) {
        setZeroTrustAssessmentState(payload.zeroTrustAssessment);
      }
      zeroTrustViewState.hasLoaded = true;
      const mode = assessment.authentication && assessment.authentication.mode === "app_only"
        ? "app-only"
        : "delegated";
      setZeroTrustActionStatus(
        mode === "app-only"
          ? "Assessment started in app-only mode."
          : "Assessment started in delegated mode. Complete Microsoft sign-in prompts if they appear.",
        "success"
      );
      scheduleZeroTrustPolling(7000);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Unable to start Zero Trust assessment.";
      setZeroTrustActionStatus(message, "error");
    } finally {
      zeroTrustViewState.isLoading = false;
      renderZeroTrustPage();
    }
  }

  function bindZeroTrustEvents() {
    if (page !== "zero-trust" || zeroTrustViewState.hasBoundEvents) {
      return;
    }

    const tabBar = document.getElementById("zero-trust-tab-bar");
    const runButton = document.getElementById("zero-trust-run-trigger");
    const refreshButton = document.getElementById("zero-trust-refresh-trigger");
    const authForm = document.getElementById("zero-trust-auth-form");
    const authMode = document.getElementById("zero-trust-auth-mode");
    const generateCertificateButton = document.getElementById("zero-trust-certificate-generate");

    if (tabBar) {
      tabBar.addEventListener("click", (event) => {
        const button = event.target.closest("[data-zero-trust-tab]");
        if (!button) {
          return;
        }
        zeroTrustViewState.activeTab = button.dataset.zeroTrustTab || "prerequisites";
        updateZeroTrustTabState();
      });
    }

    if (runButton) {
      runButton.addEventListener("click", () => {
        void runZeroTrustAssessmentNow();
      });
    }

    if (refreshButton) {
      refreshButton.addEventListener("click", () => {
        void refreshZeroTrustAssessmentStatus(true);
      });
    }

    if (authForm) {
      authForm.addEventListener("submit", (event) => {
        void saveZeroTrustAuthentication(event);
      });
    }

    if (authMode) {
      authMode.addEventListener("change", () => {
        renderZeroTrustPage();
      });
    }

    if (generateCertificateButton) {
      generateCertificateButton.addEventListener("click", () => {
        void generateZeroTrustCertificate();
      });
    }

    zeroTrustViewState.hasBoundEvents = true;
  }

  function renderZeroTrustPage() {
    if (page !== "zero-trust") {
      clearZeroTrustPolling();
      return;
    }

    bindZeroTrustEvents();

    const assessment = getZeroTrustAssessmentState();

    renderZeroTrustOverviewCards(assessment);
    renderZeroTrustPrerequisites(assessment);
    renderZeroTrustAssessmentPanel(assessment);

    updateZeroTrustTabState();

    const isRunning = String(assessment.run && assessment.run.status ? assessment.run.status : "")
      .trim()
      .toLowerCase() === "running";
    if (isRunning) {
      scheduleZeroTrustPolling(15000);
    } else {
      clearZeroTrustPolling();
    }

    if (!zeroTrustViewState.hasLoaded && !zeroTrustViewState.isLoading) {
      void refreshZeroTrustAssessmentStatus(true);
    }
  }
