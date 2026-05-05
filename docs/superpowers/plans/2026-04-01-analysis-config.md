# Analysis Config Migration & DB Cleanup — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enable scan-specific analysis config stored in `adjustments_json.analysis` with a toggle to switch between global and per-scan settings. Remove dead DB columns and the broken session-config system.

**Architecture:** Backend gets a shared `merge_scan_adjustments()` helper that merges global config with scan-level preprocessing + analysis overrides. Frontend config modal gains a scan-specific mode with toggle. Dead columns removed via Alembic migration.

**Tech Stack:** FastAPI, SQLAlchemy/Alembic, Vue 3

---

### Task 1: Extract `merge_scan_adjustments` helper and add analysis merge

**Files:**
- Modify: `src/backend/mv_hofki/services/sheet_music_scan.py:196-207,360-372`
- Create: `tests/backend/test_config_merge.py`

- [ ] **Step 1: Write the test**

Create `tests/backend/test_config_merge.py`:

```python
"""Tests for merge_scan_adjustments helper."""

import json

from mv_hofki.services.sheet_music_scan import merge_scan_adjustments


def test_preprocessing_values_override_config():
    config = {"brightness": 0, "contrast": 1.0, "morphology_kernel_size": 2}
    adj = json.dumps({"preprocessing": {"brightness": 10, "contrast": 1.5}})
    result = merge_scan_adjustments(config, adj)
    assert result["brightness"] == 10
    assert result["contrast"] == 1.5
    assert result["morphology_kernel_size"] == 2


def test_analysis_enabled_overrides_config():
    config = {"confidence_threshold": 0.6, "matching_method": "TM_CCOEFF_NORMED"}
    adj = json.dumps({
        "analysis": {
            "enabled": True,
            "confidence_threshold": 0.8,
            "matching_method": "TM_SQDIFF_NORMED",
        }
    })
    result = merge_scan_adjustments(config, adj)
    assert result["confidence_threshold"] == 0.8
    assert result["matching_method"] == "TM_SQDIFF_NORMED"


def test_analysis_disabled_keeps_global():
    config = {"confidence_threshold": 0.6}
    adj = json.dumps({
        "analysis": {
            "enabled": False,
            "confidence_threshold": 0.8,
        }
    })
    result = merge_scan_adjustments(config, adj)
    assert result["confidence_threshold"] == 0.6


def test_no_analysis_key_keeps_global():
    config = {"confidence_threshold": 0.6}
    adj = json.dumps({"preprocessing": {"brightness": 5}})
    result = merge_scan_adjustments(config, adj)
    assert result["confidence_threshold"] == 0.6
    assert result["brightness"] == 5


def test_none_adjustments_json():
    config = {"brightness": 0, "confidence_threshold": 0.6}
    result = merge_scan_adjustments(config, None)
    assert result["brightness"] == 0
    assert result["confidence_threshold"] == 0.6


def test_enabled_key_not_in_config():
    """The 'enabled' flag should not leak into the pipeline config."""
    config = {}
    adj = json.dumps({"analysis": {"enabled": True, "confidence_threshold": 0.7}})
    result = merge_scan_adjustments(config, adj)
    assert "enabled" not in result
    assert result["confidence_threshold"] == 0.7
```

- [ ] **Step 2: Run tests — expect ImportError**

```bash
python -m pytest tests/backend/test_config_merge.py -v
```

Expected: FAIL — `merge_scan_adjustments` does not exist yet.

- [ ] **Step 3: Implement `merge_scan_adjustments`**

Add this function to `src/backend/mv_hofki/services/sheet_music_scan.py`, before `run_pipeline()` (around line 130):

```python
_PREPROCESSING_KEYS = (
    "brightness",
    "contrast",
    "threshold",
    "rotation",
    "morphology_kernel_size",
)


def merge_scan_adjustments(config: dict, adjustments_json: str | None) -> dict:
    """Merge scan-level adjustments into a pipeline config dict.

    Preprocessing values always override if present.
    Analysis values override only when ``analysis.enabled`` is ``True``.
    """
    import json

    adjustments = json.loads(adjustments_json) if adjustments_json else {}

    preprocessing = adjustments.get("preprocessing", {})
    for key in _PREPROCESSING_KEYS:
        if key in preprocessing:
            config[key] = preprocessing[key]

    analysis = adjustments.get("analysis", {})
    if analysis.get("enabled", False):
        for key, value in analysis.items():
            if key != "enabled":
                config[key] = value

    return config
```

