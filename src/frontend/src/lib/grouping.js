/**
 * Interleave group headers into list rows (rows arrive sorted by group from
 * the API). Counts come from the API's `groups`, so they are right even while
 * only part of a group is loaded.
 */
export function buildSegments(rows, groups, collapsed) {
  if (!groups) return rows.map((row) => ({ type: "row", key: row._key ?? row.id, row }));
  const byKey = new Map(groups.map((g) => [g.key, g]));
  const out = [];
  let current;
  for (const row of rows) {
    const groupKey = row.group_key ?? "";
    if (groupKey !== current) {
      current = groupKey;
      const g = byKey.get(groupKey);
      out.push({
        type: "group",
        key: `group:${groupKey}`,
        groupKey,
        label: g?.label ?? row.group_label ?? "",
        count: g?.count ?? null,
        collapsed: collapsed.has(groupKey),
      });
    }
    if (!collapsed.has(groupKey)) out.push({ type: "row", key: row._key ?? row.id, row });
  }
  return out;
}
