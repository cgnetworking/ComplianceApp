function resolveApiBaseUrl() {
  if (!window.ISMS_PORTAL_CONFIG || typeof window.ISMS_PORTAL_CONFIG.apiBaseUrl !== "string") {
    throw new Error("Portal API base URL is not configured.");
  }
  return window.ISMS_PORTAL_CONFIG.apiBaseUrl.replace(/\/+$/, "");
}

function resolveLoginUrl() {
  if (!window.ISMS_PORTAL_CONFIG || typeof window.ISMS_PORTAL_CONFIG.loginUrl !== "string") {
    throw new Error("Portal login URL is not configured.");
  }
  return window.ISMS_PORTAL_CONFIG.loginUrl;
}

async function apiRequest(path, options = {}) {
  const method = typeof options.method === "string" ? options.method : "GET";
  const headers = new Headers(options.headers || {});
  const isFormData = typeof FormData !== "undefined" && options.body instanceof FormData;

  if (!headers.has("Accept")) {
    headers.set("Accept", "application/json");
  }
  if (options.body && !isFormData && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const csrfToken = readCookie("csrftoken");
  if (csrfToken && !/^(GET|HEAD|OPTIONS|TRACE)$/i.test(method)) {
    headers.set("X-CSRFToken", csrfToken);
  }

  const response = await fetch(`${resolveApiBaseUrl()}${path}`, {
    ...options,
    method,
    headers,
    credentials: "same-origin",
  });

  if (response.status === 401) {
    const next = `${window.location.pathname}${window.location.search}`;
    window.location.href = `${resolveLoginUrl()}?next=${encodeURIComponent(next)}`;
    throw new Error("Authentication required.");
  }

  const responseText = await response.text();
  let returnValue = null;
  if (responseText) {
    try {
      returnValue = JSON.parse(responseText);
    } catch (error) {
      throw new Error("API response was not valid JSON.");
    }
  }

  if (!response.ok) {
    const detail = returnValue && (returnValue.detail || returnValue.message);
    throw new Error(typeof detail === "string" && detail.trim() ? detail : `Request failed (${response.status}).`);
  }

  return returnValue;
}

function readCookie(name) {
  const escapedName = name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const match = document.cookie.match(new RegExp(`(?:^|; )${escapedName}=([^;]*)`));
  return match ? decodeURIComponent(match[1]) : "";
}