- [ ] **Step 4: Replace duplicated merge logic in `run_pipeline`**

In `src/backend/mv_hofki/services/sheet_music_scan.py`, replace lines 196–207:

```python
    # Merge scan-level preprocessing adjustments into pipeline config
    adjustments = json.loads(scan.adjustments_json) if scan.adjustments_json else {}
    preprocessing = adjustments.get("preprocessing", {})
    for key in (
        "brightness",
        "contrast",
        "threshold",
        "rotation",
        "morphology_kernel_size",
    ):
        if key in preprocessing:
            config[key] = preprocessing[key]
```

With:

```python
    # Merge scan-level adjustments (preprocessing + analysis) into pipeline config
    merge_scan_adjustments(config, scan.adjustments_json)
```

- [ ] **Step 5: Replace duplicated merge logic in `run_preview`**

In the same file, replace lines 360–372:

```python
    # Build config: global defaults + scan-level preprocessing overrides
    config = await get_effective_config(session)
    adjustments = json.loads(scan.adjustments_json) if scan.adjustments_json else {}
    preprocessing = adjustments.get("preprocessing", {})
    for key in (
        "brightness",
        "contrast",
        "threshold",
        "rotation",
        "morphology_kernel_size",
    ):
        if key in preprocessing:
            config[key] = preprocessing[key]
```

With:

```python
    # Build config: global defaults + scan-level overrides
    config = await get_effective_config(session)
    merge_scan_adjustments(config, scan.adjustments_json)
```

- [ ] **Step 6: Run tests**

```bash
python -m pytest tests/backend/test_config_merge.py tests/backend/test_pipeline_config_merge.py -v
```

Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add src/backend/mv_hofki/services/sheet_music_scan.py tests/backend/test_config_merge.py
git commit -m "refactor: extract merge_scan_adjustments helper, add analysis config merge"
```

---

### Task 2: Remove `config_overrides` / session-config from backend

**Files:**
- Modify: `src/backend/mv_hofki/services/sheet_music_scan.py:132-138,194`
- Modify: `src/backend/mv_hofki/api/routes/scan_processing.py:22-28,105-107`
- Modify: `src/backend/mv_hofki/services/scanner_config.py:35-47`

- [ ] **Step 1: Remove `config_overrides` parameter from `run_pipeline`**

In `src/backend/mv_hofki/services/sheet_music_scan.py`, change the signature (line 132–138):

```python
async def run_pipeline(
    session: AsyncSession,
    project_id: int,
    part_id: int,
    scan_id: int,
    config_overrides: ScannerConfigUpdate | None = None,
    log_callback: Callable[[str], None] | None = None,
) -> None:
```

To:

```python
async def run_pipeline(
    session: AsyncSession,
    project_id: int,
    part_id: int,
    scan_id: int,
    log_callback: Callable[[str], None] | None = None,
) -> None:
```

Remove the `ScannerConfigUpdate` TYPE_CHECKING import (line 20):

```python
    from mv_hofki.schemas.scanner_config import ScannerConfigUpdate
```

Change the config load line (around line 194):

```python
    config = await get_effective_config(session, overrides=config_overrides)
```

To:

```python
    config = await get_effective_config(session)
```

- [ ] **Step 2: Simplify `get_effective_config`**

In `src/backend/mv_hofki/services/scanner_config.py`, replace `get_effective_config` (lines 35–47):

```python
async def get_effective_config(
    session: AsyncSession, overrides: ScannerConfigUpdate | None = None
) -> dict:
    """Return a merged config dict: global defaults + any per-request overrides.

    The returned dict is ready to be placed into PipelineContext.config.
    """
    config = await get_config(session)
    result = ScannerConfigRead.model_validate(config).model_dump()
    if overrides:
        for key, value in overrides.model_dump(exclude_unset=True).items():
            result[key] = value
    return result
```

With:

```python
async def get_effective_config(session: AsyncSession) -> dict:
    """Return global scanner config as a dict for PipelineContext.config."""
    config = await get_config(session)
    return ScannerConfigRead.model_validate(config).model_dump()
