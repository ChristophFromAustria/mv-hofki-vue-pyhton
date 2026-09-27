/** Selection helpers: rows may repeat an item across groups, ids do not. */
export function toggleId(ids, id) {
  return ids.includes(id) ? ids.filter((x) => x !== id) : [...ids, id];
}

export function uniqueIds(rows) {
  return [...new Set(rows.map((r) => r.id))];
}

/** Adds every loaded row's id to an existing selection (union, not replace). */
export function mergeIds(ids, rows) {
  return [...new Set([...ids, ...uniqueIds(rows)])];
}
