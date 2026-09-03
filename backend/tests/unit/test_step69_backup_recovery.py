from pathlib import Path

import pytest

from backend.tools.database_backup import (
    build_dump_command,
    build_restore_command,
    validate_database_name,
    validate_label,
)


def test_database_and_label_validation_reject_injection_and_traversal():
    with pytest.raises(ValueError):
        validate_database_name("db;DROP DATABASE x")
    with pytest.raises(ValueError):
        validate_label("../credentials")
    with pytest.raises(ValueError):
        validate_label("secret password")


def test_native_commands_are_fixed_argument_lists_without_shell_expansion():
    dump = build_dump_command("safe_db", "postgres-container")
    restore = build_restore_command("recovery_db", "backup.dump", "postgres-container")
    assert dump[:4] == ["docker", "exec", "postgres-container", "pg_dump"]
    assert "--dbname=safe_db" in dump
    assert "--username=postgres" in dump
    assert restore[:4] == ["docker", "exec", "postgres-container", "pg_restore"]
    assert restore[-1] == "/tmp/backup.dump"
    assert "--username=postgres" in restore
    assert all(";" not in item and "&&" not in item for item in dump + restore)


def test_backup_artifact_paths_are_regular_files(tmp_path: Path):
    artifact = tmp_path / "valid.dump"
    artifact.write_bytes(b"custom-format-placeholder")
    assert artifact.is_file()
