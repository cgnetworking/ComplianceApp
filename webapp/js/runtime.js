  const data = createEmptyMappingPayload();

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
  const controlsById = new Map();
  let uploadedDocuments = [];
  let vendorSurveyResponses = [];
  const documentsById = new Map();
  const today = new Date();
  const page = document.body.dataset.page || "home";
  const params = new URLSearchParams(window.location.search);
  const initialMonthIndex = page === "reviews" && params.has("month")
    ? parseMonth(params.get("month"))
    : today.getMonth();
  refreshControlsIndex();
  refreshDocumentsIndex();

  const state = {
    search: params.get("q") || "",
    domain: params.get("domain") || "All",
    riskAssignee: params.get("assignee") || "All",
    riskStatus: params.get("status") || "All",
    riskLevel: params.get("level") || "All",
    monthIndex: initialMonthIndex,
    selectedControlId: params.get("control"),
    policyContextControlId: params.get("control"),
    activeDocumentId: params.get("doc"),
    selectedRiskId: params.get("risk") || "",
    selectedVendorResponseId: params.get("vendor"),
    vendorResponsesLoaded: false,
    selectedAssessmentProfileId: params.get("profile") || "",
    selectedAssessmentRunId: params.get("run") || "",
    riskRegister: [],
    assignableUsers: [],
    isAddingRisk: false,
    riskFormStatus: { message: "", tone: "" },
    reviewState: { activities: {}, checklist: {}, completedAt: {} },
    auditLog: [],
    checklistItems: [],
    recommendedChecklistItems: [],
    controlState: {},
  };

  const els = {
    searchInput: document.getElementById("search-input"),
    domainFilter: document.getElementById("domain-filter"),
    clearFilters: document.getElementById("clear-filters"),
    overview: document.getElementById("overview"),
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
    assessmentStatus: document.getElementById("assessment-status"),
    assessmentOverview: document.getElementById("assessment-overview"),
    assessmentProfiles: document.getElementById("assessment-profiles"),
    assessmentDetail: document.getElementById("assessment-detail"),
    assessmentReport: document.getElementById("assessment-report"),
    assessmentNewProfile: document.getElementById("assessment-new-profile"),
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
    checklistAddStartDate: document.getElementById("checklist-add-start-date"),
    checklistAddOwnerSearch: document.getElementById("checklist-add-owner-search"),
    checklistAddOwner: document.getElementById("checklist-add-owner"),
    checklistRecommendationSelect: document.getElementById("checklist-recommendation-select"),
    checklistRecommendationAdd: document.getElementById("checklist-recommendation-add"),
    reviewTasksList: document.getElementById("review-tasks-list"),
    reviewTasksStatus: document.getElementById("review-tasks-status"),
    homeUpcoming: document.getElementById("home-upcoming"),
    addRiskTrigger: document.getElementById("add-risk-trigger"),
    riskAssigneeFilter: document.getElementById("risk-assignee-filter"),
    riskStatusFilter: document.getElementById("risk-status-filter"),
    riskLevelFilter: document.getElementById("risk-level-filter"),
    riskList: document.getElementById("risk-list"),
    riskForm: document.getElementById("risk-form"),
    riskFormKicker: document.getElementById("risk-form-kicker"),
    riskFormTitle: document.getElementById("risk-form-title"),
    riskFormCopy: document.getElementById("risk-form-copy"),
    riskNameInput: document.getElementById("risk-name"),
    riskDateInput: document.getElementById("risk-date"),
    riskOwnerSearchInput: document.getElementById("risk-owner-search"),
    riskOwnerInput: document.getElementById("risk-owner"),
    riskClosedDateInput: document.getElementById("risk-closed-date"),
    riskSubmitButton: document.getElementById("risk-submit-button"),
    riskDeleteButton: document.getElementById("risk-delete-button"),
    riskFormStatus: document.getElementById("risk-form-status"),
    riskProbabilityInput: document.querySelector(
      '#risk-probability, select[name="risk-probability"], select[name="probability"], select[name="initial-risk-probability"], input[name="risk-probability"]:not([type="radio"]), input[name="probability"]:not([type="radio"]), input[name="initial-risk-probability"]:not([type="radio"])'
    ),
    riskImpactInput: document.querySelector(
      '#risk-impact, select[name="risk-impact"], select[name="impact"], select[name="initial-risk-impact"], input[name="risk-impact"]:not([type="radio"]), input[name="impact"]:not([type="radio"]), input[name="initial-risk-impact"]:not([type="radio"])'
    ),
    riskProbabilityInputs: Array.from(
      document.querySelectorAll('input[type="radio"][name="risk-probability"], input[type="radio"][name="probability"], input[type="radio"][name="initial-risk-probability"]')
    ),
    riskImpactInputs: Array.from(
      document.querySelectorAll('input[type="radio"][name="risk-impact"], input[type="radio"][name="impact"], input[type="radio"][name="initial-risk-impact"]')
    ),
    riskLevelInputs: Array.from(document.querySelectorAll('input[name="initial-risk-level"]')),
  };

  async function init() {
    await loadRemoteState();
    await loadAssignableUsers();
    if (page === "vendors" && typeof loadVendorResponsesState === "function") {
      await loadVendorResponsesState();
    }
    if (page === "assessments" && typeof loadZeroTrustState === "function") {
      await loadZeroTrustState();
    }
    updatePersistenceCopy();
    if (els.searchInput) {
      els.searchInput.value = state.search;
    }

    populateFilters();
    initializeSelection();
    bindEvents();
    renderPage();
    if (typeof applyRowSelectionAccessibility === "function") {
      applyRowSelectionAccessibility();
    }
  }

  async function loadAssignableUsers() {
    if (!new Set(["controls", "reviews", "risks"]).has(page)) {
      return;
    }
    if (!Array.isArray(state.assignableUsers) || !state.assignableUsers.length) {
      throw new Error("Assignable users were not loaded from the state API.");
    }
  }

void init();
