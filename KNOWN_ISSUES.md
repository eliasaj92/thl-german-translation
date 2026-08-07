# Known issues

- The translation is primarily machine-generated and has not completed editorial QA.
- Some short labels and ambiguous single-token cells remain in `review`/`pending` state.
- German text often expands beyond English and may overflow text boxes.
- Colored text is encoded as displayed text inside `{fc(...)...}` markup. An early extraction pass mistakenly protected some bodies; the current corpus snapshot includes a targeted repair plus independent control-code and CRLF validation.
- Slot `04` is experimental. Compatibility may differ across game builds.
- A previous experimental build reached gameplay but crashed after text replacement. Public release notes must state whether that failure is resolved.
- Text embedded in images, movies, audio, fonts, or the executable is not translated.

Please include the game build, release tag, scene, and exact on-screen line in bug reports.
