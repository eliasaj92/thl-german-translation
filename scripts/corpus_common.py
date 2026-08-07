from __future__ import annotations

import csv
import hashlib
import os
import re
import shutil
from pathlib import Path, PurePosixPath
from typing import Iterable, Sequence


SCHEMA_VERSION = 1
CORPUS_HEADER = (
    "cell_id",
    "source_archive",
    "target_archive",
    "csv_rel",
    "row_index",
    "column_index",
    "field",
    "english",
    "german",
    "classification",
    "status",
    "reason",
    "source_sha256",
)

CONTROL_RE = re.compile(
    r"\{[^{}]*(?:\([^{}]*\))?[^{}]*\}"
    r"|(?<![A-Za-z0-9])%(?:\d+\$)?[-+#0']*\d*(?:\.\d+)?[a-zA-Z](?![A-Za-z0-9])"
    r"|\\[nrt]|<[^<>]+>"
)
FC_TEXT_RE = re.compile(r"\{(?P<head>fc\([^(){}]*\))(?P<body>[^{}]*)\}", re.I | re.S)
LINE_BREAK_RE = re.compile(r"\r\n|\r|\n")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_text(value: str) -> str:
    return sha256_bytes(value.encode("utf-8"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stable_cell_id(target_archive: str, csv_rel: str, row_index: int, column_index: int) -> str:
    key = f"{target_archive}|{csv_rel.replace(os.sep, '/').lower()}|{row_index}|{column_index}"
    return sha256_text(key)[:24]


def validate_archive_name(value: str) -> str:
    if not value or value in {".", ".."} or "/" in value or "\\" in value:
        raise ValueError(f"Unsafe archive name: {value!r}")
    return value


def validate_relative_path(value: str) -> PurePosixPath:
    path = PurePosixPath(value)
    if path.is_absolute() or not path.parts or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError(f"Unsafe relative path: {value!r}")
    return path


def path_for(root: Path, archive: str, csv_rel: str) -> Path:
    validate_archive_name(archive)
    relative = validate_relative_path(csv_rel)
    candidate = root.joinpath(archive, *relative.parts)
    candidate.resolve().relative_to(root.resolve())
    return candidate


def ensure_safe_replace_target(path: Path) -> Path:
    resolved = path.resolve()
    forbidden = {Path(resolved.anchor).resolve(), Path.home().resolve(), Path.cwd().resolve()}
    if resolved in forbidden or len(resolved.parts) < 3:
        raise ValueError(f"Refusing unsafe output directory: {resolved}")
    return resolved


def install_staged_directory(staging: Path, output: Path, force: bool) -> None:
    output = ensure_safe_replace_target(output)
    if output.exists() and not force:
        raise FileExistsError(f"Output already exists: {output} (use --force to replace it)")
    backup = output.with_name(f".{output.name}.backup-{os.getpid()}")
    if backup.exists():
        shutil.rmtree(backup)
    if output.exists():
        output.replace(backup)
    try:
        staging.replace(output)
    except Exception:
        if backup.exists() and not output.exists():
            backup.replace(output)
        raise
    if backup.exists():
        shutil.rmtree(backup)


def read_csv(path: Path) -> list[list[str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.reader(handle))


def write_csv(path: Path, rows: Iterable[Sequence[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        csv.writer(handle, lineterminator="\n").writerows(rows)


def control_tokens(value: str) -> tuple[str, ...]:
    tokens: list[str] = []
    for match in CONTROL_RE.finditer(value):
        token = match.group(0)
        formatted = FC_TEXT_RE.fullmatch(token)
        if formatted:
            # Text after fc(...) is visible. Only the color opcode is structural.
            tokens.append("{" + formatted.group("head") + "}")
        else:
            tokens.append(token)
    return tuple(tokens)


def structural_signature(value: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    return control_tokens(value), tuple(LINE_BREAK_RE.findall(value))