```

Remove the unused `ScannerConfigUpdate` import from that file if it's only used in `get_effective_config`.

- [ ] **Step 3: Remove `config_overrides` from processing routes**

In `src/backend/mv_hofki/api/routes/scan_processing.py`:

Update `trigger_processing` (line 22–28) — remove `config_overrides` parameter:

```python
@router.post("/scans/{scan_id}/process", response_model=ScanStatusRead)
async def trigger_processing(
    scan_id: int,
    config_overrides: ScannerConfigUpdate | None = None,
    project_id: int | None = None,
    part_id: int | None = None,
    db: AsyncSession = Depends(get_db),
):
```

To:

```python
@router.post("/scans/{scan_id}/process", response_model=ScanStatusRead)
async def trigger_processing(
    scan_id: int,
    project_id: int | None = None,
    part_id: int | None = None,
    db: AsyncSession = Depends(get_db),
):
```

Remove `config_overrides=config_overrides` from the `run_pipeline` call (line 53–58):

```python
        await scan_service.run_pipeline(
            db,
            actual_project_id,
            actual_part_id,
            scan_id,
            config_overrides=config_overrides,
        )
```

To:

```python
        await scan_service.run_pipeline(
            db,
            actual_project_id,
            actual_part_id,
            scan_id,
        )
```

Remove the `ScannerConfigUpdate` import (line 13) and the unused config override parsing block in `stream_processing` (lines 105–107):

```python
    from mv_hofki.schemas.scanner_config import ScannerConfigUpdate as _CfgUpdate

    config_overrides: _CfgUpdate | None = None
```

Also remove `config_overrides=config_overrides` from `stream_processing`'s `run_pipeline` call (line 122).

- [ ] **Step 4: Run tests**

```bash
python -m pytest tests/backend/ -v -k "scan or config" --tb=short
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/backend/mv_hofki/services/sheet_music_scan.py src/backend/mv_hofki/api/routes/scan_processing.py src/backend/mv_hofki/services/scanner_config.py
git commit -m "refactor: remove broken config_overrides system from pipeline and routes"
```

---

### Task 3: Remove preprocessing fields from config modal

**Files:**
- Modify: `src/frontend/src/lib/scanner-config.js:174-212`

- [ ] **Step 1: Remove the "Vorverarbeitung" group**

In `src/frontend/src/lib/scanner-config.js`, delete the entire "Vorverarbeitung" group (lines 174–212):

```js
  // ── Preprocessing ──────────────────────────────────────────────────
  {
    key: "adaptive_threshold_block_size",
    label: "Adaptiver Schwellwert Blockgr.",
    group: "Vorverarbeitung",
    type: "number",
    min: 3,
    max: 99,
    step: 2,
  },
  {
    key: "adaptive_threshold_c",
    label: "Adaptiver Schwellwert Konstante",
    group: "Vorverarbeitung",
    type: "number",
    min: 0,
    max: 50,
    step: 1,
  },
  {
    key: "morphology_kernel_size",
    label: "Morphologie-Kerngr.",
    group: "Vorverarbeitung",
    type: "number",
    min: 1,
    max: 10,
    step: 1,
  },
  {
    key: "deskew_method",
    label: "Deskew-Methode",
    group: "Vorverarbeitung",
    type: "select",
    options: [
      { value: "none", label: "Keine Korrektur" },
      { value: "hough", label: "Hough-Linien (schnell)" },
      { value: "projection", label: "Projektions-Optimierung (genau)" },
    ],
  },
```

- [ ] **Step 2: Verify build**

```bash
cd /workspaces/mv_hofki/src/frontend && npx vite build
```

Expected: builds without errors.

- [ ] **Step 3: Commit**

```bash
git add src/frontend/src/lib/scanner-config.js
git commit -m "chore: remove preprocessing fields from config modal (now in ImageAdjustBar)"
```

---

### Task 4: Add scan-specific mode to ScannerConfigModal

**Files:**
- Modify: `src/frontend/src/components/ScannerConfigModal.vue`

- [ ] **Step 1: Rewrite `<script setup>`**

Replace the entire `<script setup>` block in `src/frontend/src/components/ScannerConfigModal.vue`:

```js
<script setup>
import { ref, watch } from "vue";
import { get, put } from "../lib/api.js";
import { groupedFields, SCANNER_CONFIG_FIELDS } from "../lib/scanner-config.js";

const props = defineProps({
  open: { type: Boolean, default: false },
  scanId: { type: [Number, String], default: null },
  projectId: { type: [Number, String], default: null },
  adjustments: { type: Object, default: () => ({}) },
});

const emit = defineEmits(["close", "update-adjustments"]);

const config = ref({});
const loading = ref(false);
const saving = ref(false);
const error = ref(null);
const successMsg = ref(null);
const scanSpecific = ref(false);

