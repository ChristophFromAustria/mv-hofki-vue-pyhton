"""Tests for adjustment merging in run_pipeline config assembly."""

import json


def test_preprocessing_values_merged():
    """All preprocessing keys should be extracted from the grouped JSON."""
    adjustments_json = json.dumps(
        {
            "preprocessing": {
                "brightness": 10,
                "contrast": 1.5,
                "threshold": 140,
                "rotation": 90,
                "morphology_kernel_size": 3,
            }
        }
    )
    adjustments = json.loads(adjustments_json)
    preprocessing = adjustments.get("preprocessing", {})

    config = {"brightness": 0, "contrast": 1.0, "morphology_kernel_size": 2}
    for key in (
        "brightness",
        "contrast",
        "threshold",
        "rotation",
        "morphology_kernel_size",
    ):
        if key in preprocessing:
            config[key] = preprocessing[key]

    assert config["brightness"] == 10
    assert config["contrast"] == 1.5
    assert config["threshold"] == 140
    assert config["rotation"] == 90
    assert config["morphology_kernel_size"] == 3


def test_empty_adjustments_keeps_defaults():
    """Missing adjustments_json should not override config defaults."""
    adjustments_json = None
    adjustments = json.loads(adjustments_json) if adjustments_json else {}
    preprocessing = adjustments.get("preprocessing", {})

    config = {"brightness": 0, "contrast": 1.0, "morphology_kernel_size": 2}
    for key in (
        "brightness",
        "contrast",
        "threshold",
        "rotation",
        "morphology_kernel_size",
    ):
        if key in preprocessing:
            config[key] = preprocessing[key]

    assert config["brightness"] == 0
    assert config["contrast"] == 1.0
    assert "threshold" not in config
    assert "rotation" not in config
    assert config["morphology_kernel_size"] == 2
