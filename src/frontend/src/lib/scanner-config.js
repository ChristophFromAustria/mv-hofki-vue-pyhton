/**
 * Scanner config field definitions.
 *
 * Each entry describes one backend config field so the UI can auto-generate
 * the settings form.  To add a new field, add one object here — no template
 * changes needed.
 */

export const SCANNER_CONFIG_FIELDS = [
  // ── Template Matching ──────────────────────────────────────────────
  {
    key: "confidence_threshold",
    label: "Konfidenz-Schwellwert",
    group: "Template Matching",
    type: "number",
    min: 0,
    max: 1,
    step: 0.05,
  },
  {
    key: "matching_method",
    label: "Matching-Methode",
    group: "Template Matching",
    type: "select",
    options: [
      { value: "TM_CCOEFF_NORMED", label: "Kreuzkorrelationskoeffizient (Standard)" },
      { value: "TM_CCORR_NORMED", label: "Kreuzkorrelation" },
      { value: "TM_SQDIFF_NORMED", label: "Quadratische Differenz" },
    ],
  },
  {
    key: "auto_verify_confidence",
    label: "Auto-Verifizierung ab",
    group: "Template Matching",
    type: "number",
    min: 0,
    max: 1,
    step: 0.05,
  },

  // ── Multi-Scale ────────────────────────────────────────────────────
  {
    key: "multi_scale_enabled",
    label: "Multi-Scale-Suche",
    group: "Multi-Scale",
    type: "toggle",
  },
  {
    key: "multi_scale_range",
    label: "Suchbereich (+/-)",
    group: "Multi-Scale",
    type: "number",
    min: 0.01,
    max: 0.5,
    step: 0.01,
  },
  {
    key: "multi_scale_steps",
    label: "Stufen",
    group: "Multi-Scale",
    type: "number",
    min: 1,
    max: 20,
    step: 1,
  },

  // ── Edge-Based Matching ────────────────────────────────────────────
  {
    key: "edge_matching_enabled",
    label: "Kanten-Matching",
    group: "Kanten-Matching",
    type: "toggle",
  },
  {
    key: "canny_low",
    label: "Canny unterer Schwellwert",
    group: "Kanten-Matching",
    type: "number",
    min: 0,
    max: 500,
    step: 10,
  },
  {
    key: "canny_high",
    label: "Canny oberer Schwellwert",
    group: "Kanten-Matching",
    type: "number",
    min: 0,
    max: 500,
    step: 10,
  },

  // ── Staff Removal ──────────────────────────────────────────────────
  {
    key: "staff_removal_before_matching",
    label: "Notenlinien vor Matching entfernen",
    group: "Notenlinien-Entfernung",
    type: "toggle",
  },

  // ── Dewarp (bent staff lines) ────────────────────────────────────────
  {
    key: "dewarp_enabled",
    label: "Krümmungskorrektur",
    group: "Krümmungskorrektur",
    type: "toggle",
  },
  {
    key: "dewarp_smoothing",
    label: "Glättung (px)",
    group: "Krümmungskorrektur",
    type: "number",
    min: 5,
    max: 200,
    step: 5,
  },

  // ── Masked Matching ────────────────────────────────────────────────
  {
    key: "masked_matching_enabled",
    label: "Maskiertes Matching",
    group: "Maskiertes Matching",
    type: "toggle",
  },
  {
    key: "mask_threshold",
    label: "Masken-Schwellwert",
    group: "Maskiertes Matching",
    type: "number",
    min: 0,
    max: 255,
    step: 5,
  },

  // ── NMS ────────────────────────────────────────────────────────────
  {
    key: "nms_iou_threshold",
    label: "NMS IoU-Schwellwert",
    group: "Non-Maximum Suppression",
    type: "number",
    min: 0,
    max: 1,
    step: 0.05,
  },
  {
    key: "nms_method",
    label: "NMS-Methode",
    group: "Non-Maximum Suppression",
    type: "select",
    options: [
      { value: "standard", label: "Standard (IoU)" },
      { value: "dilate", label: "Dilate (Proximity)" },
    ],
  },

  // ── Preprocessing ──────────────────────────────────────────────────
  {
    key: "adaptive_threshold_block_size",
    label: "Adaptiver Schwellwert Blockgr.",
    group: "Vorverarbeitung",
    type: "number",
    min: 3,
    max: 99,
    step: 2,
  },
  {
    key: "adaptive_threshold_c",
    label: "Adaptiver Schwellwert Konstante",
    group: "Vorverarbeitung",
    type: "number",
    min: 0,
    max: 50,
    step: 1,
  },
  {
    key: "morphology_kernel_size",
    label: "Morphologie-Kerngr.",
    group: "Vorverarbeitung",
    type: "number",
    min: 1,
    max: 10,
    step: 1,
  },
  {
    key: "deskew_method",
    label: "Deskew-Methode",
    group: "Vorverarbeitung",
    type: "select",
    options: [
      { value: "none", label: "Keine Korrektur" },
      { value: "hough", label: "Hough-Linien (schnell)" },
      { value: "projection", label: "Projektions-Optimierung (genau)" },
    ],
  },
];

/**
 * Group fields by their `group` property, preserving definition order.
 */
export function groupedFields() {
  const groups = [];
  const seen = new Map();
  for (const field of SCANNER_CONFIG_FIELDS) {
    if (!seen.has(field.group)) {
      const entry = { label: field.group, fields: [] };
      seen.set(field.group, entry);
      groups.push(entry);
    }
    seen.get(field.group).fields.push(field);
  }
  return groups;
}
