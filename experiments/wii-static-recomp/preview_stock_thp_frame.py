"""Render decoded CPU planes for inspection; never claim this is a GX/game-window capture."""
from pathlib import Path
import ast
import argparse
import hashlib
import json
import subprocess

parser = argparse.ArgumentParser()
parser.add_argument('--directory', default='colored-replay')
args = parser.parse_args()
assert args.directory.replace('-', '').isalnum()
root = Path('work/private-game/static-recomp/stock-baseline/headless-thp-snapshot', args.directory).resolve()
public = Path('experiments/wii-static-recomp').resolve()
proof = json.loads((root / 'verification.json').read_text())
path = root / 'headless-constant-fp-0.yuv'
row = next(row for row in proof['rows'] if row['variant'] == 'headless-constant-fp' and row['iteration'] == 0)
data = path.read_bytes()
assert hashlib.sha256(data).hexdigest() == row['outputSha256'] and len(data) == 460800
node = next(node for node in ast.parse((public / 'compare_stock_thp.py').read_text()).body
    if isinstance(node, ast.FunctionDef) and node.name == 'untile')
scope = {}
exec(compile(ast.Module(body=[node], type_ignores=[]), 'existing_untile', 'exec'), scope)
linear = b''
position = 0
for width, height in ((640, 480), (320, 240), (320, 240)):
    length = width * height
    linear += scope['untile'](data[position:position + length], width, height)
    position += length
ffmpeg = proof['referenceCommand'][0]
result = subprocess.run([ffmpeg, '-hide_banner', '-loglevel', 'error', '-f', 'rawvideo',
    '-pixel_format', 'yuvj420p', '-video_size', '640x480', '-i', 'pipe:0', '-frames:v', '1',
    '-f', 'image2pipe', '-vcodec', 'png', 'pipe:1'], input=linear, capture_output=True, check=True, timeout=30)
preview = root / 'native-frame-cpu-preview.png'
preview.write_bytes(result.stdout)
(root / 'preview.json').write_text(json.dumps({'kind': 'CPU_PLANE_SOFTWARE_YUV_TO_RGB_PREVIEW_NOT_GX_CAPTURE',
    'sourceSha256': row['outputSha256'], 'proofSha256': hashlib.sha256((root / 'verification.json').read_bytes()).hexdigest(),
    'pngSha256': hashlib.sha256(result.stdout).hexdigest(),
    'rendererSha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}, indent=2) + '\n')
print(preview)
