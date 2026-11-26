"""Check the actual positional main contract and guard both old and corrected launches."""
from pathlib import Path
import io
import tempfile
from unittest.mock import patch
from run_stock_pc_play import active_game_commands, play_command, BoundedCapture

with tempfile.TemporaryDirectory(prefix='openshsm-pc-arguments-') as directory:
    root = Path(directory)
    exe = root / 'OpenSHSM-0.0.42'
    game = root / 'game/DATA'
    config = root / 'config path/config.toml'
    source = root / 'main.cpp'
    source.write_text('const char *config_path = (argc >= 3) ? argv[2] : "config.toml";\n')
    assert play_command(exe, game, config) == [str(exe), str(game), str(config)]
    assert '--config' not in play_command(exe, game, config)
    assert 'const char *config_path = (argc >= 3) ? argv[2] : "config.toml";' in source.read_text()
    legacy = f'1754 {exe} {game} --config {config}'
    corrected = f'1755 {exe} {game} {config}'
    unrelated = f'1756 python3 observer.py --source {game} --config {config}'
    assert active_game_commands('\n'.join([legacy, corrected, unrelated]), game) == [legacy, corrected]
    assert active_game_commands('', game) == []
    assert active_game_commands('broken-line', game) == []
prefix, tail = io.BytesIO(), io.BytesIO()
capture = BoundedCapture(prefix, tail, 17, 9)
data = b'abcde' * 10000
for offset in range(0, len(data), 31):
    capture.feed(data[offset:offset + 31])
capture.finish()
assert prefix.getvalue() == data[:17] and tail.getvalue() == data[-9:]
assert capture.total == len(data)
with patch('run_stock_pc_play.time.monotonic', return_value=0) as clock:
    prefix, tail = io.BytesIO(), io.BytesIO()
    capture = BoundedCapture(prefix, tail, 5, 9)
    capture.feed(b'first')
    assert tail.getvalue() == b''
    clock.return_value = 1
    capture.feed(b'0123456789abcdef')
    assert prefix.getvalue() == b'first' and tail.getvalue() == b'789abcdef'
    clock.return_value = 1.5
    capture.feed(b'XY')
    assert tail.getvalue() == b'789abcdef'
    clock.return_value = 2
    capture.feed(b'Z')
    assert tail.getvalue() == b'abcdefXYZ' and capture.total == 24
    capture.finish()
    capture.finish()
    assert tail.getvalue() == b'abcdefXYZ'
with patch('run_stock_pc_play.time.monotonic', return_value=0) as clock:
    prefix, tail = io.BytesIO(), io.BytesIO(b'obsolete tail contents')
    capture = BoundedCapture(prefix, tail, 5, 9)
    clock.return_value = 1
    capture.feed(b'new')
    assert tail.getvalue() == b'new'
print('PC_PLAY_POSITIONAL_CONFIG_LEGACY_AND_CURRENT_INSTANCE_GUARD_LOG_CAP_PASS')
