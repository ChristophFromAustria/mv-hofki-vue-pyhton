/**
 * Thin fetch wrapper for API calls.
 *
 * - Prepends the base path + /api/v1 to all requests
 * - Handles JSON serialization/deserialization
 * - Placeholder for auth token header
 */

const BASE = (import.meta.env.VITE_BASE_PATH || "").replace(/\/$/, "");
const API_PREFIX = `${BASE}/api/v1`;

async function request(method, path, body = null) {
  const url = `${API_PREFIX}${path}`;
  const headers = {
    "Content-Type": "application/json",
    // Placeholder: attach auth token here
    // "Authorization": `Bearer ${getToken()}`,
  };

  const options = { method, headers };
  if (body !== null) {
    options.body = JSON.stringify(body);
  }

  const response = await fetch(url, options);
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`API ${method} ${path} failed (${response.status}): ${text}`);
  }

  const contentType = response.headers.get("content-type");
  if (contentType && contentType.includes("application/json")) {
    return response.json();
  }
  return response.text();
}

export function get(path) {
  return request("GET", path);
}

export function post(path, body) {
  return request("POST", path, body);
}

export function put(path, body) {
  return request("PUT", path, body);
}

export function del(path) {
  return request("DELETE", path);
}
