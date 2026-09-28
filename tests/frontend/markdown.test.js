import { describe, it, expect } from "vitest";
import { renderMarkdown } from "../../src/frontend/src/lib/markdown.js";

describe("renderMarkdown", () => {
  it("renders bold, italic, lists and headings", () => {
    expect(renderMarkdown("**fett**")).toContain("<strong>fett</strong>");
    expect(renderMarkdown("*kursiv*")).toContain("<em>kursiv</em>");
    expect(renderMarkdown("- eins\n- zwei")).toContain("<li>eins</li>");
    expect(renderMarkdown("## Titel")).toContain("<h2>Titel</h2>");
  });

  it("escapes raw HTML and never produces a script or img tag", () => {
    const out = renderMarkdown("<script>alert(1)</script>");
    expect(out).not.toContain("<script>");
    expect(out).toContain("&lt;script&gt;");

    const imgOut = renderMarkdown('<img src=x onerror="alert(1)">');
    expect(imgOut).not.toContain("<img");
  });

  it("turns single newlines into <br> (breaks: true)", () => {
    expect(renderMarkdown("Zeile 1\nZeile 2")).toContain("Zeile 1<br>\nZeile 2");
  });

  it("linkifies bare URLs and adds target/rel to links", () => {
    const out = renderMarkdown("https://example.com");
    expect(out).toContain('href="https://example.com"');
    expect(out).toContain('target="_blank"');
    expect(out).toContain('rel="noopener noreferrer"');
  });

  it("adds target/rel to markdown link syntax too", () => {
    const out = renderMarkdown("[Text](https://example.com)");
    expect(out).toContain('target="_blank"');
    expect(out).toContain('rel="noopener noreferrer"');
  });

  it("returns empty string for empty/null input", () => {
    expect(renderMarkdown(null)).toBe("");
    expect(renderMarkdown(undefined)).toBe("");
    expect(renderMarkdown("")).toBe("");
  });
});
