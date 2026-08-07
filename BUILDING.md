# Building the translation

The build is intentionally reproducible and requires files from your own installed copy of the game. The repository does not provide the original MVGL trees or MBE binaries.

## Requirements

- Windows or Linux with Python 3.10 or newer
- A legitimate Steam installation of *The Hundred Line: Last Defense Academy*
- Game build `23391396`
- [MVGLToolsCLI v2.2.0](https://github.com/SydMontague/MVGLTools/releases/tag/v2.2.0)

The expected MVGLTools executable hash is recorded in `supported_builds/23391396.json`.

## 1. Verify the corpus

From the repository root:

```powershell
python scripts/validate_corpus.py corpus
```

Validation checks stable IDs, source hashes, coordinates, protected fields, and preservation of control codes such as `{fc(...)}`, variables, escapes, and tags.

## 2. Extract your English archives

For every `text01` archive listed in `supported_builds/23391396.json`, verify its SHA-256 hash and unpack it independently:

```powershell
MVGLToolsCLI.exe --game=thl --mode=unpack-mvgl <text01-archive> <extracted-mvgl>/<archive-filename>
```

Then unpack every directory containing MBE files:

```powershell
MVGLToolsCLI.exe --game=thl --mode=unpack-mbe-dir <mbe-parent-directory> <source-native>/<archive-filename>/<matching-relative-directory>
```

The resulting roots must look like this:

```text
extracted-mvgl/
  app_text01.dx11.mvgl/
  patch_text01.dx11.mvgl/
  ...
source-native/
  app_text01.dx11.mvgl/
    text/...mbe/*.csv
  patch_text01.dx11.mvgl/
    text/...mbe/*.csv
  ...
```

## 3. Materialize native German CSVs

```powershell
python scripts/materialize_native.py `
  --corpus corpus `
  --source-native C:\path\to\source-native `
  --output-native build\native-de
```

This verifies the English source at every coordinate before writing German values. It produces directories named after the target slot-04 archives.

## 4. Build MVGL archives

```powershell
python scripts/build_archives.py `
  --manifest supported_builds\23391396.json `
  --mvgltools C:\path\to\MVGLToolsCLI.exe `
  --extracted-mvgl C:\path\to\extracted-mvgl `
  --native-de build\native-de `
  --output build\mvgl `
  --tool-log build\mvgltools.log
```

For each archive, the script:

1. copies the corresponding original MVGL tree;
2. runs `pack-mbe-dir`;
3. re-extracts the rebuilt MBEs and compares their CSVs;
4. replaces only matching MBE files in the copied tree;
5. runs `pack-mvgl --compress=normal`.

The build stops on a topology mismatch, round-trip mismatch, missing original MBE, or unsupported tool hash. A `build_manifest.json` with output hashes is written beside the archives.

During this project's first repaired release build, the Windows v2.2.0 binary twice became idle while packing the large app MVGL, although an earlier preflight succeeded. The Linux v2.2.0 binary built the same verified native CSV tree successfully. If the Windows process makes no CPU or output-file progress for several minutes, stop that isolated build, remove its partial output/work directory, and retry or build with the matching Linux v2.2.0 release. Do not install a partial archive.

## 5. Installing

Prebuilt and self-built archives are experimental. Back up every same-named target archive and `boot.json` before installing anything. Slot `04` also requires a compatible `boot.json` language entry. Do not patch the executable.

If the game crashes, restore your backups and report the scene plus the archive/version you used. See [KNOWN_ISSUES.md](KNOWN_ISSUES.md).
