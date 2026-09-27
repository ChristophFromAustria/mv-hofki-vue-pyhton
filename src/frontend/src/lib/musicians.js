/**
 * Helpers for musician display.
 */

/** Comma-separated register labels of a musician, "—" when none. */
export function registerLabels(musician) {
  const regs = musician?.registers || [];
  return regs.length ? regs.map((r) => r.label).join(", ") : "—";
}
