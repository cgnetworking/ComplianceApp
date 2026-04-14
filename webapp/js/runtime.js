  const data = window.ISMS_DATA && typeof window.ISMS_DATA === "object" ? window.ISMS_DATA : {};
  normalizeDataPayload(data);

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
  const defaultChecklistCategories = [
    "ISMS Governance",
    "Risk",
    "Annex A",
    "People",
    "Access",
    "Assets",
    "Suppliers",
    "Cloud",
    "Physical",
    "Operations",
    "Backups",
    "BCDR",
    "Development",
    "Incidents",
    "Compliance",
    "Custom",
  ];
  const defaultChecklistFrequencies = ["Annual", "Quarterly", "Monthly", "Semi-annual", "Per event", "Not scheduled"];
  const defaultChecklistOwners = ["Head of IT", "CTO", "Shared portal"];
  const domainColors = {
    Organizational: "#7442b8",
    People: "#9d3f9d",
    Physical: "#d05ad4",
    Technological: "#4e92e6",
  };
  const documentTypeOrder = {
    POL: 0,
    GOV: 1,
    PR: 2,
    UPL: 3,
  };
  const apiBaseUrl = resolveApiBaseUrl();
  const loginUrl = resolveLoginUrl();
  const storageKey = "isms-policy-portal-review-state-v1";
  const controlStateKey = "isms-policy-portal-control-state-v1";
  const uploadedPolicyKey = "isms-policy-portal-uploaded-policies-v1";
  const vendorSurveyKey = "isms-policy-portal-vendor-surveys-v1";
  const riskRegisterKey = "isms-policy-portal-risk-register-v1";
  let persistenceMode = "local";
  const controlsById = new Map();
  let uploadedDocuments = loadUploadedPolicies();
  let vendorSurveyResponses = loadVendorResponses();
  const documentsById = new Map();
  const today = new Date();
  const page = document.body.dataset.page || "home";
  const params = new URLSearchParams(window.location.search);
  refreshControlsIndex();
  refreshDocumentsIndex();

  const state = {
    search: params.get("q") || "",
    domain: params.get("domain") || "All",
    applicability: params.get("applicability") || "All",
    frequency: params.get("frequency") || "All",
    monthIndex: parseMonth(params.get("month")),
    selectedControlId: params.get("control"),
    policyContextControlId: params.get("control"),
    activeDocumentId: params.get("doc"),
    selectedRiskId: params.get("risk") || "",
    selectedVendorResponseId: params.get("vendor"),
    riskRegister: loadRiskRegister(),
    isAddingRisk: false,
    riskFormStatus: { message: "", tone: "" },
    reviewState: loadReviewState(),
    checklistItems: [],
    recommendedChecklistItems: [],
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
    policyUploadTrigger: document.getElementById("policy-upload-trigger"),
    policyUploadInput: document.getElementById("policy-upload-input"),
    policyUploadStatus: document.getElementById("policy-upload-status"),
    mappingUploadTrigger: document.getElementById("mapping-upload-trigger"),
    mappingUploadInput: document.getElementById("mapping-upload-input"),
    mappingUploadStatus: document.getElementById("mapping-upload-status"),
    vendorUploadTrigger: document.getElementById("vendor-upload-trigger"),
    vendorUploadInput: document.getElementById("vendor-upload-input"),
    vendorUploadStatus: document.getElementById("vendor-upload-status"),
    vendorOverview: document.getElementById("vendor-overview"),
    vendorResponses: document.getElementById("vendor-responses"),
    vendorDetail: document.getElementById("vendor-detail"),
    monthTabs: document.getElementById("month-tabs"),
    activities: document.getElementById("activities"),
    checklistSummary: document.getElementById("checklist-summary"),
    checklist: document.getElementById("checklist"),
    checklistAddTrigger: document.getElementById("checklist-add-trigger"),
    checklistAddForm: document.getElementById("checklist-add-form"),
    checklistAddCancel: document.getElementById("checklist-add-cancel"),
    checklistAddStatus: document.getElementById("checklist-add-status"),
    checklistAddCategory: document.getElementById("checklist-add-category"),
    checklistAddItem: document.getElementById("checklist-add-item"),
    checklistAddFrequency: document.getElementById("checklist-add-frequency"),
    checklistAddOwner: document.getElementById("checklist-add-owner"),
    checklistRecommendationSelect: document.getElementById("checklist-recommendation-select"),
    checklistRecommendationAdd: document.getElementById("checklist-recommendation-add"),
    homeUpcoming: document.getElementById("home-upcoming"),
    homeDomains: document.getElementById("home-domains"),
    homePolicies: document.getElementById("home-policies"),
    addRiskTrigger: document.getElementById("add-risk-trigger"),
    riskList: document.getElementById("risk-list"),
    riskForm: document.getElementById("risk-form"),
    riskFormKicker: document.getElementById("risk-form-kicker"),
    riskFormTitle: document.getElementById("risk-form-title"),
    riskFormCopy: document.getElementById("risk-form-copy"),
    riskNameInput: document.getElementById("risk-name"),
    riskDateInput: document.getElementById("risk-date"),
    riskOwnerInput: document.getElementById("risk-owner"),
    riskClosedDateInput: document.getElementById("risk-closed-date"),
    riskSubmitButton: document.getElementById("risk-submit-button"),
    riskFormStatus: document.getElementById("risk-form-status"),
    riskLevelInputs: Array.from(document.querySelectorAll('input[name="initial-risk-level"]')),
  };

  async function init() {
    await loadRemoteState();
    updateRuntimeMode();
    updatePersistenceCopy();
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

void init();
