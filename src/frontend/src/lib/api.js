/**
 * Thin fetch wrapper for API calls.
 *
 * - Prepends the base path + /api/v1 to all requests
 * - Handles JSON serialization/deserialization
 * - Placeholder for auth token header
 */

const BASE = (import.meta.env.VITE_BASE_PATH || "").replace(/\/$/, "");
const API_PREFIX = `${BASE}/api/v1`;

// Turns FastAPI's "detail" field into a human-readable string. It is either a
// plain string, or (on a pydantic 422) a list of {loc, msg, type} objects.
function detailToMessage(text) {
  let detail = text;
  try {
    const json = JSON.parse(text);
    if (json.detail) detail = json.detail;
  } catch {
    // keep raw text
  }
  if (Array.isArray(detail)) {
    return (
      detail
        .map((entry) => (entry && entry.msg) || JSON.stringify(entry))
        // pydantic prefixes a raised ValueError's message with "Value error, ".
        .map((msg) => msg.replace(/^Value error,\s*/, ""))
        .join("; ")
    );
  }
  return detail;
}

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
    throw new Error(detailToMessage(text));
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

/**
 * Every item of a paginated list endpoint ({items, total}), fetched page by page.
 * Use for pickers and histories that must not be cut off.
 */
export async function getAll(path, pageSize = 200) {
  const sep = path.includes("?") ? "&" : "?";
  const all = [];
  for (;;) {
    const page = await get(`${path}${sep}limit=${pageSize}&offset=${all.length}`);
    all.push(...page.items);
    if (!page.items.length || all.length >= page.total) return all;
  }
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

/** POST multipart/form-data (file uploads). `formData` is a FormData instance. */
export async function postForm(path, formData) {
  const response = await fetch(`${API_PREFIX}${path}`, { method: "POST", body: formData });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(detailToMessage(text));
  }
  return response.json();
}

/** PUT multipart/form-data (replacing an uploaded file). */
export async function putForm(path, formData) {
  const response = await fetch(`${API_PREFIX}${path}`, { method: "PUT", body: formData });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(detailToMessage(text));
  }
  return response.json();
}

export { API_PREFIX, BASE };
