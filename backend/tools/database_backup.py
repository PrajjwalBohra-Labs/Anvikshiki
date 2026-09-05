"""PostgreSQL-native backup and restore tooling for local administration."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

_DATABASE_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,62}$")
_LABEL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")


def validate_database_name(value: str) -> str:
    if not _DATABASE_NAME.fullmatch(value):
        raise ValueError("Database name must contain only safe PostgreSQL identifier characters.")
    return value


def validate_identifier(value: str, label: str) -> str:
    if not _DATABASE_NAME.fullmatch(value):
        raise ValueError(f"{label} must contain only safe PostgreSQL identifier characters.")
    return value


def validate_label(value: str) -> str:
    if not _LABEL.fullmatch(value):
        raise ValueError("Backup label must contain only letters, numbers, '-' or '_'.")
    return value


def _tool_prefix(container: str | None, executable: str) -> list[str]:
    if container:
        return ["docker", "exec", container, executable]
    resolved = shutil.which(executable)
    if resolved is None:
        raise RuntimeError(
            f"{executable} was not found. Install PostgreSQL client tools or provide --docker-container."
        )
    return [resolved]


def build_dump_command(
    database: str, container: str | None = None, username: str = "postgres"
) -> list[str]:
    return [
        *_tool_prefix(container, "pg_dump"),
        "--format=custom",
        "--no-owner",
        "--no-privileges",
        f"--username={validate_identifier(username, 'Database username')}",
        f"--dbname={validate_database_name(database)}",
    ]


def build_list_command(backup_path: Path, container: str | None = None) -> list[str]:
    command = [*_tool_prefix(container, "pg_restore"), "--list", "--file", "-"]
    if container:
        return [*command, f"/tmp/{backup_path.name}"]
    return [*command, str(backup_path)]


def build_restore_command(
    database: str,
    backup_name: str,
    container: str | None = None,
    username: str = "postgres",
) -> list[str]:
    source = f"/tmp/{backup_name}" if container else backup_name
    return [
        *_tool_prefix(container, "pg_restore"),
        "--exit-on-error",
        "--no-owner",
        "--no-privileges",
        f"--username={validate_identifier(username, 'Database username')}",
        f"--dbname={validate_database_name(database)}",
        source,
    ]


def _run(command: list[str], *, stdout=None) -> None:
    if stdout is None:
        subprocess.run(command, check=True, capture_output=True, text=True)
    else:
        subprocess.run(command, check=True, stdout=stdout, stderr=subprocess.PIPE)


def backup(
    database: str,
    output_dir: Path,
    label: str,
    container: str | None,
    username: str,
) -> Path:
    validate_database_name(database)
    validate_label(label)
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    destination = output_dir / f"{label}.dump"
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{label}-", suffix=".dump", dir=output_dir
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        with temporary.open("wb") as stream:
            _run(build_dump_command(database, container, username), stdout=stream)
        if temporary.stat().st_size == 0:
            raise RuntimeError("pg_dump produced an empty backup artifact.")
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)
    digest = hashlib.sha256(destination.read_bytes()).hexdigest()
    (destination.with_suffix(".sha256")).write_text(f"{digest}  {destination.name}\n", encoding="ascii")
    return destination


def validate_backup(backup_path: Path, container: str | None) -> None:
    backup_path = backup_path.resolve()
    if not backup_path.is_file() or backup_path.stat().st_size == 0:
        raise ValueError("Backup artifact must be a non-empty file.")
    if container:
        _copy_to_container(backup_path, container)
        try:
            _run(build_list_command(backup_path, container))
        finally:
            _remove_from_container(backup_path, container)
    else:
        _run(build_list_command(backup_path))


def _copy_to_container(backup_path: Path, container: str) -> None:
    subprocess.run(["docker", "cp", str(backup_path), f"{container}:/tmp/{backup_path.name}"], check=True, capture_output=True)


def _remove_from_container(backup_path: Path, container: str) -> None:
    subprocess.run(["docker", "exec", container, "rm", "-f", f"/tmp/{backup_path.name}"], check=False, capture_output=True)


def restore(
    database: str,
    backup_path: Path,
    container: str | None,
    create_target: bool,
    username: str,
) -> None:
    validate_database_name(database)
    backup_path = backup_path.resolve()
    validate_backup(backup_path, container)
    if container:
        if create_target:
            _run(
                [
                    "docker",
                    "exec",
                    container,
                    "createdb",
                    f"--username={validate_identifier(username, 'Database username')}",
                    database,
                ]
            )
        _copy_to_container(backup_path, container)
        try:
            _run(build_restore_command(database, backup_path.name, container, username))
        finally:
            _remove_from_container(backup_path, container)
    else:
        if create_target:
            raise ValueError("--create-target requires --docker-container in this local tool.")
        _run(build_restore_command(database, str(backup_path)))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="operation", required=True)
    backup_parser = subparsers.add_parser("backup")
    backup_parser.add_argument("--database", required=True)
    backup_parser.add_argument("--output-dir", type=Path, default=Path("backups"))
    backup_parser.add_argument("--label", default="anvikshiki")
    backup_parser.add_argument("--docker-container")
    backup_parser.add_argument("--username", default="postgres")
    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("--backup", type=Path, required=True)
    validate_parser.add_argument("--docker-container")
    restore_parser = subparsers.add_parser("restore")
    restore_parser.add_argument("--database", required=True)
    restore_parser.add_argument("--backup", type=Path, required=True)
    restore_parser.add_argument("--docker-container")
    restore_parser.add_argument("--create-target", action="store_true")
    restore_parser.add_argument("--username", default="postgres")
    args = parser.parse_args(argv)
    try:
        if args.operation == "backup":
            artifact = backup(
                args.database, args.output_dir, args.label, args.docker_container, args.username
            )
            print(json.dumps({"status": "created", "artifact": artifact.name}, sort_keys=True))
        elif args.operation == "validate":
            validate_backup(args.backup, args.docker_container)
            print(json.dumps({"status": "valid", "artifact": args.backup.name}, sort_keys=True))
        else:
            restore(
                args.database,
                args.backup,
                args.docker_container,
                args.create_target,
                args.username,
            )
            print(json.dumps({"status": "restored", "database": args.database}, sort_keys=True))
        return 0
    except (OSError, RuntimeError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"database backup operation failed: {type(exc).__name__}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
