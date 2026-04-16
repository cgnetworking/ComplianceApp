function resolveApiBaseUrl() {
  if (window.ISMS_PORTAL_CONFIG && typeof window.ISMS_PORTAL_CONFIG.apiBaseUrl === "string") {
    return window.ISMS_PORTAL_CONFIG.apiBaseUrl.replace(/\/+$/, "");
  }
  return "/api";
}

function resolveLoginUrl() {
  if (window.ISMS_PORTAL_CONFIG && typeof window.ISMS_PORTAL_CONFIG.loginUrl === "string") {
    return window.ISMS_PORTAL_CONFIG.loginUrl;
  }
  return "/login/";
}

async function apiRequest(path, options) {
  const requestOptions = options || {};
  const method = requestOptions.method || "GET";
  const headers = new Headers(requestOptions.headers || {});
  const isFormData = typeof FormData !== "undefined" && requestOptions.body instanceof FormData;

  if (!headers.has("Accept")) {
    headers.set("Accept", "application/json");
  }
  if (requestOptions.body && !isFormData && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const csrfToken = readCookie("csrftoken");
  if (csrfToken && !/^(GET|HEAD|OPTIONS|TRACE)$/i.test(method)) {
    headers.set("X-CSRFToken", csrfToken);
  }

  const response = await fetch(`${resolveApiBaseUrl()}${path}`, {
    ...requestOptions,
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
  let payload = null;
  if (responseText) {
    try {
      payload = JSON.parse(responseText);
    } catch (error) {
      payload = null;
    }
  }

  if (!response.ok) {
    throw new Error((payload && (payload.detail || payload.message)) || `Request failed (${response.status}).`);
  }

  return payload;
}

function readCookie(name) {
  const escapedName = name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const match = document.cookie.match(new RegExp(`(?:^|; )${escapedName}=([^;]*)`));
  return match ? decodeURIComponent(match[1]) : "";
}
