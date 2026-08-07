# The Hundred Line – German Translation

An unofficial, community-editable German fan translation for **The Hundred Line: Last Defense Academy**.

> [!WARNING]
> This is an early, machine-translated work in progress. It has not received a complete editorial QA pass. Expect awkward wording, untranslated fragments, layout problems, and possible game crashes. Keep backups of your saves and game files.

## Project status

- Target: Steam build `23391396`
- Source language slot: English (`01`)
- Experimental target slot: German (`04`)
- First-pass translation: OPUS-MT, with targeted repairs
- Human review: incomplete
- Images, movies, audio, fonts, and executable-embedded text: out of scope

The repository contains bilingual, per-MBE CSV files rather than proprietary game archives. Prebuilt experimental archives, when available, are published separately on the [Releases page](https://github.com/eliasaj92/thl-german-translation/releases).

## Repository layout

```text
corpus/                         English/German cells grouped by archive and native CSV
scripts/export_corpus.py        Export the public corpus from the translation database
scripts/validate_corpus.py      Check structure, hashes, IDs, and control-code parity
scripts/materialize_native.py   Apply German cells to an extracted native CSV tree
scripts/build_archives.py       Repack native CSVs into slot-04 MVGL archives
scripts/package_release.py      Create a checksummed GitHub Release ZIP
supported_builds/               Supported game-build and archive hashes
```

Every corpus CSV uses this schema:

```text
cell_id,source_archive,target_archive,csv_rel,row_index,column_index,field,english,german,classification,status,reason,source_sha256
```

The rows retain stable cell IDs and native row/column coordinates, so fixes can be reviewed and repacked reproducibly.

## Using a prebuilt alpha

1. Confirm your installed Steam build is listed in [SUPPORTED_BUILDS.md](SUPPORTED_BUILDS.md).
2. Download the matching asset from [GitHub Releases](https://github.com/eliasaj92/thl-german-translation/releases).
3. Follow [INSTALLING.md](INSTALLING.md) and back up every file the release replaces.
4. Install only into the matching game build.

Do not redistribute the game or combine these files with pirated copies.

## Building it yourself

See [BUILDING.md](BUILDING.md). You need your own installed copy of the game and [MVGLToolsCLI v2.2.0](https://github.com/SydMontague/MVGLTools/releases/tag/v2.2.0).

## Contributing

Small corrections are welcome even while the project is rough. See [CONTRIBUTING.md](CONTRIBUTING.md). Please preserve all markup and control codes exactly.

## Legal

This project is unofficial and is not affiliated with or endorsed by Aniplex, TooKyo Games, Media.Vision, or any other rightsholder. Game names, English text, characters, and assets remain the property of their respective owners. See [CORPUS_NOTICE.md](CORPUS_NOTICE.md), [LICENSE-CODE.txt](LICENSE-CODE.txt), and [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
