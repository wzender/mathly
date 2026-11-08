import pytest

from mathly2 import config
from mathly2.config import load_settings

NAMES = ("SUPABASE_URL", "SUPABASE_PUBLISHABLE_KEY", "SUPABASE_SECRET_KEY", "TEACHER_EMAILS", "DEVELOPER_EMAILS", "ADMIN_EMAILS", "ANTHROPIC_API_KEY")


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch):
    """Start with none of the settings in the environment; monkeypatch puts back whatever was there afterwards
    (load_dotenv writes into os.environ, so this also stops one test leaking into the next)."""
    for name in NAMES:
        monkeypatch.setenv(name, "")
        monkeypatch.delenv(name)


def write(tmp_path, text):
    path = tmp_path / ".env"
    path.write_text(text, encoding="utf-8")
    return path


def test_the_env_file_fills_in_what_the_environment_does_not_set(tmp_path):
    settings = load_settings(write(tmp_path, "TEACHER_EMAILS=A@School.test, b@school.test\n"))
    assert settings.teachers == {"a@school.test", "b@school.test"}
    assert settings.supabase_on is False                               # no Supabase values: local development


def test_a_real_environment_variable_wins_over_the_file(tmp_path, monkeypatch):
    monkeypatch.setenv("TEACHER_EMAILS", "real@school.test")
    settings = load_settings(write(tmp_path, "TEACHER_EMAILS=file@school.test\n"))
    assert settings.teachers == {"real@school.test"}


def test_all_three_supabase_values_in_the_file_turn_supabase_on(tmp_path):
    text = "SUPABASE_URL=https://p.supabase.test/\nSUPABASE_PUBLISHABLE_KEY=pub\nSUPABASE_SECRET_KEY=sec\n"
    settings = load_settings(write(tmp_path, text))
    assert settings.supabase_on and settings.supabase_url == "https://p.supabase.test"


def test_a_half_configured_file_is_refused(tmp_path):
    with pytest.raises(ValueError, match="all of SUPABASE_URL"):
        load_settings(write(tmp_path, "SUPABASE_URL=https://p.supabase.test\n"))


def test_a_missing_env_file_is_fine(tmp_path):
    assert load_settings(tmp_path / "nope.env").teachers == frozenset()


def test_the_two_default_files_are_this_apps_own_and_the_repository_root_one():
    assert config.ENV_FILE.parent.name == "mathly2" and config.ENV_FILE.name == ".env"
    assert config.ROOT_ENV_FILE == config.ENV_FILE.parent.parent / ".env" and config.ROOT_ENV_FILE.parent.name == "mathly"


def test_the_repository_env_is_used_when_this_app_has_none(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "ENV_FILE", tmp_path / "missing.env")
    monkeypatch.setattr(config, "ROOT_ENV_FILE", write(tmp_path, "ADMIN_EMAILS=root-admin@x.test\nTEACHER_EMAILS=root-teacher@x.test\n"))
    settings = load_settings()
    assert settings.admins == {"root-admin@x.test"} and settings.teachers == {"root-teacher@x.test"}


def test_order_is_environment_then_this_apps_file_then_the_repository_file(tmp_path, monkeypatch):
    own = tmp_path / "own.env"
    own.write_text("TEACHER_EMAILS=own@x.test\nADMIN_EMAILS=own-admin@x.test\n", encoding="utf-8")
    root = tmp_path / "root.env"
    root.write_text("TEACHER_EMAILS=root@x.test\nADMIN_EMAILS=root-admin@x.test\nDEVELOPER_EMAILS=root-dev@x.test\n", encoding="utf-8")
    monkeypatch.setattr(config, "ENV_FILE", own)
    monkeypatch.setattr(config, "ROOT_ENV_FILE", root)
    monkeypatch.setenv("TEACHER_EMAILS", "env@x.test")
    settings = load_settings()
    assert settings.teachers == {"env@x.test"}             # the environment wins over both files
    assert settings.admins == {"own-admin@x.test"}          # this app's file wins over the repository's
    assert settings.developers == {"root-dev@x.test"}       # the repository's file fills what is left


def test_passing_a_file_reads_only_that_file(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "ROOT_ENV_FILE", write(tmp_path, "ADMIN_EMAILS=root-admin@x.test\n"))
    assert load_settings(tmp_path / "nope.env").admins == frozenset()


def test_the_example_file_lists_every_setting_with_empty_values():
    example = (config.ENV_FILE.parent / ".env.example").read_text(encoding="utf-8")
    for name in ("SUPABASE_URL", "SUPABASE_PUBLISHABLE_KEY", "SUPABASE_SECRET_KEY", "TEACHER_EMAILS"):
        assert f"\n{name}=\n" in example


def test_the_container_image_never_gets_the_env_file():
    ignore = (config.ENV_FILE.parent / "Dockerfile.dockerignore").read_text(encoding="utf-8").split()
    assert "mathly2/.env" in ignore


def test_developers_and_admins_come_from_the_environment_and_the_file(tmp_path, monkeypatch):
    monkeypatch.setenv("DEVELOPER_EMAILS", "Dev@School.test")
    settings = load_settings(write(tmp_path, "ADMIN_EMAILS=head@school.test, deputy@school.test\nDEVELOPER_EMAILS=file-dev@school.test\n"))
    assert settings.developers == {"dev@school.test"}                      # the environment wins over the file
    assert settings.admins == {"head@school.test", "deputy@school.test"}   # from the file
    assert settings.teachers == frozenset()


def test_the_example_file_and_readme_name_the_new_settings():
    base = config.ENV_FILE.parent
    for name in ("DEVELOPER_EMAILS", "ADMIN_EMAILS"):
        assert f"\n{name}=\n" in (base / ".env.example").read_text(encoding="utf-8")
        assert f"`{name}`" in (base / "README.md").read_text(encoding="utf-8")
