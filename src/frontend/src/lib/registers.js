/**
 * Helpers for the register (Stimmgruppe) administration page.
 */

/** Sort registers by sort_order, then label (de-AT collation). */
export function sortRegisters(registers) {
  return [...(registers || [])].sort(
    (a, b) =>
      (a.sort_order ?? 0) - (b.sort_order ?? 0) ||
      String(a.label).localeCompare(String(b.label), "de-AT"),
  );
}

/**
 * Move the register at `index` by `delta` (-1 up, +1 down) and return the
 * updates needed to persist the new order: [{ id, sort_order }] for every
 * register whose position value changes. Positions are renumbered in steps of
 * 10 so later inserts fit in between. Returns [] if the move is not possible.
 */
export function reorderUpdates(registers, index, delta) {
  const list = sortRegisters(registers);
  const target = index + delta;
  if (index < 0 || index >= list.length || target < 0 || target >= list.length) return [];
  const [moved] = list.splice(index, 1);
  list.splice(target, 0, moved);
  const updates = [];
  list.forEach((r, i) => {
    const order = (i + 1) * 10;
    if (r.sort_order !== order) updates.push({ id: r.id, sort_order: order });
  });
  return updates;
}

/** Next free sort_order for a new register (appended at the end). */
export function nextSortOrder(registers) {
  const max = Math.max(0, ...(registers || []).map((r) => r.sort_order ?? 0));
  return Math.ceil((max + 1) / 10) * 10;
}
