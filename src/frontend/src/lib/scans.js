/**
 * Scan access shared by the analysis page, the LilyPond editor page and the
 * project detail page.
 */
import { get, put } from "./api.js";

const BASE = (import.meta.env.VITE_BASE_PATH || "").replace(/\/$/, "");

/** Scan record by id alone (no project/part path needed). */
export function fetchScan(scanId) {
  return get(`/scanner/scans/${scanId}`);
}

/** Persist per-scan adjustments (preprocessing + analysis/layout overrides). */
export function saveScanAdjustments(scanId, adjustments) {
  return put(`/scanner/scans/${scanId}`, {
    adjustments_json: JSON.stringify(adjustments),
  });
}

export function parseAdjustments(adjustmentsJson, fallback = {}) {
  if (!adjustmentsJson) return fallback;
  try {
    return JSON.parse(adjustmentsJson);
  } catch {
    return fallback;
  }
}

/**
 * URL of a file in the scan directory (image, PDF, PNG preview).
 * `cacheBust` forces the browser to reload a file whose path never changes.
 */
export function scanAssetUrl(path, cacheBust = null) {
  if (!path) return null;
  const relative = path.replace(/^data\/scans\//, "");
  const url = `${BASE}/scans/${relative}`;
  return cacheBust ? `${url}?v=${cacheBust}` : url;
}
