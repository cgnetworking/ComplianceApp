const reviewMonthNames = [
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

function emptySummary() {
  return {
    controlCount: 0,
    documentCount: 0,
    policyCount: 0,
    activityCount: 0,
    checklistCount: 0,
    domainCounts: {},
    documentReviewFrequencies: {},
    checklistFrequencies: {},
  };
}

function createEmptyMappingPayload() {
  return {
    generatedAt: new Date().toISOString(),
    sourceSnapshot: {},
    summary: emptySummary(),
    controls: [],
    documents: [],
    activities: [],
    checklist: [],
    policyCoverage: [],
  };
}

function normalizeUploadedPolicyItem(item) {
  if (!item || typeof item !== "object") {
    return null;
  }
  const id = typeof item.id === "string" ? item.id.trim() : "";
  const title = typeof item.title === "string" ? item.title.trim() : "";
  const type = typeof item.type === "string" ? item.type.trim() : "";
  const approver = typeof item.approver === "string" ? item.approver.trim() : "";
  const reviewFrequency = typeof item.reviewFrequency === "string" ? item.reviewFrequency.trim() : "";
  const path = typeof item.path === "string" ? item.path.trim() : "";
  const folder = typeof item.folder === "string" ? item.folder.trim() : "";
  const contentHtml = typeof item.contentHtml === "string" ? item.contentHtml : "";
  if (!id || !title || !type || !approver || !reviewFrequency || !path || !folder) {
    return null;
  }
  if (typeof item.contentAvailable !== "boolean" || typeof item.contentLoaded !== "boolean") {
    return null;
  }
  return {
    id,
    title,
    type,
    approver,
    approvedAt: typeof item.approvedAt === "string" ? item.approvedAt : "",
    approvedBy: typeof item.approvedBy === "string" ? item.approvedBy : "",
    reviewFrequency,
    path,
    folder,
    purpose: typeof item.purpose === "string" ? item.purpose : "",
    contentHtml,
    contentAvailable: item.contentAvailable,
    contentLoaded: item.contentLoaded,
    isUploaded: true,
    originalFilename: typeof item.originalFilename === "string" ? item.originalFilename : "",
    uploadedAt: typeof item.uploadedAt === "string" ? item.uploadedAt : "",
  };
}

function normalizeMappingDocumentItem(item) {
  if (!item || typeof item !== "object") {
    return null;
  }
  const id = typeof item.id === "string" ? item.id.trim() : "";
  const title = typeof item.title === "string" ? item.title.trim() : "";
  if (!id || !title) {
    return null;
  }
  const contentHtml = typeof item.contentHtml === "string" ? item.contentHtml : "";
  return {
    id,
    title,
    type: typeof item.type === "string" ? item.type : "",
    owner: typeof item.owner === "string" ? item.owner : "",
    approver: typeof item.approver === "string" ? item.approver : "",
    reviewFrequency: typeof item.reviewFrequency === "string" ? item.reviewFrequency : "",
    path: typeof item.path === "string" ? item.path : "",
    folder: typeof item.folder === "string" ? item.folder : "",
    purpose: typeof item.purpose === "string" ? item.purpose : "",
    contentHtml,
    contentAvailable: typeof item.contentAvailable === "boolean" ? item.contentAvailable : false,
    contentLoaded: typeof item.contentLoaded === "boolean" ? item.contentLoaded : false,
    isUploaded: Boolean(item.isUploaded),
    originalFilename: typeof item.originalFilename === "string" ? item.originalFilename : "",
  };
}

function buildReviewStateMonthKey(itemId, monthIndex) {
  const normalizedItemId = typeof itemId === "string" ? itemId.trim() : "";
  if (!normalizedItemId) {
    return "";
  }
  const parsedMonth = Number(monthIndex);
  if (!Number.isInteger(parsedMonth) || parsedMonth < 0 || parsedMonth > 11) {
    throw new Error("Review state month index is invalid.");
  }
  return `m${parsedMonth}::${normalizedItemId}`;
}

function isMonthScopedReviewStateKey(value) {
  return typeof value === "string" && /^m(?:[0-9]|1[01])::.+$/.test(value);
}

function normalizeReviewStateMapByMonth(value) {
  if (!value || typeof value !== "object") {
    return {};
  }
  const normalized = {};
  Object.entries(value).forEach(([rawKey, rawValue]) => {
    const key = String(rawKey || "").trim();
    if (!key) {
      return;
    }
    if (!isMonthScopedReviewStateKey(key)) {
      throw new Error(`Review state key '${key}' is not month scoped.`);
    }
    normalized[key] = Boolean(rawValue);
  });
  return normalized;
}

function normalizeReviewStateTimestampMap(value) {
  if (!value || typeof value !== "object") {
    return {};
  }

  const normalized = {};
  Object.entries(value).forEach(([rawKey, rawValue]) => {
    const key = String(rawKey || "").trim();
    const parsed = new Date(rawValue);
    if (!key) {
      return;
    }
    if (Number.isNaN(parsed.getTime())) {
      throw new Error(`Review state timestamp for '${key}' is invalid.`);
    }
    if (!isMonthScopedReviewStateKey(key)) {
      throw new Error(`Review state timestamp key '${key}' is not month scoped.`);
    }
    normalized[key] = parsed.toISOString();
  });
  return normalized;
}

function normalizeReviewAuditLogEntries(value) {
  if (!Array.isArray(value)) {
    return [];
  }

  return value
    .map((entry) => {
      if (!entry || typeof entry !== "object") {
        return null;
      }
      if (
        typeof entry.id !== "string"
        || typeof entry.action !== "string"
        || typeof entry.entityType !== "string"
        || typeof entry.summary !== "string"
        || typeof entry.occurredAt !== "string"
        || !entry.actor
        || typeof entry.actor !== "object"
        || typeof entry.actor.username !== "string"
      ) {
        throw new Error("Review state audit log entry shape is invalid.");
      }
      return {
        id: entry.id.trim(),
        action: entry.action.trim(),
        entityType: entry.entityType.trim(),
        entityId: typeof entry.entityId === "string" ? entry.entityId.trim() : "",
        summary: entry.summary.trim(),
        occurredAt: entry.occurredAt,
        actor: {
          username: entry.actor.username.trim(),
          displayName: typeof entry.actor.displayName === "string" ? entry.actor.displayName.trim() : "",
        },
        metadata: entry.metadata && typeof entry.metadata === "object" ? entry.metadata : {},
      };
    })
    .filter(Boolean)
    .slice(-2000);
}

function normalizeReviewStateValue(value) {
  if (!value || typeof value !== "object") {
    return { activities: {}, checklist: {}, completedAt: {}, auditLog: [] };
  }
  return {
    activities: normalizeReviewStateMapByMonth(value.activities),
    checklist: normalizeReviewStateMapByMonth(value.checklist),
    completedAt: normalizeReviewStateTimestampMap(value.completedAt),
    auditLog: normalizeReviewAuditLogEntries(value.auditLog),
  };
}

function parseChecklistDateParts(value) {
  const normalized = String(value || "").trim();
  if (!normalized) {
    return null;
  }
  const match = normalized.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (!match) {
    return null;
  }
  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  const parsed = new Date(Date.UTC(year, month - 1, day));
  if (
    parsed.getUTCFullYear() !== year
    || parsed.getUTCMonth() !== month - 1
    || parsed.getUTCDate() !== day
  ) {
    return null;
  }
  return {
    isoDate: `${String(year).padStart(4, "0")}-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}`,
    year,
    monthIndex: month - 1,
    day,
  };
}

function recurringMonths(anchorMonth, interval, count) {
  const seen = new Set();
  const months = [];
  for (let index = 0; index < count; index += 1) {
    const month = (anchorMonth + (interval * index)) % 12;
    if (seen.has(month)) {
      continue;
    }
    seen.add(month);
    months.push(month);
  }
  return months;
}

function dueMonthsForFrequency(frequency, startDate = "") {
  const value = String(frequency || "").trim().toLowerCase();
  const dateParts = parseChecklistDateParts(startDate);
  const anchorMonth = dateParts ? dateParts.monthIndex : null;
  if (value.includes("monthly")) {
    return [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11];
  }
  if (value.includes("quarterly")) {
    return recurringMonths(anchorMonth === null ? 2 : anchorMonth, 3, 4);
  }
  if (value.includes("semi")) {
    return recurringMonths(anchorMonth === null ? 5 : anchorMonth, 6, 2);
  }
  if (value.includes("annual")) {
    return [anchorMonth === null ? 11 : anchorMonth];
  }
  return [];
}

function normalizeChecklistStartDate(value) {
  const parts = parseChecklistDateParts(value);
  return parts ? parts.isoDate : "";
}

function normalizeChecklistCreatedAt(value) {
  const raw = typeof value === "string" ? value.trim() : "";
  if (!raw) {
    return "";
  }
  if (typeof parseDisplayDateValue === "function") {
    return parseDisplayDateValue(raw) ? raw : "";
  }
  const parsed = new Date(raw);
  return Number.isNaN(parsed.getTime()) ? "" : raw;
}

function checklistFrequencyWithAnchorLabel(frequency, startDate, monthIndex = null) {
  const normalizedFrequency = String(frequency || "").trim() || "Not scheduled";
  const dateParts = parseChecklistDateParts(startDate);
  if (!dateParts) {
    return normalizedFrequency;
  }
  if (normalizedFrequency.toLowerCase().includes("monthly")) {
    return `${normalizedFrequency} (day ${dateParts.day})`;
  }
  const displayMonthIndex = Number.isInteger(monthIndex) ? monthIndex : dateParts.monthIndex;
  return `${normalizedFrequency} (${reviewMonthNames[displayMonthIndex]} ${dateParts.day})`;
}

function normalizeChecklistItems(items) {
  if (!Array.isArray(items)) {
    return [];
  }

  const seenIds = new Set();
  return items
    .map((item) => {
      if (!item || typeof item !== "object") {
        return null;
      }
      const id = typeof item.id === "string" ? item.id.trim() : "";
      const checklistItem = typeof item.item === "string" ? item.item.trim() : "";
      const category = typeof item.category === "string" ? item.category.trim() : "";
      const frequency = typeof item.frequency === "string" ? item.frequency.trim() : "";
      const owner = typeof item.owner === "string" ? item.owner.trim() : "";
      if (!id || !checklistItem || seenIds.has(id)) {
        return null;
      }
      if (!category || !frequency || !owner) {
        return null;
      }
      seenIds.add(id);
      return {
        id,
        category,
        item: checklistItem,
        frequency,
        startDate: normalizeChecklistStartDate(item.startDate),
        owner,
        createdAt: normalizeChecklistCreatedAt(item.createdAt),
      };
    })
    .filter(Boolean);
}

function normalizeAssignableUsers(items) {
  if (!Array.isArray(items)) {
    return [];
  }

  const seen = new Set();
  return items
    .map((item) => {
      if (!item || typeof item !== "object") {
        return null;
      }
      const username = typeof item.username === "string" ? item.username.trim() : "";
      const displayName = typeof item.displayName === "string" ? item.displayName.trim() : "";
      if (!username || seen.has(username)) {
        return null;
      }
      if (!displayName) {
        return null;
      }
      seen.add(username);
      return { username, displayName };
    })
    .filter(Boolean)
    .sort((left, right) => left.displayName.localeCompare(right.displayName, undefined, { numeric: true, sensitivity: "base" }));
}

function normalizeDataPayload(payload) {
  if (!payload || typeof payload !== "object") {
    throw new Error("Mapping payload must be an object.");
  }
  if (typeof payload.generatedAt !== "string" || !payload.generatedAt.trim()) {
    throw new Error("Mapping payload generatedAt is required.");
  }
  if (!payload.sourceSnapshot || typeof payload.sourceSnapshot !== "object") {
    throw new Error("Mapping payload sourceSnapshot is required.");
  }
  if (!payload.summary || typeof payload.summary !== "object") {
    throw new Error("Mapping payload summary is required.");
  }
  if (!Array.isArray(payload.controls) || !Array.isArray(payload.documents) || !Array.isArray(payload.activities)
    || !Array.isArray(payload.checklist) || !Array.isArray(payload.policyCoverage)) {
    throw new Error("Mapping payload arrays are required.");
  }
}

function applyMappingPayload(payload) {
  const mappingPayload = payload && typeof payload === "object" ? payload : {};
  normalizeDataPayload(mappingPayload);

  data.generatedAt = mappingPayload.generatedAt;
  data.sourceSnapshot = mappingPayload.sourceSnapshot;
  data.summary = mappingPayload.summary;
  data.controls = mappingPayload.controls;
  data.documents = mappingPayload.documents
    .map((item) => normalizeMappingDocumentItem(item))
    .filter(Boolean);
  data.activities = mappingPayload.activities;
  data.checklist = mappingPayload.checklist;
  data.policyCoverage = mappingPayload.policyCoverage;

  refreshControlsIndex();
  refreshDocumentsIndex();
  pruneControlState();
}

function refreshControlsIndex() {
  controlsById.clear();
  data.controls.forEach((control) => {
    if (!control || typeof control !== "object" || typeof control.id !== "string") {
      return;
    }
    if (!Array.isArray(control.documentIds)) {
      control.documentIds = [];
    }
    if (!Array.isArray(control.policyDocumentIds)) {
      control.policyDocumentIds = Array.isArray(control.documentIds) ? control.documentIds : [];
    }
    controlsById.set(control.id, control);
  });
}

function pruneControlState() {
  Object.keys(state.controlState).forEach((controlId) => {
    if (!controlsById.has(controlId)) {
      delete state.controlState[controlId];
    }
  });
}

function refreshDocumentsIndex() {
  documentsById.clear();
  data.documents.concat(uploadedDocuments).forEach((documentItem) => {
    documentsById.set(documentItem.id, documentItem);
  });
}

async function loadRemoteState() {
  const payload = await apiRequest(`/state/?page=${encodeURIComponent(page)}`);
  applyRemoteState(payload);
}

function applyRemoteState(payload) {
  if (!payload || typeof payload !== "object") {
    return;
  }

  if (payload.mapping && typeof payload.mapping === "object") {
    applyMappingPayload(payload.mapping);
  }
  if (Array.isArray(payload.uploadedDocuments)) {
    uploadedDocuments = payload.uploadedDocuments.map((item) => normalizeUploadedPolicyItem(item)).filter(Boolean);
  }
  if (Array.isArray(payload.vendorSurveyResponses)) {
    vendorSurveyResponses = payload.vendorSurveyResponses;
    state.vendorResponsesLoaded = true;
  }
  if (Array.isArray(payload.riskRegister)) {
    state.riskRegister = payload.riskRegister.map((item) => normalizeRiskRecord(item)).filter(Boolean);
  }
  if (Array.isArray(payload.assignableUsers) && typeof normalizeAssignableUsers === "function") {
    state.assignableUsers = normalizeAssignableUsers(payload.assignableUsers);
  }
  if (Array.isArray(payload.checklistItems)) {
    state.checklistItems = normalizeChecklistItems(payload.checklistItems);
  }
  if (Array.isArray(payload.recommendedChecklistItems)) {
    state.recommendedChecklistItems = normalizeChecklistItems(payload.recommendedChecklistItems);
  }
  if (payload.reviewState && typeof payload.reviewState === "object") {
    state.reviewState = normalizeReviewStateValue(payload.reviewState);
  }
  if (payload.controlState && typeof payload.controlState === "object") {
    state.controlState = payload.controlState;
  }

  refreshControlsIndex();
  refreshDocumentsIndex();
  pruneControlState();
}

async function saveReviewState() {
  const payload = await apiRequest("/state/review/", {
    method: "PUT",
    body: JSON.stringify({ reviewState: state.reviewState }),
  });

  if (!payload || !payload.reviewState || typeof payload.reviewState !== "object" || Array.isArray(payload.reviewState)) {
    throw new Error("Review state save response was invalid.");
  }

  state.reviewState = normalizeReviewStateValue(payload.reviewState);
  return state.reviewState;
}

async function saveControlState() {
  const payload = await apiRequest("/state/control/", {
    method: "PUT",
    body: JSON.stringify({ controlState: state.controlState }),
  });

  if (!payload || !payload.controlState || typeof payload.controlState !== "object" || Array.isArray(payload.controlState)) {
    throw new Error("Control state save response was invalid.");
  }

  state.controlState = payload.controlState;
  pruneControlState();
  return state.controlState;
}

async function runAsyncOperation(setStatus, messages, operation) {
  const pendingMessage = messages && typeof messages.pending === "function"
    ? messages.pending()
    : messages && Object.prototype.hasOwnProperty.call(messages, "pending")
      ? messages.pending
      : "";
  if (typeof setStatus === "function") {
    setStatus(pendingMessage || "", "info");
  }

  try {
    const result = await operation();
    const successMessage = messages && typeof messages.success === "function"
      ? messages.success(result)
      : messages && Object.prototype.hasOwnProperty.call(messages, "success")
        ? messages.success
        : "";
    if (typeof setStatus === "function" && successMessage !== null && successMessage !== undefined) {
      setStatus(successMessage || "", "success");
    }
    return result;
  } catch (error) {
    const configuredErrorMessage = messages && typeof messages.error === "function"
      ? messages.error(error)
      : messages && Object.prototype.hasOwnProperty.call(messages, "error")
        ? messages.error
        : "";
    const detail = error instanceof Error && error.message
      ? error.message
      : configuredErrorMessage || "Operation failed.";
    if (typeof setStatus === "function") {
      setStatus(detail, "error");
    }
    throw error;
  }
}
