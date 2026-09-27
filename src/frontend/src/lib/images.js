/**
 * Item images come in two kinds: photos of the object ("foto") and scanned
 * paper documents such as data sheets, lists or invoices ("scan").
 * Images without a kind (older API responses) count as photos.
 */

export function isScan(image) {
  return image?.kind === "scan";
}

/** Split an image list into { photos, scans }, keeping the original order. */
export function splitImages(images) {
  const photos = [];
  const scans = [];
  for (const img of images || []) {
    (isScan(img) ? scans : photos).push(img);
  }
  return { photos, scans };
}

/** Human-readable title for a scan: its caption, or a numbered fallback. */
export function scanTitle(scan, index) {
  const caption = scan?.caption?.trim();
  return caption || `Scan ${index + 1}`;
}