const groups = groupedFields();
const analysisKeys = SCANNER_CONFIG_FIELDS.map((f) => f.key);

watch(
  () => props.open,
  async (isOpen) => {
    if (!isOpen) return;
    successMsg.value = null;
    error.value = null;

    const analysis = props.adjustments?.analysis;
    scanSpecific.value = analysis?.enabled === true;

    await loadGlobalConfig();

    // If scan has specific values, overlay them onto the loaded global config
    if (analysis && analysis.enabled) {
      for (const key of analysisKeys) {
        if (key in analysis) {
          config.value[key] = analysis[key];
        }
      }
    }
  },
);

watch(scanSpecific, (isScanSpecific) => {
  if (!isScanSpecific) {
    // Switching back to global: reload global values
    loadGlobalConfig();
  }
});

async function loadGlobalConfig() {
  loading.value = true;
  error.value = null;
  try {
    config.value = await get("/scanner/config");
  } catch (e) {
    error.value = e.message;
  } finally {
    loading.value = false;
  }
}

async function saveGlobal() {
  saving.value = true;
  error.value = null;
  successMsg.value = null;
  try {
    config.value = await put("/scanner/config", config.value);
    successMsg.value = "Global gespeichert";
    setTimeout(() => {
      successMsg.value = null;
    }, 2000);
  } catch (e) {
    error.value = e.message;
  } finally {
    saving.value = false;
  }
}

async function saveScanSpecific() {
  saving.value = true;
  error.value = null;
  successMsg.value = null;
  try {
    // Build analysis object from current config values
    const analysis = { enabled: true };
    for (const key of analysisKeys) {
      if (key in config.value) {
        analysis[key] = config.value[key];
      }
    }
    const updated = { ...props.adjustments, analysis };
    // Save to backend
    const partsData = await get(`/scanner/projects/${props.projectId}/parts`);
    for (const part of partsData) {
      const scansData = await get(
        `/scanner/projects/${props.projectId}/parts/${part.id}/scans`,
      );
      const found = scansData.find((s) => String(s.id) === String(props.scanId));
      if (found) {
        await put(
          `/scanner/projects/${props.projectId}/parts/${part.id}/scans/${props.scanId}`,
          { adjustments_json: JSON.stringify(updated) },
        );
        break;
      }
    }
    emit("update-adjustments", updated);
    successMsg.value = "Für diesen Scan gespeichert";
    setTimeout(() => {
      successMsg.value = null;
    }, 2000);
  } catch (e) {
    error.value = e.message;
  } finally {
    saving.value = false;
  }
}

async function resetDefaults() {
  await loadGlobalConfig();
}
</script>
```

- [ ] **Step 2: Rewrite `<template>`**

Replace the template section with:

```html
<template>
  <div v-if="open" class="modal-backdrop" @click.self="emit('close')">
    <div class="modal modal-config">
      <div class="modal-header">
        <h2>Scanner-Konfiguration</h2>
        <button class="close-btn" title="Schließen" @click="emit('close')">✕</button>
      </div>

      <div v-if="loading" class="modal-loading">Laden...</div>

      <div v-else class="modal-body">
        <div v-if="error" class="config-error">{{ error }}</div>
        <div v-if="successMsg" class="config-success">{{ successMsg }}</div>

        <!-- Scan-specific toggle -->
        <div v-if="scanId" class="scan-toggle">
          <label class="toggle-label">
            <input v-model="scanSpecific" type="checkbox" class="toggle-input" />
            <span class="toggle-text">Scan-spezifische Parameter verwenden</span>
          </label>
        </div>

        <div v-for="group in groups" :key="group.label" class="config-group">
          <h3 class="group-title">{{ group.label }}</h3>
          <div class="group-fields">
            <div v-for="field in group.fields" :key="field.key" class="config-field">
              <!-- Toggle -->
              <template v-if="field.type === 'toggle'">
                <label class="toggle-label">
                  <input v-model="config[field.key]" type="checkbox" class="toggle-input" />
                  <span class="toggle-text">{{ field.label }}</span>
                </label>
              </template>

              <!-- Select -->
              <template v-else-if="field.type === 'select'">
                <label class="field-label">
                  {{ field.label }}
                  <select v-model="config[field.key]" class="field-select">
                    <option v-for="opt in field.options" :key="opt.value" :value="opt.value">
                      {{ opt.label }}
                    </option>
                  </select>
                </label>
              </template>

              <!-- Number -->
              <template v-else-if="field.type === 'number'">
                <label class="field-label">
                  <span class="field-label-row">
                    {{ field.label }}
                    <span class="field-value">{{ config[field.key] }}</span>
                  </span>
                  <input
                    v-model.number="config[field.key]"
                    type="range"
                    :min="field.min"
                    :max="field.max"
                    :step="field.step"
                    class="field-slider"
                  />
                </label>
              </template>
            </div>
          </div>
        </div>
      </div>

      <div class="modal-footer">
        <button class="btn" :disabled="loading" @click="resetDefaults">Zurücksetzen</button>
        <div class="footer-spacer"></div>
        <template v-if="scanSpecific && scanId">
          <button
            class="btn btn-primary"
            :disabled="loading || saving"
            @click="saveScanSpecific"
          >
            {{ saving ? "Speichert..." : "Für diesen Scan speichern" }}
          </button>
        </template>
        <template v-else>
          <button class="btn btn-primary" :disabled="loading || saving" @click="saveGlobal">
            {{ saving ? "Speichert..." : "Global speichern" }}
          </button>
        </template>
      </div>
    </div>
  </div>
