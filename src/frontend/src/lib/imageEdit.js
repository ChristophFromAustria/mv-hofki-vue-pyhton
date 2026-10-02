/**
 * Image editing for ImageEditor.vue: rotate, crop and colour adjustments,
 * done on a canvas in the browser. Colour work goes through one lookup table
 * per channel (levels → midtones → white balance → brightness → contrast), so
 * the full image is a single pass over its pixels.
 */

/** Edit parameters; crop is { x, y, w, h } in 0..1 of the rotated image. */
export function neutralEdit() {
  return {
    rotate: 0, // 0 | 90 | 180 | 270, clockwise
    crop: null,
    brightness: 0, // -100..100
    contrast: 0, // -100..100
    warmth: 0, // -100 (cooler, bluer) .. 100 (warmer, yellower)
    // From autoLevels: { r: [lo, hi], g: [lo, hi], b: [lo, hi], gamma }.
    levels: null,
  };
}

export function isNeutral(edit) {
  const n = neutralEdit();
  return (
    edit.rotate === n.rotate &&
    !edit.crop &&
    !edit.brightness &&
    !edit.contrast &&
    !edit.warmth &&
    !edit.levels
  );
}

// Target mean brightness (0..1) of "Automatisch": a little below the middle.
const AUTO_MEAN = 0.46;

/**
 * Per channel, the values below/above which `clip` of the pixels lie, and a
 * midtone gamma. Stretching each channel to its range restores contrast and,
 * channel by channel, removes a colour cast; the gamma moves the mean
 * brightness towards AUTO_MEAN (within 0.7..1.6) — what overexposed scans
 * (bright midtones, white scanner borders) need most.
 */
export function autoLevels(imageData, clip = 0.01) {
  const { data } = imageData;
  const hist = [new Uint32Array(256), new Uint32Array(256), new Uint32Array(256)];
  for (let i = 0; i < data.length; i += 4) {
    hist[0][data[i]]++;
    hist[1][data[i + 1]]++;
    hist[2][data[i + 2]]++;
  }
  const total = data.length / 4;
  const cut = Math.max(1, Math.round(total * clip));
  const range = (h) => {
    let lo = 0;
    for (let n = 0; lo < 255 && n + h[lo] < cut; lo++) n += h[lo];
    let hi = 255;
    for (let n = 0; hi > 0 && n + h[hi] < cut; hi--) n += h[hi];
    if (hi - lo < 16) return [0, 255]; // (almost) flat channel: leave it
    return [lo, hi];
  };
  const levels = { r: range(hist[0]), g: range(hist[1]), b: range(hist[2]) };
  // Mean brightness after stretching (luma of the channel means).
  const mean = (h, [lo, hi]) => {
    let sum = 0;
    for (let v = 0; v < 256; v++) sum += h[v] * Math.min(1, Math.max(0, (v - lo) / (hi - lo)));
    return sum / total;
  };
  const luma =
    0.299 * mean(hist[0], levels.r) +
    0.587 * mean(hist[1], levels.g) +
    0.114 * mean(hist[2], levels.b);
  const gamma = luma > 0.02 && luma < 0.98 ? Math.log(AUTO_MEAN) / Math.log(luma) : 1;
  // Moderate on purpose: documents are bright by nature and only need their
  // text a little stronger; more is up to the brightness slider.
  return { ...levels, gamma: Math.min(1.6, Math.max(0.7, gamma)) };
}

/** Three 256-entry lookup tables for the colour parameters of `edit`. */
export function buildLuts(edit) {
  const c = (edit.contrast || 0) * 2.55;
  const factor = (259 * (c + 255)) / (255 * (259 - c));
  // Brightness as a midtone curve (black and white stay): -100 → γ 2, +100 → γ 0.5.
  const gamma = (edit.levels?.gamma || 1) * 2 ** (-(edit.brightness || 0) / 100);
  const warm = (edit.warmth || 0) / 100;
  const gains = { r: 1 + 0.18 * warm, g: 1 + 0.04 * warm, b: 1 - 0.18 * warm };
  const out = {};
  for (const ch of ["r", "g", "b"]) {
    const [lo, hi] = edit.levels?.[ch] || [0, 255];
    const lut = new Uint8ClampedArray(256);
    for (let v = 0; v < 256; v++) {
      const t = Math.min(1, Math.max(0, (v - lo) / (hi - lo)));
      let x = 255 * t ** gamma;
      x *= gains[ch];
      x = factor * (x - 128) + 128;
      lut[v] = x; // Uint8ClampedArray clamps and rounds
    }
    out[ch] = lut;
  }
  return out;
}

