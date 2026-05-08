# _ii live

No-Python, headless multimedia layer for the `_ii` workspace.

This directory is for raw command-line art systems: GLSL framebuffer visuals,
SuperCollider audio patches, ANSI terminal engines, ffmpeg lavfi renders, and
tmux performance layouts. It does not depend on X11, Wayland, or a desktop
session.

## Quick start

From the repo root:

```sh
cd /home/nnn/ii/live
./bin/_ii ansi
./bin/_ii c-ansi
./bin/_ii shader
./bin/_ii audio
./bin/_ii render out/ritual.mkv 20
./bin/_ii tmux
```

## Commands

| Command | What it runs |
| --- | --- |
| `./bin/_ii ansi [field|scan]` | Bash/awk ANSI terminal visual engine |
| `./bin/_ii c-ansi` | C ANSI terminal visual engine, compiled on first run |
| `./bin/_ii shader [file.frag]` | `glslviewer` / `glslViewer` shader |
| `./bin/_ii audio [file.scd]` | headless `sclang` SuperCollider patch |
| `./bin/_ii render [out.mkv] [seconds]` | ffmpeg lavfi audio/video render |
| `./bin/_ii tmux` | tmux layout for live work |

## Environment knobs

```sh
_II_FPS=30 ./bin/_ii ansi
_II_GLSL_ARGS="--drm" ./bin/_ii shader shaders/ion-field.frag
_II_SIZE=1920x1080 _II_FPS=60 ./bin/_ii render out/ritual.mkv 60
CC=clang ./bin/_ii c-ansi
```

`_II_GLSL_ARGS` is intentionally passed through to your local `glslviewer`
build, because direct DRM/KMS flags differ by build and version.

## Layout

```text
live/
├── bin/                # small launchers
├── shaders/            # GLSL fragment shaders
├── scd/                # SuperCollider patches
├── engines/
│   ├── ansi/           # shell/awk terminal visuals
│   ├── c/              # compiled terminal visuals
│   └── ffmpeg/         # lavfi render scripts
├── tmux/               # performance sessions
└── out/                # generated builds/renders
```

