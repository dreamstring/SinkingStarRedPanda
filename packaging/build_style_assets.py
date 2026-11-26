"""Build side-by-side panda assets without overwriting any original game asset."""
import argparse
import hashlib
import json
import struct
from pathlib import Path


def directory(stream):
    stream.seek(16)
    offset, = struct.unpack('<Q', stream.read(8))
    stream.seek(offset)
    header = stream.read(64)
    if header[:4] != b'toc!':
        raise ValueError('Invalid game package header')
    count, = struct.unpack_from('<I', header, 8)
    entries = {}
    for _ in range(count):
        length, = struct.unpack('<I', stream.read(4))
        key = stream.read(length + 1)
        size, position = struct.unpack('<QQ', stream.read(16))
        if key[-1:] != b'\0':
            raise ValueError('Invalid package entry')
        entries[key[:-1].decode()] = position, size
    if len(entries) != count:
        raise ValueError('Duplicate package keys')
    return entries


def read(stream, entry):
    position, size = entry
    stream.seek(position)
    blob = stream.read(size)
    if len(blob) != size:
        raise ValueError('Truncated entry')
    return blob


def build(stock, panda, rules, output):
    output.mkdir(parents=True, exist_ok=False)
    records = []
    for rule in rules:
        path = rule['file']
        original = stock / path
        replacement = panda / path
        for file, field in [(original, 'original'), (replacement, 'modified')]:
            with file.open('rb') as stream:
                if hashlib.file_digest(stream, 'sha256').hexdigest() != rule[field]:
                    raise ValueError(f'{field} file mismatch: {path}')
        def store(key, blob):
            dest = output / key
            dest.resolve().relative_to(output.resolve())
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(blob)
            records.append(dict(source=path, key=key, sha256=hashlib.sha256(blob).hexdigest()))
        if not path.endswith('.package'):
            store(path, replacement.read_bytes())
        elif path in ('data/animation.package', 'data/materials.package'):
            with original.open('rb') as a, replacement.open('rb') as b:
                left, right = directory(a), directory(b)
                if left.keys() - right.keys():
                    raise ValueError('Removed asset keys')
                for key, entry in right.items():
                    blob = read(b, entry)
                    if key not in left or read(a, left[key]) != blob:
                        store(key, blob)
    (output / 'assets.json').write_text(json.dumps(records, indent=2), encoding='utf-8')
    return len(records)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for name in ('stock', 'panda', 'rules', 'output'):
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    print(build(args.stock, args.panda, json.loads(args.rules.read_bytes()), args.output))