</template>
```

- [ ] **Step 3: Add scan-toggle style**

In the `<style scoped>` section, add after the `.config-success` rule:

```css
.scan-toggle {
  margin-bottom: 1rem;
  padding: 0.75rem;
  background: var(--color-bg-soft);
  border-radius: var(--radius);
  border: 1px solid var(--color-border);
}
```

- [ ] **Step 4: Verify build**

```bash
cd /workspaces/mv_hofki/src/frontend && npx vite build
```

Expected: builds without errors.

- [ ] **Step 5: Commit**

```bash
git add src/frontend/src/components/ScannerConfigModal.vue
git commit -m "feat: add scan-specific analysis config mode to ScannerConfigModal"
```

---

### Task 5: Wire config modal into ScanEditorPage and remove sessionConfig

**Files:**
- Modify: `src/frontend/src/pages/ScanEditorPage.vue`

- [ ] **Step 1: Remove sessionConfig and related code**

In `src/frontend/src/pages/ScanEditorPage.vue`:

Delete the `sessionConfig` ref (line 44):

```js
const sessionConfig = ref(null);
```

Delete the `onApplySessionConfig` handler (lines 426–428):

```js
function onApplySessionConfig(cfg) {
  sessionConfig.value = cfg;
}
```

- [ ] **Step 2: Add `onUpdateAdjustments` handler**

Add after `onAdjust` function (around line 200):

```js
function onUpdateAdjustments(updated) {
  adjustments.value = updated;
}
```

- [ ] **Step 3: Update config button in template**

Replace the config button (around line 554–560):

```html
            <button
              class="btn btn-sm"
              :class="{ 'btn-active': sessionConfig !== null }"
              :title="
                sessionConfig ? 'Konfiguration (Sitzungsparameter aktiv)' : 'Scanner-Konfiguration'
              "
              @click="showConfig = true"
            >
              {{ sessionConfig ? "Konfig. *" : "Konfig." }}
            </button>
```

With:

```html
            <button
              class="btn btn-sm"
              :class="{ 'btn-active': adjustments.analysis?.enabled }"
              :title="
                adjustments.analysis?.enabled
                  ? 'Konfiguration (Scan-spezifisch aktiv)'
                  : 'Scanner-Konfiguration'
              "
              @click="showConfig = true"
            >
              {{ adjustments.analysis?.enabled ? "Konfig. *" : "Konfig." }}
            </button>
```

- [ ] **Step 4: Remove session badge from status bar**

Delete the session badge block (around lines 636–641):

```html
        <span
          v-if="sessionConfig"
          class="session-badge"
          title="Klicken zum Zurücksetzen"
          @click="sessionConfig = null"
        >
          Sitzungsparameter aktiv ✕
        </span>
```

- [ ] **Step 5: Update ScannerConfigModal usage in template**

Replace (around lines 674–678):

```html
    <ScannerConfigModal
      :open="showConfig"
      @close="showConfig = false"
      @apply-session="onApplySessionConfig"
    />
```

With:

```html
    <ScannerConfigModal
      :open="showConfig"
      :scan-id="props.scanId"
      :project-id="props.projectId"
      :adjustments="adjustments"
      @close="showConfig = false"
      @update-adjustments="onUpdateAdjustments"
    />
