# Repository preparation and remaining acceptance

This directory is a source-only candidate, not an accepted playable release.
It is prepared without initializing Git, creating commits or uploading files.

Included: active source, supported-copy fingerprints, recovery/build/import
scripts, first-run launcher, dependency instructions and third-party notices.
Excluded: original game data/code, generated translations, executables, SDKs,
saves and private development evidence. The snapshot manifest records hashes.

Before upload, verify the untouched candidate from its root:

```sh
python3 -B experiments/wii-static-recomp/verify_public_repository.py .
python3 -B experiments/wii-static-recomp/verify_launcher_import.py
python3 -B experiments/wii-static-recomp/verify_launcher_locale.py
```

The manifest audit is intended for the fresh snapshot before Git initialization.
It rejects `.git` and any files not recorded in the snapshot. If you edit files,
regenerate the candidate from the maintained source instead of editing hashes
to hide a difference.

Remaining before a playable public release:
- Preserve OpenSHSM, NWiiRecomp and other third-party license notices.
- Extract a real supported own-Wii image with external DolphinTool from a fresh
  directory; repeat preparation/build/launch on an independent machine.
- Confirm first-run UI and Windows wrapper on their actual target systems.
- Accept graphics/brightness, full audio, controls/puzzles, stable performance,
  full story and saves. Physical Wiimote+Nunchuk support remains a requirement.

No compatibility with other disc regions/revisions is claimed. See README.md
for the experimental build status and explicit external dependencies.
