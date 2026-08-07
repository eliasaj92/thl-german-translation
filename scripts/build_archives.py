#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from corpus_common import ensure_safe_replace_target, sha256_file, validate_archive_name


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build slot-04 MVGL archives from native German CSV trees.")
    parser.add_argument("--manifest", required=True, type=Path, help="supported_builds/<build>.json")
    parser.add_argument("--mvgltools", required=True, type=Path, help="MVGLToolsCLI executable or its directory")
    parser.add_argument("--extracted-mvgl", required=True, type=Path, help="Original unpack-mvgl output root")
    parser.add_argument("--native-de", required=True, type=Path, help="materialize_native.py output root")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--work", type=Path, help="Temporary work root (default: beside output)")
    parser.add_argument("--force", action="store_true", help="Replace matching output archives and work data")
    parser.add_argument("--skip-roundtrip", action="store_true", help="Skip MBE re-extraction comparison (not recommended)")
    parser.add_argument("--allow-tool-hash-mismatch", action="store_true")
    parser.add_argument("--keep-work", action="store_true")
    parser.add_argument("--tool-log", type=Path, help="Write verbose MVGLTools output to this file")
    return parser.parse_args()


def locate_tool(value: Path) -> Path:
    value = value.resolve()
    candidates = [value] if value.is_file() else [value / "MVGLToolsCLI.exe", value / "MVGLToolsCLI"]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(f"Could not find MVGLToolsCLI at {value}")


def run(tool: Path, *arguments: str, output=None) -> None:
    command = [str(tool), "--game=thl", *arguments]
    print("+ " + " ".join(command))
    subprocess.run(
        command,
        cwd=tool.parent,
        check=True,
        stdout=output,
        stderr=subprocess.STDOUT if output is not None else None,
    )