```

- [ ] **Step 6: Remove `session-badge` CSS if present**

Search for `.session-badge` in the `<style>` section and delete the rule if found.

- [ ] **Step 7: Verify build**

```bash
cd /workspaces/mv_hofki/src/frontend && npx vite build
```

Expected: builds without errors.

- [ ] **Step 8: Commit**

```bash
git add src/frontend/src/pages/ScanEditorPage.vue
git commit -m "feat: wire scan-specific config modal, remove broken sessionConfig system"
```

---

### Task 6: Alembic migration — remove dead columns

**Files:**
- Create: `alembic/versions/XXXX_remove_dead_columns.py` (auto-generated)
- Modify: `src/backend/mv_hofki/models/sheet_music_scan.py:28-29,31-32`
- Modify: `src/backend/mv_hofki/schemas/sheet_music_scan.py`

- [ ] **Step 1: Generate migration**

```bash
cd /workspaces/mv_hofki
PYTHONPATH=src/backend alembic revision -m "remove_corrected_image_path_and_pipeline_config_json"
```

- [ ] **Step 2: Write the migration**

In the generated file, replace `upgrade()` and `downgrade()`:

```python
"""remove corrected_image_path and pipeline_config_json from sheet_music_scans"""

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = "<auto>"
down_revision = "<auto>"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("sheet_music_scans") as batch_op:
        batch_op.drop_column("corrected_image_path")
        batch_op.drop_column("pipeline_config_json")


def downgrade() -> None:
    with op.batch_alter_table("sheet_music_scans") as batch_op:
        batch_op.add_column(sa.Column("pipeline_config_json", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("corrected_image_path", sa.String(500), nullable=True))
```

Note: `batch_alter_table` is required for SQLite column drops.

- [ ] **Step 3: Update the ORM model**

In `src/backend/mv_hofki/models/sheet_music_scan.py`, delete these two lines:

```python
    corrected_image_path: Mapped[str | None] = mapped_column(String(500))
    pipeline_config_json: Mapped[str | None] = mapped_column(Text)
```

- [ ] **Step 4: Update the Pydantic schema**

In `src/backend/mv_hofki/schemas/sheet_music_scan.py`, remove `pipeline_config_json` from `SheetMusicScanRead`:

```python
    pipeline_config_json: str | None
```

And remove `pipeline_config_json` from `SheetMusicScanUpdate`:

```python
    pipeline_config_json: str | None = None
```

- [ ] **Step 5: Run migration**

```bash
PYTHONPATH=src/backend alembic upgrade head
```

- [ ] **Step 6: Run tests**

```bash
python -m pytest tests/backend/ -v -k "scan" --tb=short
```

Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add alembic/versions/*remove_corrected_image_path* src/backend/mv_hofki/models/sheet_music_scan.py src/backend/mv_hofki/schemas/sheet_music_scan.py
git commit -m "migrate: remove dead columns corrected_image_path and pipeline_config_json"
```

---

### Task 7: Clean up old test file and run full verification

**Files:**
- Delete: `tests/backend/test_pipeline_config_merge.py` (superseded by `test_config_merge.py`)

- [ ] **Step 1: Remove superseded test file**

```bash
rm tests/backend/test_pipeline_config_merge.py
```

- [ ] **Step 2: Run all backend tests**

```bash
python -m pytest tests/backend/ -v --tb=short
```

Expected: all pass (except the pre-existing `test_create_invoice_on_sheet_music_rejected`).

- [ ] **Step 3: Run frontend build**

```bash
cd /workspaces/mv_hofki/src/frontend && npx vite build
```

Expected: clean build.

- [ ] **Step 4: Run pre-commit**

```bash
cd /workspaces/mv_hofki
pre-commit run --all-files
```

Expected: all pass (except pre-existing mypy pypdf issue).

- [ ] **Step 5: Commit cleanup**

```bash
git add -A
git commit -m "chore: remove superseded test file, final cleanup"
```

- [ ] **Step 6: Manual E2E verification**

Open the scan editor:
1. Open Config-Modal → no "Vorverarbeitung" group visible
2. Toggle "Scan-spezifische Parameter" on → modify a value → "Für diesen Scan speichern"
3. Close and reopen modal → toggle is on, scan-specific values shown
4. Toggle off → global values shown again
5. Config button shows `"Konfig. *"` when scan-specific is active
6. Run analysis → scan-specific config values are used by pipeline
7. Old "Sitzungsparameter aktiv" badge is gone
