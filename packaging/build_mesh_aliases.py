import re
import shutil
import struct
from pathlib import Path

import lz4.block
from build_style_assets import directory, read


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
