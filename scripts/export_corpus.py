#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from corpus_common import (
    CORPUS_HEADER,
    SCHEMA_VERSION,
    ensure_safe_replace_target,
    install_staged_directory,
    path_for,
    sha256_file,
    validate_archive_name,
    validate_relative_path,
)


QUERY = """
SELECT cell_id, source_archive, target_archive, csv_rel, row_index, col_index,
       header, source_text, target_text, classification, status, reason, source_hash
FROM cells
ORDER BY source_archive, csv_rel, row_index, col_index
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export the THL translation memory as bilingual per-MBE CSVs.")
    parser.add_argument("--database", required=True, type=Path, help="translation_memory.sqlite")
    parser.add_argument("--output", type=Path, default=Path("corpus"), help="Corpus output directory")
    parser.add_argument("--force", action="store_true", help="Atomically replace an existing output directory")
    return parser.parse_args()


def connect_read_only(path: Path) -> sqlite3.Connection:
    absolute = path.resolve()
    if not absolute.is_file():
        raise FileNotFoundError(absolute)
    database = sqlite3.connect(f"file:{absolute.as_posix()}?mode=ro", uri=True)
    database.row_factory = sqlite3.Row
    columns = {row[1] for row in database.execute("PRAGMA table_info(cells)")}
    required = {
        "cell_id", "source_archive", "target_archive", "csv_rel", "row_index", "col_index",
        "header", "source_text", "target_text", "classification", "status", "reason", "source_hash",
    }
    missing = sorted(required - columns)
    if missing:
        raise RuntimeError(f"Database is missing cells columns: {', '.join(missing)}")
    return database


def main() -> int:
    args = parse_args()
    output = ensure_safe_replace_target(args.output)
    if output.exists() and not args.force:
        raise FileExistsError(f"Output already exists: {output} (use --force to replace it)")
    staging = output.with_name(f".{output.name}.staging-{os.getpid()}")
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)

    database = connect_read_only(args.database)
    archive_counts: Counter[tuple[str, str]] = Counter()
    file_records: list[dict[str, object]] = []
    total_cells = 0
    current_key: tuple[str, str] | None = None
    current_path: Path | None = None
    current_handle = None
    writer = None
    current_count = 0

    try:
        for row in database.execute(QUERY):
            source_archive = validate_archive_name(row["source_archive"])
            target_archive = validate_archive_name(row["target_archive"])
            csv_rel = validate_relative_path(row["csv_rel"]).as_posix()
            key = (source_archive, csv_rel)
            if key != current_key:
                if current_handle is not None and current_path is not None and current_key is not None:
                    current_handle.close()
                    file_records.append(
                        {
                            "path": current_path.relative_to(staging).as_posix(),
                            "cells": current_count,
                        }
                    )
                current_key = key
                current_count = 0
                current_path = path_for(staging, source_archive, csv_rel)
                current_path.parent.mkdir(parents=True, exist_ok=True)
                current_handle = current_path.open("w", encoding="utf-8", newline="")
                writer = csv.writer(current_handle, lineterminator="\n")
                writer.writerow(CORPUS_HEADER)
            assert writer is not None
            writer.writerow(
                (
                    row["cell_id"], source_archive, target_archive, csv_rel,
                    row["row_index"], row["col_index"], row["header"],
                    row["source_text"], row["target_text"], row["classification"],
                    row["status"], row["reason"], row["source_hash"],
                )
            )
            archive_counts[(source_archive, target_archive)] += 1
            current_count += 1
            total_cells += 1

        if current_handle is not None and current_path is not None:
            current_handle.close()
            current_handle = None
            file_records.append(
                {
                    "path": current_path.relative_to(staging).as_posix(),
                    "cells": current_count,
                }
            )

        manifest = {
            "schema_version": SCHEMA_VERSION,
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "database_sha256": sha256_file(args.database),
            "columns": list(CORPUS_HEADER),
            "total_cells": total_cells,
            "total_csv_files": len(file_records),
            "archives": [
                {
                    "source_archive": source,
                    "target_archive": target,
                    "cells": count,
                    "csv_files": sum(1 for item in file_records if str(item["path"]).startswith(source + "/")),
                }
                for (source, target), count in sorted(archive_counts.items())
            ],
            "files": file_records,
        }
        with (staging / "manifest.json").open("w", encoding="utf-8", newline="\n") as handle:
            json.dump(manifest, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        install_staged_directory(staging, output, args.force)
    except Exception:
        if current_handle is not None:
            current_handle.close()
        if staging.exists():
            shutil.rmtree(staging)
        raise
    finally:
        database.close()

    print(f"Exported {total_cells:,} cells in {len(file_records):,} CSV files to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
