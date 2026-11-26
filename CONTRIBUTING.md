# Contributing

Work in `experiments/wii-static-recomp/`. Preserve the Wii static-recompilation
pipeline; do not revive the retired hand-reconstructed native implementation.
The only validated disc is Wii US R5WEA4 revision 0. PS2 is research-only and
must never become an import, build, or runtime dependency.

Never submit disc images, extracted assets, DOL/ELF files, generated guest code,
saves, user configs, toolchain binaries, captures, or private research logs.
Use synthetic fixtures for public tests. State whether evidence comes from
original Wii code, PS2 research, or a PC adapter, and distinguish offline/mocked
checks from actual gameplay, graphics, sound, FPS and controller acceptance.

Before proposing launcher changes, run:

```sh
python3 -B experiments/wii-static-recomp/verify_launcher_import.py
```

That command tests importer/launcher failure handling using synthetic bytes and
a mocked extractor. It does not start Tk, the game, GPU, audio or input devices.
Actual disc import and game verification require your own supported copy.
Preserve third-party notices and review `LICENSE.md` before redistribution.
