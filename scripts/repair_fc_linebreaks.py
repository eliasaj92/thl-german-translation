#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import re
import sqlite3
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from corpus_common import FC_TEXT_RE, LINE_BREAK_RE, structural_signature


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Restore source CR/LF structure in repaired colored-text cells.")
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--apply", action="store_true", help="Write the verified fixes; otherwise only report them")
    return parser.parse_args()


def reflow_body(source_body: str, target_body: str) -> str:
    breaks = LINE_BREAK_RE.findall(source_body)
    if not breaks:
        return target_body
    source_parts = LINE_BREAK_RE.split(source_body)
    words = re.findall(r"\S+", LINE_BREAK_RE.sub(" ", target_body))
    weights = [len(re.findall(r"\S+", part)) for part in source_parts]
    total_weight = sum(weights)
    if not words or not total_weight:
        segments = [""] * len(source_parts)
        if words:
            segments[-1] = " ".join(words)
    else:
        boundaries = [0]
        cumulative = 0
        for weight in weights[:-1]:
            cumulative += weight
            boundaries.append(round(len(words) * cumulative / total_weight))
        boundaries.append(len(words))
        boundaries = [max(0, min(len(words), value)) for value in boundaries]
        segments = [" ".join(words[boundaries[index] : boundaries[index + 1]]) for index in range(len(source_parts))]
    rebuilt: list[str] = []
    for index, segment in enumerate(segments):
        rebuilt.append(segment)
        if index < len(breaks):
            rebuilt.append(breaks[index])
    return "".join(rebuilt)


def repair_value(source: str, target: str) -> str:
    source_matches = list(FC_TEXT_RE.finditer(source))
    target_matches = list(FC_TEXT_RE.finditer(target))
    if len(source_matches) != len(target_matches):
        raise ValueError("Colored segment count differs")
    replacements: list[str] = []
    for source_match, target_match in zip(source_matches, target_matches):
        if source_match.group("head").lower() != target_match.group("head").lower():
            raise ValueError("Colored segment opcode differs")
        body = target_match.group("body")
        if LINE_BREAK_RE.findall(source_match.group("body")) != LINE_BREAK_RE.findall(body):
            body = reflow_body(source_match.group("body"), body)
        replacements.append("{" + target_match.group("head") + body + "}")
    iterator = iter(replacements)
    repaired = FC_TEXT_RE.sub(lambda _match: next(iterator), target)
    if structural_signature(source) != structural_signature(repaired):
        raise ValueError("Repaired value still has a structural mismatch")
    return repaired


def read_csv(path: Path) -> list[list[str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.reader(handle))


def write_csv(path: Path, rows: list[list[str]]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        csv.writer(handle, lineterminator="\n").writerows(rows)
    temporary.replace(path)


def main() -> int:
    args = parse_args()
    workspace = args.workspace.resolve()
    database_path = workspace / "translation_memory.sqlite"
    database = sqlite3.connect(database_path)
    database.row_factory = sqlite3.Row
    rows = database.execute(
        "SELECT * FROM cells WHERE reason='displayed-string:fc-repair' ORDER BY target_archive,csv_rel,row_index,col_index"
    ).fetchall()
    fixes: list[tuple[sqlite3.Row, str]] = []
    for row in rows:
        if structural_signature(row["source_text"]) == structural_signature(row["target_text"]):
            continue
        fixes.append((row, repair_value(row["source_text"], row["target_text"])))
    print(f"Verified {len(fixes)} colored-text line-break repairs")
    if not args.apply or not fixes:
        database.close()
        return 0

    backup_root = workspace / "backups"
    backup_root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_path = backup_root / f"fc_linebreak_repair_{stamp}.json"
    backup_path.write_text(
        json.dumps(
            [
                {"cell_id": row["cell_id"], "old_target": row["target_text"], "new_target": target}
                for row, target in fixes
            ],
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    by_file: dict[Path, list[tuple[sqlite3.Row, str]]] = defaultdict(list)
    for row, target in fixes:
        by_file[workspace / "de" / row["target_archive"] / Path(row["csv_rel"])].append((row, target))
    for path, file_fixes in by_file.items():
        csv_rows = read_csv(path)
        for row, target in file_fixes:
            row_index = int(row["row_index"])
            column_index = int(row["col_index"])
            if csv_rows[row_index][column_index] != row["target_text"]:
                raise RuntimeError(f"Native German value differs from database: {path}:{row_index}:{column_index}")
            csv_rows[row_index][column_index] = target
        write_csv(path, csv_rows)

    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    database.executemany(
        "UPDATE cells SET target_text=?,reason='displayed-string:fc-repair:linebreak',updated_at=? WHERE cell_id=?",
        ((target, now, row["cell_id"]) for row, target in fixes),
    )
    database.commit()
    database.close()
    print(f"Applied {len(fixes)} repairs across {len(by_file)} CSV files; backup: {backup_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

