"""Verify current GXState/source to pinned texgen arithmetic mapping; no game run."""
from pathlib import Path
import argparse
import json
import subprocess
import tempfile
from stock_debug_font_build import sha


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--texgen-proof', type=Path, required=True)
    args = parser.parse_args()
    proof = json.loads(args.texgen_proof.read_text())
    assert proof['result'] == 'GX_TEXGEN_PINNED_ARITHMETIC_PASS_NOT_RUNTIME_RENDER'
    for path, digest in proof['dependencies'].items():
        assert sha(path) == digest, path
    public = Path(__file__).resolve().parent
    root = public.parents[1]
    gx_state = root / 'work/private-game/static-recomp/stock-baseline/headless-tev-banks/include/runtime/gx_state.h'
    cache = Path(tempfile.mkdtemp(prefix='openshsm-gx-texgen-bridge-', dir='/private/tmp'))
    executable = cache / 'probe'
    command = ['/Library/Developer/CommandLineTools/usr/bin/c++', '-std=c++20',
        '-O1', '-ffp-contract=off', '-fsanitize=address,undefined',
        '-fno-omit-frame-pointer', '-isysroot',
        '/Library/Developer/CommandLineTools/SDKs/MacOSX27.0.sdk',
        '-I', str(public), '-I', str(gx_state.parents[1]),
        str(public / 'stock_gx_texgen_bridge_probe.cpp'), '-o', str(executable)]
    compiled = subprocess.run(command, capture_output=True, text=True, timeout=60)
    (cache / 'compile.log').write_text(compiled.stdout + compiled.stderr)
    assert compiled.returncode == 0, compiled.stderr
    result = subprocess.run([str(executable)], capture_output=True, text=True, timeout=20)
    (cache / 'run.log').write_text(result.stdout + result.stderr)
    assert result.returncode == 0 and 'GX_TEXGEN_BRIDGE_PASS 3channels/dualpost/2guards' in result.stdout, result.stderr
    dependencies = [Path(__file__), args.texgen_proof, gx_state,
        *[public / name for name in ('stock_gx_texgen_bridge.h', 'stock_gx_texgen.h',
            'stock_gx_vertex_sources.h', 'stock_gx_texgen_bridge_probe.cpp')]]
    report = {'result': 'GX_TEXGEN_STATE_BRIDGE_PASS_NOT_GAME_RENDER',
        'output': result.stdout.strip(), 'compileCommand': command,
        'executableSha256': sha(executable),
        'dependencies': {str(path.resolve()): sha(path) for path in dependencies},
        'limits': ['Synthetic current GXState XF/BP and raw source fixture; pinned arithmetic proof preserved.',
            'Caller supplies post-lighting colors, transformed normals, view/light positions and post-matrix bank.',
            'Current renderer does not yet retain XF post matrices or send eight S/T/Q channels to GL.',
            'No original SHSM scene/pixel/FPS/game build acceptance.']}
    path = cache / 'verification.json'
    path.write_text(json.dumps(report, indent=2) + '\n')
    print(report['result'], path, flush=True)


if __name__ == '__main__':
    main()
