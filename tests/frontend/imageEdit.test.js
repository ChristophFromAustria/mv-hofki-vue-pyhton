import { describe, it, expect } from "vitest";
import {
  autoLevels,
  buildLuts,
  clampCrop,
  cropPixels,
  isNeutral,
  neutralEdit,
  rotatedSize,
} from "../../src/frontend/src/lib/imageEdit.js";

function pixels(list) {
  const data = new Uint8ClampedArray(list.length * 4);
  list.forEach(([r, g, b], i) => data.set([r, g, b, 255], i * 4));
  return { data, width: list.length, height: 1 };
}

describe("imageEdit", () => {
  it("auto levels find each channel's real range (washed-out scan)", () => {
    // A pale, slightly yellow scan: everything between 150 and 250.
    const img = pixels(Array.from({ length: 200 }, (_, i) => [200 + (i % 50), 190 + (i % 60), 150 + (i % 100)]));
    const levels = autoLevels(img, 0);
    expect(levels.gamma).toBeGreaterThan(0.5);
    expect(levels.r).toEqual([200, 249]);
    expect(levels.g).toEqual([190, 249]);
    expect(levels.b).toEqual([150, 249]);
    // A flat channel stays as it is.
    expect(autoLevels(pixels([[10, 10, 10], [12, 10, 10]]), 0).g).toEqual([0, 255]);
  });

  it("levels stretch a channel to the full range", () => {
    const luts = buildLuts({ ...neutralEdit(), levels: { r: [200, 250], g: [0, 255], b: [0, 255] } });
    expect(luts.r[200]).toBe(0);
    expect(luts.r[250]).toBe(255);
    expect(luts.r[225]).toBe(128);
    expect(luts.g[100]).toBe(100);
  });

  it("brightness, contrast and warmth", () => {
    expect(buildLuts(neutralEdit()).r[123]).toBe(123);
    // Brightness bends the midtones; black and white stay.
    const darker = buildLuts({ ...neutralEdit(), brightness: -50 }).r;
    expect(darker[128]).toBeLessThan(100);
    expect(darker[0]).toBe(0);
    expect(darker[255]).toBe(255);
    const contrast = buildLuts({ ...neutralEdit(), contrast: 50 }).r;
    expect(contrast[200]).toBeGreaterThan(200);
    expect(contrast[50]).toBeLessThan(50);
    const warm = buildLuts({ ...neutralEdit(), warmth: 100 });
    expect(warm.r[150]).toBeGreaterThan(150);
    expect(warm.b[150]).toBeLessThan(150);
  });

  it("geometry", () => {
    expect(rotatedSize(400, 300, 90)).toEqual({ w: 300, h: 400 });
    expect(rotatedSize(400, 300, 180)).toEqual({ w: 400, h: 300 });
    expect(cropPixels(null, 400, 300)).toEqual({ x: 0, y: 0, w: 400, h: 300 });
    expect(cropPixels({ x: 0.25, y: 0.5, w: 0.5, h: 0.5 }, 400, 300)).toEqual({ x: 100, y: 150, w: 200, h: 150 });
    expect(clampCrop({ x: 0.9, y: -0.2, w: 0.5, h: 0.01 })).toEqual({ x: 0.5, y: 0, w: 0.5, h: 0.05 });
  });

  it("knows when nothing was changed", () => {
    expect(isNeutral(neutralEdit())).toBe(true);
    expect(isNeutral({ ...neutralEdit(), rotate: 90 })).toBe(false);
    expect(isNeutral({ ...neutralEdit(), levels: { r: [0, 255] } })).toBe(false);
  });
});

describe("auto midtones", () => {
  it("darkens an overexposed scan with a white border towards a natural mean", () => {
    // 10 % white border, the rest bright (around 210-235).
    const list = [
      ...Array.from({ length: 20 }, () => [255, 255, 255]),
      ...Array.from({ length: 180 }, (_, i) => [210 + (i % 25), 205 + (i % 25), 200 + (i % 25)]),
      ...Array.from({ length: 4 }, () => [20, 20, 20]),
    ];
    const levels = autoLevels(pixels(list));
    expect(levels.gamma).toBe(1.6); // > 1 darkens midtones; capped
    const luts = buildLuts({ ...neutralEdit(), levels });
    expect(luts.g[220]).toBeLessThan(200);
    expect(luts.g[255]).toBe(255);
  });
});
