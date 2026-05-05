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
    adj = json.dumps(
        {
            "analysis": {
                "enabled": True,
                "confidence_threshold": 0.8,
                "matching_method": "TM_SQDIFF_NORMED",
            }
        }
    )
    result = merge_scan_adjustments(config, adj)
    assert result["confidence_threshold"] == 0.8
    assert result["matching_method"] == "TM_SQDIFF_NORMED"


def test_analysis_disabled_keeps_global():
    config = {"confidence_threshold": 0.6}
    adj = json.dumps(
        {
            "analysis": {
                "enabled": False,
                "confidence_threshold": 0.8,
            }
        }
    )
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