export function applyLuts(imageData, luts) {
  const { data } = imageData;
  const { r, g, b } = luts;
  for (let i = 0; i < data.length; i += 4) {
    data[i] = r[data[i]];
    data[i + 1] = g[data[i + 1]];
    data[i + 2] = b[data[i + 2]];
  }
  return imageData;
}

/** Size of an image of w × h after rotating it by `rotate` degrees. */
export function rotatedSize(w, h, rotate) {
  return rotate % 180 === 0 ? { w, h } : { w: h, h: w };
}

/** The crop in pixels of a rotated image of w × h (whole image if none). */
export function cropPixels(crop, w, h) {
  if (!crop) return { x: 0, y: 0, w, h };
  const x = Math.round(crop.x * w);
  const y = Math.round(crop.y * h);
  return {
    x,
    y,
    w: Math.max(1, Math.min(w - x, Math.round(crop.w * w))),
    h: Math.max(1, Math.min(h - y, Math.round(crop.h * h))),
  };
}

/** Keep a crop inside the image and at least `min` (0..1) large. */
export function clampCrop(crop, min = 0.05) {
  const w = Math.min(1, Math.max(min, crop.w));
  const h = Math.min(1, Math.max(min, crop.h));
  return {
    x: Math.min(1 - w, Math.max(0, crop.x)),
    y: Math.min(1 - h, Math.max(0, crop.y)),
    w,
    h,
  };
}

function canvas(w, h) {
  const c = document.createElement("canvas");
  c.width = w;
  c.height = h;
  return c;
}

/**
 * Render `source` (an image or canvas) with `edit` onto a new canvas, the
 * long side at most `maxSide` px. withCrop=false shows the whole rotated
 * image (while choosing the crop).
 */
export function renderEdit(source, edit, { maxSide = 1200, withCrop = true } = {}) {
  const sw = source.naturalWidth || source.width;
  const sh = source.naturalHeight || source.height;
  const rot = rotatedSize(sw, sh, edit.rotate);
  const area = withCrop ? cropPixels(edit.crop, rot.w, rot.h) : { x: 0, y: 0, ...rot };
  const scale = Math.min(1, maxSide / Math.max(area.w, area.h));

  // Rotate the part of the image that is shown into a canvas of its size.
  const out = canvas(
    Math.max(1, Math.round(area.w * scale)),
    Math.max(1, Math.round(area.h * scale)),
  );
  const ctx = out.getContext("2d", { willReadFrequently: true });
  ctx.imageSmoothingQuality = "high";
  ctx.scale(scale, scale);
  ctx.translate(-area.x, -area.y);
  ctx.translate(rot.w / 2, rot.h / 2);
  ctx.rotate((edit.rotate * Math.PI) / 180);
  ctx.drawImage(source, -sw / 2, -sh / 2);

  const luts = buildLuts(edit);
  const identity = !edit.levels && !edit.brightness && !edit.contrast && !edit.warmth;
  if (!identity) {
    const data = ctx.getImageData(0, 0, out.width, out.height);
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.putImageData(applyLuts(data, luts), 0, 0);
  }
  return out;
}

/** The edited image as a JPEG blob (long side at most maxSide). */
export function exportEdit(source, edit, { maxSide = 3000, quality = 0.9 } = {}) {
  const out = renderEdit(source, edit, { maxSide, withCrop: true });
  return new Promise((resolve, reject) => {
    out.toBlob(
      (blob) => (blob ? resolve(blob) : reject(new Error("Bild konnte nicht erzeugt werden"))),
      "image/jpeg",
      quality,
    );
  });
}
