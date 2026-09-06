/**
 * Shared ordering for scan projects so the list page and the
 * prev/next navigation on the detail page agree on what "next" means.
 */

export function compareByCatalogNumber(a, b) {
  const na = a.catalog_number ?? Infinity;
  const nb = b.catalog_number ?? Infinity;
  return na - nb || a.name.localeCompare(b.name, "de");
}

export function compareByName(a, b) {
  return a.name.localeCompare(b.name, "de");
}

export function sortProjects(projects, sortBy = "catalog_number") {
  const cmp = sortBy === "name" ? compareByName : compareByCatalogNumber;
  return [...projects].sort(cmp);
}
