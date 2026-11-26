"""Summarize existing read-only loop snapshots, without claiming a FIFO root cause."""
import collections
import re
import struct


def summarize(log, dol, guest_text):
    layout = struct.unpack('>64I', dol[:256])
    sites = []
    for address in (0x802AE4A0, 0x802AE4A8, 0x802AE4BC, 0x802AE504, 0x802AE508, 0x802AD13C):
        word = int(re.search(rf'// 0x{address:08X}: ([0-9A-F]{{8}})', guest_text).group(1), 16)
        section = next(i for i in range(18) if layout[18 + i] <= address < layout[18 + i] + layout[36 + i])
        assert struct.unpack_from('>I', dol, layout[section] + address - layout[18 + section])[0] == word
        sites.append({'address': hex(address), 'word': hex(word)})
    ring, incomplete = [], 0
    for body in re.findall(r'\[LoopPeek\] pc=0x80197498 address=0x8052b220 words=([^\n]*)', log):
        words = body.split()
        if len(words) != 32 or any(not re.fullmatch('[0-9a-fA-F]+', word) for word in words):
            incomplete += 1
            continue
        values = [int(word, 16) for word in words]
        ring.append({'head': values[11], 'tail': values[12], 'rawWords': values})
    cp, stacks = [], []
    for frames, registers in re.findall(r'\[LoopStack\] pc=0x80197498 lr=0x[0-9a-f]+ frames=([^\n]*?) cp=([^\n]*)', log):
        words = registers.split()
        if len(words) != 10 or any(not re.fullmatch('[0-9a-fA-F]+', word) for word in words):
            continue
        values = [int(word, 16) for word in words]
        cp.append({'status': values[0], 'control': values[1], 'distance': values[2] | (values[3] << 16),
            'write': values[4] | (values[5] << 16), 'read': values[6] | (values[7] << 16),
            'breakpoint': values[8] | (values[9] << 16)})
        stacks.append(frames.strip())
    stats = [{'seconds': int(second), 'frames': int(frames), 'draws': int(draws)}
        for second, frames, draws in re.findall(r'\[STAT\] (\d+)s frames=(\d+) draws=(\d+)', log)]
    stalled = [{'bytes': int(count), 'head': bytes(int(word, 16) for word in body.split()).hex()}
        for count, body in re.findall(r'\[GX\] stalled remainder (\d+) bytes, head:((?: [0-9a-f]+){1,24})', log)]
    main = re.findall(r'\[Thread\] 0x80492658 state=([0-9a-f]+) prio=\d+ waitq=0x([0-9a-f]+)', log)
    assert ring and cp and stats and stalled
    return {'sourceSites': sites, 'ring': ring, 'incompleteRingRecords': incomplete,
        'headTailCounts': dict(collections.Counter(f"{row['head']}/{row['tail']}" for row in ring)),
        'cp': cp, 'callerStacks': stacks, 'stats': stats, 'stalled': stalled,
        'mainStates': dict(collections.Counter(row[0] for row in main)),
        'lastMainState': {'state': main[-1][0], 'queue': main[-1][1]} if main else None,
        'limits': ['R13 SDA base8052E720/address interpretation inherited from verified earlier ABI; no root cause from queue state alone.',
            'CP snapshots and ring snapshots are separate reads, not one atomic GPU/CPU transaction.',
            'A three-byte BP prefix needs two further bytes; do not pad/discard/force idle without producer evidence.',
            'Main thread can become ready later; sampled sleep is not a permanent deadlock proof.']}
