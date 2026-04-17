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

function normalizeUploadedPolicyItem(item) {
  if (!item || typeof item !== "object") {
    return null;
  }
  const id = typeof item.id === "string" ? item.id.trim() : "";
  const title = typeof item.title === "string" ? item.title.trim() : "";
  const contentHtml = typeof item.contentHtml === "string" ? item.contentHtml : "";
  if (!id || !title) {
    return null;
  }
  const contentAvailable = typeof item.contentAvailable === "boolean"
    ? item.contentAvailable
    : Boolean(contentHtml.trim());
  const contentLoaded = typeof item.contentLoaded === "boolean"
    ? item.contentLoaded
    : Boolean(contentHtml.trim());
  return {
    id,
    title,
    type: typeof item.type === "string" && item.type.trim() ? item.type.trim() : "Uploaded policy",
    approver: typeof item.approver === "string" && item.approver.trim() ? item.approver.trim() : "Pending review",
    approvedAt: typeof item.approvedAt === "string" ? item.approvedAt : "",
    approvedBy: typeof item.approvedBy === "string" ? item.approvedBy : "",
    reviewFrequency: typeof item.reviewFrequency === "string" && item.reviewFrequency.trim()
      ? item.reviewFrequency.trim()
      : "Not scheduled",
    path: typeof item.path === "string" && item.path.trim() ? item.path.trim() : "Uploaded file",
    folder: typeof item.folder === "string" && item.folder.trim() ? item.folder.trim() : "Uploaded",
    purpose: typeof item.purpose === "string" ? item.purpose : "",
    contentHtml,
    contentAvailable,
    contentLoaded,
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
  const title = typeof item.title === "string" && item.title.trim() ? item.title.trim() : id;
  if (!id || !title) {
    return null;
  }
  const contentHtml = typeof item.contentHtml === "string" ? item.contentHtml : "";
  const contentAvailable = typeof item.contentAvailable === "boolean"
    ? item.contentAvailable
    : Boolean(contentHtml.trim());
  const contentLoaded = typeof item.contentLoaded === "boolean"
    ? item.contentLoaded
    : Boolean(contentHtml.trim());
  return {
    id,
    title,
    type: typeof item.type === "string" ? item.type : "",
    owner: typeof item.owner === "string" ? item.owner : "",
    approver: typeof item.approver === "string" ? item.approver : "",
    reviewFrequency: typeof item.reviewFrequency === "string" && item.reviewFrequency.trim()
      ? item.reviewFrequency.trim()
      : "Not scheduled",
    path: typeof item.path === "string" ? item.path : "",
    folder: typeof item.folder === "string" ? item.folder : "",
    purpose: typeof item.purpose === "string" ? item.purpose : "",
    contentHtml,
    contentAvailable,
    contentLoaded,
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
  const normalizedMonth = Number.isInteger(parsedMonth) && parsedMonth >= 0 && parsedMonth <= 11
    ? parsedMonth
    : today.getMonth();
  return `m${normalizedMonth}::${normalizedItemId}`;
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
    const isChecked = Boolean(rawValue);
    if (isMonthScopedReviewStateKey(key)) {
      normalized[key] = isChecked;
      return;
    }
    if (!isChecked) {
      return;
    }
    const monthScopedKey = buildReviewStateMonthKey(key, today.getMonth());
    if (monthScopedKey) {
      normalized[monthScopedKey] = true;
    }
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
    if (!key || Number.isNaN(parsed.getTime())) {
      return;
    }
    if (isMonthScopedReviewStateKey(key)) {
      normalized[key] = parsed.toISOString();
      return;
    }
    const monthScopedKey = buildReviewStateMonthKey(key, today.getMonth());
    if (monthScopedKey) {
      normalized[monthScopedKey] = parsed.toISOString();
    }
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
      return {
        id: typeof entry.id === "string" ? entry.id : "",
        action: typeof entry.action === "string" && entry.action.trim() ? entry.action.trim() : "state_changed",
        entityType: typeof entry.entityType === "string" && entry.entityType.trim() ? entry.entityType.trim() : "record",
        entityId: typeof entry.entityId === "string" ? entry.entityId.trim() : "",
        summary: typeof entry.summary === "string" && entry.summary.trim() ? entry.summary.trim() : "State updated.",
        occurredAt: typeof entry.occurredAt === "string" ? entry.occurredAt : "",
        actor: entry.actor && typeof entry.actor === "object"
          ? {
              username: typeof entry.actor.username === "string" ? entry.actor.username.trim() : "",
              displayName: typeof entry.actor.displayName === "string" ? entry.actor.displayName.trim() : "",
            }
          : {},
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
    auditLog: normalizeReviewAuditLogEntries(value.auditLog || value.events),
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
      if (!id || !checklistItem || seenIds.has(id)) {
        return null;
      }
      seenIds.add(id);
      return {
        id,
        category: typeof item.category === "string" && item.category.trim() ? item.category.trim() : "Custom",
        item: checklistItem,
        frequency: typeof item.frequency === "string" && item.frequency.trim() ? item.frequency.trim() : "Annual",
        startDate: normalizeChecklistStartDate(item.startDate),
        owner: typeof item.owner === "string" && item.owner.trim() ? item.owner.trim() : "Shared portal",
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
      if (!username || seen.has(username)) {
        return null;
      }
      seen.add(username);
      const displayName = typeof item.displayName === "string" && item.displayName.trim()
        ? item.displayName.trim()
        : username;
      return { username, displayName };
    })
    .filter(Boolean)
    .sort((left, right) => left.displayName.localeCompare(right.displayName, undefined, { numeric: true, sensitivity: "base" }));
}

function deriveAssignableUsers() {
  const seen = new Set();
  return state.riskRegister
    .map((risk) => (risk && typeof risk.owner === "string" ? risk.owner.trim() : ""))
    .filter((owner) => {
      if (!owner || seen.has(owner)) {
        return false;
      }
      seen.add(owner);
      return true;
    })
    .map((owner) => ({ username: owner, displayName: owner }));
}

function normalizeDataPayload(payload) {
  if (!payload || typeof payload !== "object") {
    return;
  }

  payload.generatedAt = typeof payload.generatedAt === "string" && payload.generatedAt.trim()
    ? payload.generatedAt
    : new Date().toISOString();
  payload.sourceSnapshot = payload.sourceSnapshot && typeof payload.sourceSnapshot === "object"
    ? payload.sourceSnapshot
    : {};

  const summary = payload.summary && typeof payload.summary === "object" ? payload.summary : {};
  payload.summary = {
    ...emptySummary(),
    ...summary,
    domainCounts: summary.domainCounts && typeof summary.domainCounts === "object" ? summary.domainCounts : {},
    documentReviewFrequencies: summary.documentReviewFrequencies && typeof summary.documentReviewFrequencies === "object"
      ? summary.documentReviewFrequencies
      : {},
    checklistFrequencies: summary.checklistFrequencies && typeof summary.checklistFrequencies === "object"
      ? summary.checklistFrequencies
      : {},
  };

  payload.controls = Array.isArray(payload.controls) ? payload.controls : [];
  payload.documents = Array.isArray(payload.documents) ? payload.documents : [];
  payload.activities = Array.isArray(payload.activities) ? payload.activities : [];
  payload.checklist = Array.isArray(payload.checklist) ? payload.checklist : [];
  payload.policyCoverage = Array.isArray(payload.policyCoverage) ? payload.policyCoverage : [];
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
  try {
    const payload = await apiRequest(`/state/?page=${encodeURIComponent(page)}`);
    applyRemoteState(payload);
  } catch (error) {
    console.error("Failed to load portal state from the API.", error);
  }
}

function applyRemoteState(payload) {
  if (!payload || typeof payload !== "object") {
    return;
  }

  if (payload.mapping && typeof payload.mapping === "object") {
    const remoteControls = Array.isArray(payload.mapping.controls) ? payload.mapping.controls : [];
    if (remoteControls.length) {
      applyMappingPayload(payload.mapping);
    }
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
    const assignableUsers = normalizeAssignableUsers(payload.assignableUsers);
    if (assignableUsers.length) {
      state.assignableUsers = assignableUsers;
    }
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
    const fallbackErrorMessage = messages && typeof messages.error === "function"
      ? messages.error(error)
      : messages && Object.prototype.hasOwnProperty.call(messages, "error")
        ? messages.error
        : "";
    const detail = error instanceof Error && error.message
      ? error.message
      : fallbackErrorMessage || "Operation failed.";
    if (typeof setStatus === "function") {
      setStatus(detail, "error");
    }
    throw error;
  }
}