def read_csv(path: Path) -> list[list[str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.reader(handle))


def compare_csv_trees(expected: Path, actual: Path) -> list[str]:
    expected_files = {path.relative_to(expected).as_posix(): path for path in expected.rglob("*.csv")}
    actual_files = {path.relative_to(actual).as_posix(): path for path in actual.rglob("*.csv")}
    errors: list[str] = []
    missing = sorted(set(expected_files) - set(actual_files))
    unexpected = sorted(set(actual_files) - set(expected_files))
    errors.extend(f"Missing round-trip CSV: {value}" for value in missing[:20])
    errors.extend(f"Unexpected round-trip CSV: {value}" for value in unexpected[:20])
    for relative in sorted(set(expected_files) & set(actual_files)):
        if read_csv(expected_files[relative]) != read_csv(actual_files[relative]):
            errors.append(f"Round-trip CSV content differs: {relative}")
            if len(errors) >= 20:
                break
    return errors


def prepare_output(output: Path, force: bool) -> None:
    output = ensure_safe_replace_target(output)
    if output.exists() and not output.is_dir():
        raise NotADirectoryError(output)
    output.mkdir(parents=True, exist_ok=True)
    existing = list(output.glob("*.mvgl")) + list(output.glob("build_manifest.json"))
    if existing and not force:
        raise FileExistsError(f"Build output already contains archives (use --force): {output}")


def main() -> int:
    args = parse_args()
    config = json.loads(args.manifest.read_text(encoding="utf-8"))
    tool = locate_tool(args.mvgltools)
    expected_tool_hash = config["mvgltools"]["executable_sha256"]
    actual_tool_hash = sha256_file(tool)
    if actual_tool_hash != expected_tool_hash and not args.allow_tool_hash_mismatch:
        raise RuntimeError(
            f"MVGLToolsCLI SHA-256 mismatch: expected {expected_tool_hash}, got {actual_tool_hash}. "
            "Use --allow-tool-hash-mismatch only after verifying the tool version yourself."
        )

    extracted_root = args.extracted_mvgl.resolve()
    native_root = args.native_de.resolve()
    output = ensure_safe_replace_target(args.output)
    prepare_output(output, args.force)
    work = ensure_safe_replace_target(args.work or output.with_name(f".{output.name}-work"))
    if work.exists():
        if not args.force:
            raise FileExistsError(f"Work directory exists (use --force): {work}")
        shutil.rmtree(work)
    work.mkdir(parents=True)
    tool_log_handle = None
    if args.tool_log:
        tool_log_path = args.tool_log.resolve()
        tool_log_path.parent.mkdir(parents=True, exist_ok=True)
        tool_log_handle = tool_log_path.open("wb")

    build_records: list[dict[str, object]] = []
    try:
        for archive_record in config["archives"]:
            source_archive = validate_archive_name(archive_record["source_archive"])
            target_archive = validate_archive_name(archive_record["target_archive"])
            source_tree = extracted_root / source_archive
            german_tree = native_root / target_archive
            if not source_tree.is_dir():
                raise FileNotFoundError(f"Missing original MVGL tree: {source_tree}")
            if not german_tree.is_dir():
                raise FileNotFoundError(f"Missing native German CSV tree: {german_tree}")

            archive_work = work / target_archive
            staging_mvgl = archive_work / "mvgl"
            packed_mbe = archive_work / "packed-mbe"
            roundtrip = archive_work / "roundtrip"
            shutil.copytree(source_tree, staging_mvgl)

            mbe_directories = sorted(path for path in german_tree.rglob("*.mbe") if path.is_dir())
            if not mbe_directories:
                raise RuntimeError(f"No native MBE directories found: {german_tree}")
            mbe_parents = sorted({path.parent for path in mbe_directories})
            for csv_parent in mbe_parents:
                relative_parent = csv_parent.relative_to(german_tree)
                packed_parent = packed_mbe / relative_parent
                packed_parent.mkdir(parents=True, exist_ok=True)
                run(tool, "--mode=pack-mbe-dir", str(csv_parent), str(packed_parent), output=tool_log_handle)
                if not args.skip_roundtrip:
                    roundtrip_parent = roundtrip / relative_parent
                    roundtrip_parent.mkdir(parents=True, exist_ok=True)
                    run(tool, "--mode=unpack-mbe-dir", str(packed_parent), str(roundtrip_parent), output=tool_log_handle)

            packed_files = sorted(packed_mbe.rglob("*.mbe"))
            if len(packed_files) != len(mbe_directories):
                raise RuntimeError(
                    f"Packed MBE count mismatch for {target_archive}: "
                    f"expected {len(mbe_directories)}, got {len(packed_files)}"
                )
            if not args.skip_roundtrip:
                errors = compare_csv_trees(german_tree, roundtrip)
                if errors:
                    raise RuntimeError("\n".join(errors))

            for packed in packed_files:
                relative = packed.relative_to(packed_mbe)
                destination = staging_mvgl / relative
                if not destination.is_file():
                    raise FileNotFoundError(f"Packed MBE has no original counterpart: {relative}")
                shutil.copy2(packed, destination)

            output_archive = output / target_archive
            if output_archive.exists() and not args.force:
                raise FileExistsError(output_archive)
            run(
                tool,
                "--mode=pack-mvgl",
                str(staging_mvgl),
                str(output_archive),
                "--compress=normal",
                output=tool_log_handle,
            )
            build_records.append(
                {
                    "file": target_archive,
                    "size": output_archive.stat().st_size,
                    "sha256": sha256_file(output_archive),
                    "mbe_count": len(packed_files),
                }
            )

        build_manifest = {
            "schema_version": 1,
            "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "game_build_id": config["build_id"],
            "target_slot": config["target_slot"],
            "mvgltools_sha256": actual_tool_hash,
            "roundtrip_verified": not args.skip_roundtrip,
            "files": build_records,
        }
        (output / "build_manifest.json").write_text(
            json.dumps(build_manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    finally:
        if tool_log_handle is not None:
            tool_log_handle.close()
        if work.exists() and not args.keep_work:
            shutil.rmtree(work)

    print(f"Built {len(build_records)} archives in {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
