#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import tempfile
import zipfile
from pathlib import Path

from corpus_common import sha256_file, validate_archive_name


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a checksummed GitHub Release ZIP from built MVGL archives.")
    parser.add_argument("--archives", required=True, type=Path, help="Directory containing build_manifest.json")
    parser.add_argument("--repository", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", required=True, type=Path, help="Output ZIP")
    parser.add_argument("--name", default="thl-german-wip")
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def add_file(bundle: zipfile.ZipFile, source: Path, destination: str) -> None:
    bundle.write(source, destination)


def main() -> int:
    args = parse_args()
    archives = args.archives.resolve()
    repository = args.repository.resolve()
    output = args.output.resolve()
    if output.exists() and not args.force:
        raise FileExistsError(f"Output exists (use --force): {output}")
    manifest_path = archives / "build_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not manifest.get("roundtrip_verified"):
        raise RuntimeError("Refusing to package a build without MBE round-trip verification")
    if str(manifest.get("game_build_id")) != "23391396" or int(manifest.get("target_slot", -1)) != 4:
        raise RuntimeError("This packager currently supports only build 23391396, target slot 04")

    records = manifest.get("files", [])
    expected_names = {
        "app_romA_text04.dx11.mvgl",
        "app_steam_text04.dx11.mvgl",
        "app_text04.dx11.mvgl",
        "patch_steam_text04.dx11.mvgl",
        "patch_text04.dx11.mvgl",
    }
    actual_names = {validate_archive_name(str(record["file"])) for record in records}
    if actual_names != expected_names:
        raise RuntimeError(f"Archive set mismatch: expected {sorted(expected_names)}, got {sorted(actual_names)}")

    checksum_lines: list[str] = []
    archive_paths: list[tuple[Path, str]] = []
    for record in sorted(records, key=lambda item: str(item["file"])):
        name = validate_archive_name(str(record["file"]))
        path = archives / name
        if not path.is_file():
            raise FileNotFoundError(path)
        actual_hash = sha256_file(path)
        if actual_hash != record["sha256"] or path.stat().st_size != int(record["size"]):
            raise RuntimeError(f"Build manifest mismatch: {name}")
        checksum_lines.append(f"{actual_hash}  archives/{name}")
        archive_paths.append((path, f"{args.name}/archives/{name}"))

    required_docs = ["INSTALLING.md", "RELEASE_NOTES_ALPHA.md", "CORPUS_NOTICE.md", "THIRD_PARTY_NOTICES.md"]
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent) as temporary:
        checksum_path = Path(temporary) / "SHA256SUMS.txt"
        checksum_path.write_text("\n".join(checksum_lines) + "\n", encoding="utf-8")
        temporary_zip = Path(temporary) / output.name
        with zipfile.ZipFile(temporary_zip, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as bundle:
            for path, destination in archive_paths:
                add_file(bundle, path, destination)
            add_file(bundle, manifest_path, f"{args.name}/build_manifest.json")
            add_file(bundle, checksum_path, f"{args.name}/SHA256SUMS.txt")
            for document in required_docs:
                source = repository / document
                if not source.is_file():
                    raise FileNotFoundError(source)
                add_file(bundle, source, f"{args.name}/{document}")
        temporary_zip.replace(output)

    print(f"Created {output} ({output.stat().st_size:,} bytes, SHA-256 {sha256_file(output)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

