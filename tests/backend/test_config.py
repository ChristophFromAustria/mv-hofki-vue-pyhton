from mv_hofki.core.config import settings


def test_settings_defaults():
    assert settings.APP_NAME == "mv_hofki"
    assert settings.DEBUG is True
    assert settings.API_V1_PREFIX == "/api/v1"
    assert settings.BASE_PATH == "/"


def test_project_root_contains_pyproject(tmp_path):
    """PROJECT_ROOT should point to the directory containing pyproject.toml."""
    from mv_hofki.core.config import settings
    assert (settings.PROJECT_ROOT / "pyproject.toml").exists()
