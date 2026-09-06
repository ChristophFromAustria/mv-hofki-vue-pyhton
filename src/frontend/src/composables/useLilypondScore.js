/**
 * LilyPond score of a scan: current code, rendered files and the actions
 * that change them (generate from the analysis, render an edited version,
 * discard the edited version).
 */
import { ref } from "vue";
import { post } from "../lib/api.js";

export function useLilypondScore(scanId) {
  const code = ref("");
  const pdfPath = ref(null);
  const pngPaths = ref([]);
  const warnings = ref([]);
  /** "analysis" = generated from the scan, "edited" = saved editor version */
  const source = ref("analysis");
  const editedAt = ref(null);
  const generating = ref(false);
  const rendering = ref(false);
  const error = ref(null);
  /** Increases with every render result so cached PNG/PDF get reloaded. */
  const renderStamp = ref(0);

  function applyResult(result, fallbackSource) {
    code.value = result.lilypond_code;
    pdfPath.value = result.pdf_path;
    pngPaths.value = result.png_paths || [];
    warnings.value = result.warnings || [];
    source.value = result.source || fallbackSource;
    editedAt.value = result.edited_at || null;
    renderStamp.value = Date.now();
  }

  /**
   * Current score: the saved editor version if there is one, otherwise the
   * code generated from the analysis. `reset` discards the editor version.
   */
  async function generate(reset = false) {
    if (generating.value) return false;
    generating.value = true;
    error.value = null;
    try {
      const query = reset ? "?reset=true" : "";
      const result = await post(`/scanner/scans/${scanId}/generate-lilypond${query}`);
      applyResult(result, "analysis");
      return true;
    } catch (e) {
      error.value = e.message;
      return false;
    } finally {
      generating.value = false;
    }
  }

  /** Save edited code as the scan's version and render PDF + preview. */
  async function renderEdited(editedCode) {
    if (rendering.value) return false;
    rendering.value = true;
    error.value = null;
    try {
      const result = await post(`/scanner/scans/${scanId}/render-lilypond`, {
        lilypond_code: editedCode,
      });
      applyResult(result, "edited");
      return true;
    } catch (e) {
      error.value = e.message;
      return false;
    } finally {
      rendering.value = false;
    }
  }

  return {
    code,
    pdfPath,
    pngPaths,
    warnings,
    source,
    editedAt,
    generating,
    rendering,
    error,
    renderStamp,
    generate,
    renderEdited,
  };
}
