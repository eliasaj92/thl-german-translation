#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
from pathlib import Path

from corpus_common import (
    CORPUS_HEADER,
    ensure_safe_replace_target,
    install_staged_directory,
    path_for,
    read_csv,
    sha256_text,
    validate_archive_name,
    validate_relative_path,
    write_csv,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply bilingual German cells to native MVGLTools CSV trees.")
    parser.add_argument("--corpus", type=Path, default=Path("corpus"))
    parser.add_argument("--source-native", required=True, type=Path)
    parser.add_argument("--output-native", required=True, type=Path)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    corpus = args.corpus.resolve()
    source_native = args.source_native.resolve()
    output = ensure_safe_replace_target(args.output_native)
    manifest = json.loads((corpus / "manifest.json").read_text(encoding="utf-8"))
    if output.exists() and not args.force:
        raise FileExistsError(f"Output already exists: {output} (use --force to replace it)")
    staging = output.with_name(f".{output.name}.staging-{os.getpid()}")
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)

    archive_map: dict[str, str] = {}
    try:
        for record in manifest["archives"]:
            source_archive = validate_archive_name(record["source_archive"])
            target_archive = validate_archive_name(record["target_archive"])
            source_root = source_native / source_archive
            if not source_root.is_dir():
                raise FileNotFoundError(f"Missing extracted native source tree: {source_root}")
            if target_archive in archive_map.values():
                raise RuntimeError(f"Duplicate target archive: {target_archive}")
            archive_map[source_archive] = target_archive
            shutil.copytree(source_root, staging / target_archive)

        changed = 0
        applied = 0
        for file_record in manifest["files"]:
            corpus_rel = validate_relative_path(file_record["path"])
            if len(corpus_rel.parts) < 2:
                raise RuntimeError(f"Invalid corpus file path: {corpus_rel}")
            source_archive = corpus_rel.parts[0]
            csv_rel = PureCsvPath(corpus_rel.parts[1:])
            target_archive = archive_map[source_archive]
            native_path = path_for(staging, target_archive, csv_rel)
            if not native_path.is_file():
                raise FileNotFoundError(f"Missing native CSV: {native_path}")
            native_rows = read_csv(native_path)
            corpus_path = corpus.joinpath(*corpus_rel.parts)
            with corpus_path.open("r", encoding="utf-8-sig", newline="") as handle:
                reader = csv.DictReader(handle)
                if tuple(reader.fieldnames or ()) != CORPUS_HEADER:
                    raise RuntimeError(f"Corpus header mismatch: {corpus_path}")
                for line_number, row in enumerate(reader, 2):
                    row_index = int(row["row_index"])
                    column_index = int(row["column_index"])
                    if row["source_archive"] != source_archive or row["target_archive"] != target_archive:
                        raise RuntimeError(f"Archive mismatch at {corpus_path}:{line_number}")
                    if validate_relative_path(row["csv_rel"]).as_posix() != csv_rel:
                        raise RuntimeError(f"CSV path mismatch at {corpus_path}:{line_number}")
                    if row_index >= len(native_rows) or column_index >= len(native_rows[row_index]):
                        raise IndexError(f"Native coordinate out of range at {corpus_path}:{line_number}")
                    if not native_rows or column_index >= len(native_rows[0]):
                        raise IndexError(f"Native header coordinate out of range at {corpus_path}:{line_number}")
                    if native_rows[0][column_index] != row["field"]:
                        raise RuntimeError(f"Native field mismatch at {corpus_path}:{line_number}")
                    if native_rows[row_index][column_index] != row["english"]:
                        raise RuntimeError(f"English source mismatch at {corpus_path}:{line_number}")
                    if sha256_text(row["english"]) != row["source_sha256"]:
                        raise RuntimeError(f"English hash mismatch at {corpus_path}:{line_number}")
                    if row["classification"] == "protected" and row["german"] != row["english"]:
                        raise RuntimeError(f"Protected cell changed at {corpus_path}:{line_number}")
                    if row["german"] != row["english"]:
                        changed += 1
                    native_rows[row_index][column_index] = row["german"]
                    applied += 1
            write_csv(native_path, native_rows)

        install_staged_directory(staging, output, args.force)
    except Exception:
        if staging.exists():
            shutil.rmtree(staging)
        raise

    print(f"Materialized {applied:,} cells ({changed:,} changed) in {output}")
    return 0


def PureCsvPath(parts: tuple[str, ...]) -> str:
    value = "/".join(parts)
    return validate_relative_path(value).as_posix()


if __name__ == "__main__":
    raise SystemExit(main())

