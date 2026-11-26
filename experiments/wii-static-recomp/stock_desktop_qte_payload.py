"""Write and verify a private descriptor for the CPU-validated own-Wii QTE bank."""
import hashlib
import json
from pathlib import Path


HEADER = 'openshsm_owner_qte_payload.h'
PAYLOAD_SHA256 = '5f7a649d927e36266a860f5b41888be648eb7be6a29dd2c58f9279e4ad921406'
DOL_SHA256 = 'ef1a39ea96367ddc0c0070923c247c9bbe56c7c64045795a13430e1e9b00ae6f'


def checked_payload(directory):
    directory = Path(directory)
    path = directory / 'qte-glyphs.txd'
    if path.is_symlink() or not path.is_file() or path.stat().st_size != 5544:
        raise ValueError('QTE payload must be the verified 5544-byte bank')
    payload = path.read_bytes()
    report_path = directory / 'result.json'
    if report_path.is_symlink() or report_path.stat().st_size > 65536:
        raise ValueError('Invalid QTE preparation report')
    report = json.loads(report_path.read_text())
    if not isinstance(report, dict):
        raise ValueError('QTE preparation report must be an object')
    if hashlib.sha256(payload).hexdigest() != PAYLOAD_SHA256 or report.get('txdSha256') != PAYLOAD_SHA256 \
            or report.get('dolSha256') != DOL_SHA256 or report.get('textureCount') != 8 \
            or report.get('txdBytes') != len(payload) or report.get('ps2AssetsUsed') is not False:
        raise ValueError('QTE preparation differs from the native-validated Wii bank')
    return payload


def descriptor(payload):
    if len(payload) != 5544 or hashlib.sha256(payload).hexdigest() != PAYLOAD_SHA256:
        raise ValueError('Unverified QTE descriptor input')
    values = ','.join(map(str, payload))
    guid = ','.join(map(str, hashlib.sha256(payload).digest()[:16]))
    return ('#pragma once\n#include <array>\n#include <cstdint>\n'
        '#define OPENSHSM_OWNER_QTE_PAYLOAD 1\n'
        'namespace openshsm::experiment::prepared_qte {\n'
        'inline constexpr uint8_t bytes[] = {' + values + '};\n'
        'inline constexpr std::array<uint8_t, 16> guid = {' + guid + '};\n}\n').encode()


def write_descriptor(directory, target):
    target = Path(target)
    if target.name != HEADER:
        raise ValueError('Unexpected private QTE descriptor name')
    data = descriptor(checked_payload(directory))
    with target.open('xb') as stream:
        stream.write(data)
    return {'header': HEADER, 'directory': 'desktop-qte', 'txdSha256': PAYLOAD_SHA256,
        'headerSha256': hashlib.sha256(data).hexdigest(), 'dolSha256': DOL_SHA256}


def validate_descriptor(source, metadata):
    source = Path(source)
    path = source / HEADER
    if metadata is None:
        if path.exists() or path.is_symlink():
            raise ValueError('Undeclared private QTE descriptor')
        return
    if not isinstance(metadata, dict):
        raise ValueError('Private QTE descriptor metadata must be an object')
    if metadata.get('header') != HEADER or metadata.get('directory') != 'desktop-qte' \
            or metadata.get('txdSha256') != PAYLOAD_SHA256 or metadata.get('dolSha256') != DOL_SHA256:
        raise ValueError('Invalid private QTE descriptor metadata')
    if path.is_symlink() or not path.is_file():
        raise ValueError('Private QTE descriptor is missing or linked')
    data = descriptor(checked_payload(source / 'desktop-qte'))
    if path.read_bytes() != data or hashlib.sha256(data).hexdigest() != metadata.get('headerSha256'):
        raise ValueError('Private QTE descriptor changed')
