"""Exercise copy-identity refusals without reproducing any game file."""
from pathlib import Path
import json
import tempfile
from verify_wii_us_copy import audit_copy, check_file, digest


def rejects(action, phrase):
    try:
        action()
    except ValueError as error:
        assert phrase in str(error), error
    else:
        raise AssertionError(phrase)


with tempfile.TemporaryDirectory(prefix='openshsm-wii-copy-inputs-', dir='/private/tmp') as temporary:
    root = Path(temporary)
    data = root / 'DATA'
    (data / 'sys').mkdir(parents=True)
    boot = data / 'sys/boot.bin'
    boot.write_bytes(b'R5WEA4\0\0')
    rejects(lambda: audit_copy(root), 'Missing or wrong-sized')
    boot.write_bytes(b'R5WEA4\0\1')
    rejects(lambda: audit_copy(root), 'R5WEA4 revision 0')
    boot.write_bytes(b'R5WPA4\0\0')
    rejects(lambda: audit_copy(root), 'R5WEA4 revision 0')
    boot.unlink()
    (root / 'other-boot').write_bytes(b'R5WEA4\0\0')
    boot.symlink_to(root / 'other-boot')
    rejects(lambda: audit_copy(data), 'Boot header must not be a symlink')
    sample = data / 'sample'
    sample.write_bytes(b'1234')
    rejects(lambda: check_file(data, Path('sample'),
        {'bytes': 4, 'sha256': '0' * 64}), 'SHA-256 mismatch')
    rejects(lambda: check_file(data, Path('sample'),
        {'bytes': 5, 'sha256': digest(sample)}), 'wrong-sized')
    sample.unlink()
    sample.symlink_to(root / 'other-sample')
    rejects(lambda: check_file(data, Path('sample'),
        {'bytes': 4, 'sha256': '0' * 64}), 'Symlink')
    report = {'result': 'WII_COPY_SEVEN_INVALID_INPUTS_REFUSED', 'cases': 7,
        'limits': ['Synthetic malformed paths and headers only; actual owner copy separately verified.']}
    print(json.dumps(report))
