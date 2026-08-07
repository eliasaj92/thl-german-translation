#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path

from corpus_common import (
    CORPUS_HEADER,
    SCHEMA_VERSION,
    sha256_text,
    stable_cell_id,
    structural_signature,
    validate_archive_name,
    validate_relative_path,
)


ALLOWED_CLASSIFICATIONS = {"translate", "protected", "review"}
ALLOWED_STATUSES = {"pending", "protected", "translated", "reviewed", "approved", "source_changed"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate the public THL bilingual corpus.")
    parser.add_argument("corpus", nargs="?", type=Path, default=Path("corpus"))
    parser.add_argument("--max-errors", type=int, default=100)
    return parser.parse_args()


def fail(errors: list[str], message: str, maximum: int) -> None:
    if len(errors) < maximum:
        errors.append(message)


def main() -> int:
    args = parse_args()
    root = args.corpus.resolve()
    manifest_path = root / "manifest.json"
    if not manifest_path.is_file():
        print(f"Missing corpus manifest: {manifest_path}", file=sys.stderr)
        return 2
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    errors: list[str] = []
    warnings: Counter[str] = Counter()

    if manifest.get("schema_version") != SCHEMA_VERSION:
        fail(errors, f"Unsupported schema version: {manifest.get('schema_version')!r}", args.max_errors)
    if tuple(manifest.get("columns", ())) != CORPUS_HEADER:
        fail(errors, "Manifest columns do not match the corpus schema", args.max_errors)

    archive_map: dict[str, str] = {}
    for record in manifest.get("archives", []):
        try:
            source = validate_archive_name(str(record["source_archive"]))
            target = validate_archive_name(str(record["target_archive"]))
        except (KeyError, ValueError) as exc:
            fail(errors, f"Invalid archive record: {exc}", args.max_errors)
            continue
        if source in archive_map and archive_map[source] != target:
            fail(errors, f"Conflicting target archive for {source}", args.max_errors)
        archive_map[source] = target

    expected_records = {str(record["path"]): record for record in manifest.get("files", [])}
    actual_paths = {
        path.relative_to(root).as_posix(): path
        for path in root.rglob("*.csv")
        if path.is_file()
    }
    missing = sorted(set(expected_records) - set(actual_paths))
    unexpected = sorted(set(actual_paths) - set(expected_records))
    for value in missing:
        fail(errors, f"Missing corpus file: {value}", args.max_errors)
    for value in unexpected:
        fail(errors, f"Unexpected corpus file: {value}", args.max_errors)

    seen_ids: set[str] = set()
    seen_coordinates: set[tuple[str, str, int, int]] = set()
    total_cells = 0
    status_counts: Counter[str] = Counter()
    classification_counts: Counter[str] = Counter()

    for relative in sorted(set(expected_records) & set(actual_paths)):
        path = actual_paths[relative]
        record = expected_records[relative]
        parts = validate_relative_path(relative).parts
        if len(parts) < 2:
            fail(errors, f"Corpus path lacks archive prefix: {relative}", args.max_errors)
            continue
        path_archive = parts[0]
        path_csv_rel = "/".join(parts[1:])
        file_cells = 0
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if tuple(reader.fieldnames or ()) != CORPUS_HEADER:
                fail(errors, f"Header mismatch: {relative}", args.max_errors)
                continue
            for line_number, row in enumerate(reader, 2):
                file_cells += 1
                total_cells += 1
                prefix = f"{relative}:{line_number}"
                try:
                    row_index = int(row["row_index"])
                    column_index = int(row["column_index"])
                    source_archive = validate_archive_name(row["source_archive"])
                    target_archive = validate_archive_name(row["target_archive"])
                    csv_rel = validate_relative_path(row["csv_rel"]).as_posix()
                except (ValueError, KeyError) as exc:
                    fail(errors, f"{prefix}: invalid coordinate/path: {exc}", args.max_errors)
                    continue
                if row_index < 0 or column_index < 0:
                    fail(errors, f"{prefix}: negative row or column", args.max_errors)
                if source_archive != path_archive or csv_rel != path_csv_rel:
                    fail(errors, f"{prefix}: row path does not match containing file", args.max_errors)
                if archive_map.get(source_archive) != target_archive:
                    fail(errors, f"{prefix}: archive mapping does not match manifest", args.max_errors)

                expected_id = stable_cell_id(target_archive, csv_rel, row_index, column_index)
                if row["cell_id"] != expected_id:
                    fail(errors, f"{prefix}: stable cell ID mismatch", args.max_errors)
                if row["cell_id"] in seen_ids:
                    fail(errors, f"{prefix}: duplicate cell ID {row['cell_id']}", args.max_errors)
                seen_ids.add(row["cell_id"])
                coordinate = (target_archive, csv_rel, row_index, column_index)
                if coordinate in seen_coordinates:
                    fail(errors, f"{prefix}: duplicate native coordinate", args.max_errors)
                seen_coordinates.add(coordinate)

                if sha256_text(row["english"]) != row["source_sha256"]:
                    fail(errors, f"{prefix}: English source hash mismatch", args.max_errors)
                classification = row["classification"]
                status = row["status"]
                classification_counts[classification] += 1
                status_counts[status] += 1
                if classification not in ALLOWED_CLASSIFICATIONS:
                    fail(errors, f"{prefix}: unknown classification {classification!r}", args.max_errors)
                if status not in ALLOWED_STATUSES:
                    fail(errors, f"{prefix}: unknown status {status!r}", args.max_errors)
                if classification == "protected" and row["german"] != row["english"]:
                    fail(errors, f"{prefix}: protected cell changed", args.max_errors)
                if classification != "protected" and row["english"] and not row["german"]:
                    fail(errors, f"{prefix}: displayed string has an empty German value", args.max_errors)
                if structural_signature(row["english"]) != structural_signature(row["german"]):
                    fail(errors, f"{prefix}: control code or line-break mismatch", args.max_errors)
                if classification == "review" or status in {"pending", "source_changed"}:
                    warnings["unresolved review/pending cells"] += 1
                if classification != "protected" and row["english"] == row["german"]:
                    warnings["unchanged displayed strings"] += 1
        if file_cells != int(record.get("cells", -1)):
            fail(errors, f"Cell count mismatch: {relative}", args.max_errors)

    if total_cells != int(manifest.get("total_cells", -1)):
        fail(errors, "Total cell count does not match manifest", args.max_errors)
    if len(expected_records) != int(manifest.get("total_csv_files", -1)):
        fail(errors, "Total CSV file count does not match manifest", args.max_errors)

    if errors:
        for message in errors:
            print(f"ERROR: {message}", file=sys.stderr)
        if len(errors) >= args.max_errors:
            print(f"ERROR: stopped reporting after {args.max_errors} errors", file=sys.stderr)
        return 1

    print(f"Validated {total_cells:,} cells in {len(expected_records):,} CSV files.")
    print("Classifications: " + ", ".join(f"{key}={value:,}" for key, value in sorted(classification_counts.items())))
    print("Statuses: " + ", ".join(f"{key}={value:,}" for key, value in sorted(status_counts.items())))
    for label, count in sorted(warnings.items()):
        print(f"WARNING: {label}: {count:,}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
