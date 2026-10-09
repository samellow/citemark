# Fonts

IBM Plex, under the SIL Open Font License 1.1 (`OFL.txt`), with the reserved font name "Plex". These are IBM's own files, unmodified, so the name is used as IBM ships it.

- **These files**, for pages that load fonts (the admin page and the demo page): the five faces Citemark's type roles use. Plex Sans Condensed 600 (headings and labels), Plex Sans 400 and 600 (text), Plex Mono 400 and 500 (numbers and IDs).
- **`latin1/`**, for the report to embed: the same five faces, from IBM's own Latin-1 split. They hold every character of the report's own text, at about a third of the size. A few characters a quoted help-center passage can hold, such as arrows (→), ⌘ and emoji, show in the reader's system font instead (checked on 2026-10-09 against Zulip's saved help center). A subset made here would be a modified font, which the license allows only under another name.

The widget loads no fonts (design system 5).

## Where they came from

From the npm registry on 2026-10-09, each package checked against its published integrity hash:

| Package | Version | Integrity |
|---|---|---|
| `@ibm/plex-sans-condensed` | 2.0.0 | `sha512-dzgR4Npf/JJMiTYf6iOBQJp…` |
| `@ibm/plex-sans` | 1.1.0 | `sha512-WPgvO6Yfj2w5YbhyAr1tv95…` |
| `@ibm/plex-mono` | 2.5.0 | `sha512-STBJIPxPomOYPmBMO7z5TKP…` |

The complete files are from each package's `fonts/complete/woff2/`, the Latin-1 files from `fonts/split/woff2/`, and `OFL.txt` is the packages' `LICENSE.txt` (the same in all three).

## SHA-256

- `IBMPlexMono-Medium.woff2` 33faf307fa6031fb4062276d7320a6d632de890cbb347576fd80cfa01077bc25
- `IBMPlexMono-Regular.woff2` ba204497f16b6d334cee9d1e963a831b73e3a56e1d6300a8489d18df7214b350
- `IBMPlexSansCondensed-SemiBold.woff2` 385a082a1eac88343eab01fb6746be04b7175dacaf4550b17dee76ea0f78126d
- `IBMPlexSans-Regular.woff2` ba711a3085ff9f27440b6b9c4550cfc47c97bf36591d5da958b975bb3add8c1a
- `IBMPlexSans-SemiBold.woff2` f78048030eab62e860efa39a0df79e2e5581bf122eb95b9bc42c0b8a4988d205
- `latin1/IBMPlexMono-Medium-Latin1.woff2` 41201b658a328b9d00368215c2f1102770f80b15952ab82631e4006255e6365d
- `latin1/IBMPlexMono-Regular-Latin1.woff2` e8993d946649b9d01abb1ed06d574b19d8ea3e66b5c3948602db335c44c18e56
- `latin1/IBMPlexSansCondensed-SemiBold-Latin1.woff2` 6738b1096fd433204a070db0b4a9b1172ad3e6bdff8aad5f05f7351e7c157d06
- `latin1/IBMPlexSans-Regular-Latin1.woff2` b5ad7bd39f996144915f0ad9849a90183b27d8c28ad97ed98af5b1bebc51f6b1
- `latin1/IBMPlexSans-SemiBold-Latin1.woff2` fff0ab3a88b0b4aa0b693e4f0201359a15183b08e3fa5696d1918d8f0ade8ad5
- `OFL.txt` 7e6b2818edbd8f6a01ae80641cc8f16a51080d08fb4e532be3a0b6f74adb07da
