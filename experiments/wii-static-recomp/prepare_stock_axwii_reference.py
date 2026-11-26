"""Pin open-source DSP/GX references only; never fetch game binaries or install runtime code."""
from pathlib import Path
import argparse
import concurrent.futures
import hashlib
import json
import subprocess
import tempfile

REVISION = 'e2ad09306e6d371f7272205bdc363da9fe05fe08'
FILES = ('Source/Core/Core/HW/DSPHLE/UCodes/AXWii.cpp',
    'Source/Core/Core/HW/DSPHLE/UCodes/AXWii.h',
    'Source/Core/Core/HW/DSPHLE/UCodes/AX.cpp',
    'Source/Core/Core/HW/DSPHLE/UCodes/AX.h',
    'Source/Core/Core/HW/DSPHLE/UCodes/AXVoice.h',
    'Source/Core/Core/HW/DSPHLE/UCodes/AXStructs.h',
    'Source/Core/Core/DSP/DSPAccelerator.cpp',
    'Source/Core/Core/DSP/DSPAccelerator.h',
    'Source/Core/Core/HW/DSP.cpp',
    'Source/Core/Core/HW/DSP.h',
    'Source/Core/Core/HW/DSPHLE/MailHandler.cpp',
    'Source/Core/Core/HW/DSPHLE/MailHandler.h',
    'Source/Core/Core/HW/DSPHLE/UCodes/ROM.cpp',
    'Source/Core/Core/HW/DSPHLE/UCodes/UCodes.cpp',
    'Source/Core/Core/HW/DSPHLE/UCodes/UCodes.h',
    'Source/Core/Common/Hash.cpp', 'COPYING')
GRAPHICS_FILES = ('Source/Core/VideoCommon/VertexShaderGen.cpp',
    'Source/Core/VideoCommon/XFMemory.h',
    'Source/Core/VideoBackends/Software/TransformUnit.cpp',
    'Source/Core/Common/Matrix.h',
    'Source/Core/VideoCommon/VertexLoader_Normal.cpp',
    'Source/Core/VideoCommon/VertexLoader_Normal.h', 'COPYING')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--graphics-only', action='store_true')
    args = parser.parse_args()
    files = GRAPHICS_FILES if args.graphics_only else FILES
    cache = Path(tempfile.mkdtemp(prefix='openshsm-gx-reference-' if args.graphics_only else 'openshsm-axwii-reference-', dir='/private/tmp'))
    def fetch(name):
        path = cache / 'dolphin' / name
        path.parent.mkdir(parents=True, exist_ok=True)
        url = f'https://raw.githubusercontent.com/dolphin-emu/dolphin/{REVISION}/{name}'
        result = subprocess.run(['curl', '--fail', '--silent', '--show-error', '--location',
            '--max-time', '25', url, '-o', str(path)], capture_output=True, text=True, timeout=30)
        assert result.returncode == 0, (name, result.stderr)
        assert 0 < path.stat().st_size < 256 * 1024
        if name.endswith(('.h', '.cpp')):
            assert 'SPDX-License-Identifier: GPL-2.0-or-later' in path.read_text()
        print('Pinned reference', name, flush=True)
        return {'url': url, 'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        references = list(pool.map(fetch, files))
    report = {'result': 'PINNED_GX_TEXGEN_REFERENCE_READY_NOT_RUNTIME_CODE' if args.graphics_only else 'PINNED_AXWII_SCHEMA_REFERENCE_READY_NOT_RUNTIME_CODE',
        'revision': REVISION, 'references': references,
        'preparerSha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'limits': ['Open-source reference only; no game binary/assets downloaded.',
            'No source compiled or installed in runtime; memory/update bounds require independent review before execution.',
            'Variant schema/PCM/original hardware behavior and redistribution licensing remain separate checks.']}
    path = cache / 'reference.json'
    path.write_text(json.dumps(report, indent=2) + '\n')
    print(report['result'], path, flush=True)


if __name__ == '__main__':
    main()
