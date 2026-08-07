from __future__ import annotations

import csv
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY / "scripts"))

from corpus_common import stable_cell_id


class PipelineTests(unittest.TestCase):
    def test_export_validate_and_materialize(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            database_path = root / "memory.sqlite"
            database = sqlite3.connect(database_path)
            database.execute(
                """
                CREATE TABLE cells (
                    cell_id TEXT PRIMARY KEY, source_archive TEXT, target_archive TEXT,
                    csv_rel TEXT, row_index INTEGER, col_index INTEGER, header TEXT,
                    source_text TEXT, target_text TEXT, classification TEXT, reason TEXT,
                    status TEXT, source_hash TEXT, tokens_json TEXT, updated_at TEXT
                )
                """
            )
            source_archive = "app_text01.dx11.mvgl"
            target_archive = "app_text04.dx11.mvgl"
            csv_rel = "text/example.mbe/000_Sheet1.csv"
            english = "Use {fc(ff0000)Fatigue} now"
            german = "Nutze jetzt {fc(ff0000)Erschöpfung}"
            import hashlib

            database.execute(
                "INSERT INTO cells VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    stable_cell_id(target_archive, csv_rel, 1, 1),
                    source_archive,
                    target_archive,
                    csv_rel,
                    1,
                    1,
                    "string 1",
                    english,
                    german,
                    "translate",
                    "displayed-string",
                    "translated",
                    hashlib.sha256(english.encode("utf-8")).hexdigest(),
                    "[]",
                    "2026-01-01T00:00:00+00:00",
                ),
            )
            database.commit()
            database.close()

            corpus = root / "corpus"
            subprocess.run(
                [sys.executable, str(REPOSITORY / "scripts" / "export_corpus.py"), "--database", str(database_path), "--output", str(corpus)],
                check=True,
                capture_output=True,
                text=True,
            )
            # A contributor may edit the German field without regenerating the
            # manifest. Immutable IDs, source hashes, paths, and structure are
            # still validated independently.
            public_csv = corpus / source_archive / "text" / "example.mbe" / "000_Sheet1.csv"
            with public_csv.open("r", encoding="utf-8", newline="") as handle:
                public_rows = list(csv.DictReader(handle))
            german = "Verwende jetzt {fc(ff0000)Erschöpfung}"
            public_rows[0]["german"] = german
            with public_csv.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=public_rows[0].keys(), lineterminator="\n")
                writer.writeheader()
                writer.writerows(public_rows)
            subprocess.run(
                [sys.executable, str(REPOSITORY / "scripts" / "validate_corpus.py"), str(corpus)],
                check=True,
                capture_output=True,
                text=True,
            )

            source_native = root / "source-native" / source_archive / "text" / "example.mbe"
            source_native.mkdir(parents=True)
            with (source_native / "000_Sheet1.csv").open("w", encoding="utf-8", newline="") as handle:
                csv.writer(handle, lineterminator="\n").writerows((("int 0", "string 1"), ("1", english)))
            output_native = root / "native-de"
            subprocess.run(
                [
                    sys.executable,
                    str(REPOSITORY / "scripts" / "materialize_native.py"),
                    "--corpus",
                    str(corpus),
                    "--source-native",
                    str(root / "source-native"),
                    "--output-native",
                    str(output_native),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            with (output_native / target_archive / "text" / "example.mbe" / "000_Sheet1.csv").open(
                "r", encoding="utf-8", newline=""
            ) as handle:
                rows = list(csv.reader(handle))
            self.assertEqual(rows[1][1], german)


if __name__ == "__main__":
    unittest.main()
