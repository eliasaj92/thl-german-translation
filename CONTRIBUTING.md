# Contributing

This is deliberately a work-in-progress project. Corrections to individual lines, terminology, punctuation, and character voice are welcome.

## Editing a line

1. Find the English text with repository search.
2. Edit only the `german` field in the matching bilingual CSV row.
3. Keep `cell_id`, archive names, path, coordinates, field name, English source, classification, reason, and hash unchanged.
4. Preserve every control code, tag, variable, escape, and explicit line break.
5. Run `python scripts/validate_corpus.py corpus`.
6. In a pull request, mention where the line appears and why the new wording is better.

Do not submit game binaries, original MVGL archives, copyrighted images/audio, save files containing personal information, or API credentials.

## German style

- Use natural contemporary `de-DE`.
- Preserve names and retained honorifics unless there is a documented project-wide decision.
- Preserve profanity, dark humor, and emotional intensity rather than sanitizing them.
- Keep `du`/`Sie` consistent with established character relationships.
- Prefer concise phrasing where a text box is tight.

## Licensing your contribution

By contributing, you agree to the terms in [CORPUS_NOTICE.md](CORPUS_NOTICE.md). You must have the right to submit your changes.

