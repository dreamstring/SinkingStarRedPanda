import hashlib
import re
import shutil
import struct
from pathlib import Path

import lz4.block
from build_style_assets import directory, read


def correct_druid_antlers(raw):
    # Six eight-vertex branches in the verified quadruped asset, across all LODs.
    data = bytearray(raw)
    vertices, = struct.unpack_from("<I", data, 4)
    slots, = struct.unpack_from("<I", data, 52)
    offset = 56 + 44 * vertices
    for _ in range(3):
        indices, size = struct.unpack_from("<II", data, offset + 12 * slots)
        first = offset + 12 * slots + 10
        corrected = 0
        for face in range(first, first + 2 * indices, 6):
            a, b, c = struct.unpack_from("<3H", data, face)
            if 16973 <= min(a, b, c) and max(a, b, c) <= 17020:
                struct.pack_into("<3H", data, face, c, b, a)
                corrected += 1
        if corrected != 144:
            raise ValueError("Unexpected antler triangle count")
        offset = first + size
    return bytes(data)


def correct_trader_panniers(raw):
    """Restore front and reverse winding for the two verified merchant meshes."""
    data = bytearray(raw)
    vertices, = struct.unpack_from("<I", data, 4)
    slots, = struct.unpack_from("<I", data, 52)
    offset = 56 + 44 * vertices
    for _ in range(3):
        header = offset + 12 * slots
        count, size = struct.unpack_from("<II", data, header)
        start = header + 10
        front_count = count // 6
        # Faces relative to the end of the front copy: bases, curved lid, two caps.
        for relative, length in ((-2548, 64), (-2484, 72), (-2401, 11), (-1618, 11)):
            for index in range(front_count + relative, front_count + relative + length):
                front = start + index * 6
                back = front + front_count * 6
                a, b, c = struct.unpack_from("<3H", data, front)
                if struct.unpack_from("<3H", data, back) != (c, b, a):
                    raise ValueError("Unexpected merchant reverse-face layout")
                face = (c, b, a) if relative == -2548 else (a, c, b)
                struct.pack_into("<3H", data, front, *face)
                struct.pack_into("<3H", data, back, *reversed(face))
        offset = start + size
    return bytes(data)


def build_mesh_outlines(source, stage):
    data = source.read_bytes()
    native = dict(row.split() for row in data.splitlines() if row.strip())
    additions = []
    for mesh in sorted((stage / "data-pc").glob("red_panda_*.compressed_mesh")):
        alias = mesh.stem.encode()
        role = alias[len(b"red_panda_"):]
        material = native.get(role) or native.get(role.removesuffix(b"_alt"))
        if not material:
            raise ValueError(f"Missing native mesh outline for {mesh.stem}")
        additions.append(alias + b" " + material)
    newline = b"\r\n" if b"\r\n" in data else b"\n"
    (stage / "data" / source.name).write_bytes(data.rstrip(b"\r\n") + newline +
                                             newline.join(additions) + newline)


def build(assets, original_materials, stage):
    pc = stage / "data-pc"
    pc.mkdir(exist_ok=True)
    textures = {p.stem.lower(): p for p in (assets / "data-pc").glob("*.texture")}
    for texture in textures.values():
        shutil.copyfile(texture, pc / ("red_panda_" + texture.name))

    material_refs = {}
    parents = {}
    with original_materials.open("rb") as stream:
        for key, entry in directory(stream).items():
            path = Path(key)
            if path.suffix != ".material":
                continue
            override = assets / key
            data = override.read_bytes() if override.exists() else read(stream, entry)
            def texture_ref(match):
                name = match[1].decode("ascii").lower()
                return (b'"red_panda_' + textures[name].stem.encode() + b'"'
                        if name in textures else match[0])
            adapted = re.sub(rb'"([A-Za-z0-9_-]+)"', texture_ref, data)
            parent = re.search(rb'(?m)^parent "([^"]+)"', data)
            if parent:
                parents[path.stem.lower().encode()] = (path, adapted, parent[1].lower())
            if adapted == data and not override.exists():
                continue
            material_refs[path.stem.lower().encode()] = (path, adapted)

    while parents:
        children = [name for name, (_, _, parent) in parents.items() if parent in material_refs]
        if not children:
            break
        for name in children:
            path, data, parent = parents.pop(name)
            parent_path, parent_data = material_refs[parent]
            dest = stage / parent_path.with_name("red_panda_" + parent_path.name)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(parent_data)
            data = re.sub(rb'(?m)^parent "[^"]+"', b'parent "red_panda_' +
                          parent_path.stem.encode() + b'"', data)
            material_refs[name] = (path, data)

    for mesh in (assets / "data-pc").glob("*.compressed_mesh"):
        blob = mesh.read_bytes()
        size, = struct.unpack_from("<I", blob, 8)
        raw = lz4.block.decompress(blob[12:], uncompressed_size=size - 12)
        if mesh.stem == "druid" and hashlib.sha256(blob).hexdigest() == (
            "1ed9499bf0fa4cefc1ef3d80a51d36a232f9bab61a96498a429e2653f8beda9c"
        ):
            raw = correct_druid_antlers(raw)
        if (mesh.stem, hashlib.sha256(blob).hexdigest()) in {
            ("trader", "6e3661b56b9953883f0fa3ee1d652cf39605015a3510137fcac2b437e4a74a57"),
            ("trader_alt", "38dd09b5289927792e994db148e1ccba7f4f406144db6ba55e21048df81bd062"),
        }:
            raw = correct_trader_panniers(raw)
        # Mesh material names are ASCII strings preceded by their uint16 byte count.
        def mesh_ref(match):
            name = match[2]
            if int.from_bytes(match[1], "little") != len(name):
                return match[0]
            path, data = material_refs[name.lower()]
            dest = stage / path.with_name("red_panda_" + path.name)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
            alias = b"red_panda_" + path.stem.encode()
            return struct.pack("<H", len(alias)) + alias
        pattern = rb"(.{2})(" + b"|".join(re.escape(n) for n in sorted(material_refs, key=len, reverse=True)) + rb")"
        adapted = re.sub(pattern, mesh_ref, raw, flags=re.I | re.S)
        result = blob[:8] + struct.pack("<I", len(adapted) + 12) + lz4.block.compress(adapted, store_size=False)
        (pc / ("red_panda_" + mesh.name)).write_bytes(result)

    build_mesh_outlines(original_materials.with_name("mesh_outlines.mesh_outlines"), stage)
