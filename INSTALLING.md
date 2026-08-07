# Installing an experimental build

> [!CAUTION]
> This mod is an unreviewed alpha. It may crash the game. The first public build has not been launched by the automation that produced it. Back up the files below before changing anything.

These instructions apply only to Steam build `23391396` and a slot-04 release package from this repository.

## 1. Close the game

Do not install or remove archives while the game is running.

## 2. Locate `gamedata`

The usual path is:

```text
C:\Program Files (x86)\Steam\steamapps\common\The Hundred Line -Last Defense Academy-\gamedata
```

Your Steam library may be elsewhere.

## 3. Make a backup

Create a new dated directory outside `gamedata`. Copy `boot.json` into it. Also copy any existing files with these names:

```text
app_romA_text04.dx11.mvgl
app_steam_text04.dx11.mvgl
app_text04.dx11.mvgl
patch_steam_text04.dx11.mvgl
patch_text04.dx11.mvgl
```

If no slot-04 file existed, record that fact so you know it should be removed during restoration.

## 4. Verify and copy the release

Compare the downloaded ZIP's SHA-256 with the checksum on the GitHub Release. Extract it, then compare the five files under `archives/` with `SHA256SUMS.txt`.

Copy those five archives into `gamedata`. Do not rename or replace any `text01` English archive.

## 5. Edit `boot.json`

Open the existing `boot.json` and change only the text-language fields. Preserve `voices`, `defaultVoice`, and the entire `rom` object.

The relevant section should become:

```json
"language": {
  "texts": [0, 1, 2, 3, 4, 8],
  "voices": [0, 1],
  "defaultText": 4,
  "defaultVoice": 1
}
```

If your voice values differ, keep your original values. The only required changes are adding `4` to `texts` and setting `defaultText` to `4`.

## Restoring the game

1. Close the game.
2. Restore your original `boot.json`.
3. Restore each slot-04 archive that existed before installation.
4. Delete only the five slot-04 files that came from the release and had no prior counterpart.
5. If needed, use Steam's **Verify integrity of game files** after your own backups are safe.

Report crashes with the game build, release tag, exact scene, and whether restoring the original files stopped the crash.

