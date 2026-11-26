"""Register alternate appearance resources alongside the game's original catalog entries."""
import shutil
import struct

from build_style_assets import directory, read


def extend_package(source, output, additions):
    with source.open("rb") as original, output.open("wb") as dest:
        entries = directory(original)
        original.seek(16)
        toc, = struct.unpack("<Q", original.read(8))
        original.seek(toc)
        header = bytearray(original.read(64))
        original.seek(0)
        shutil.copyfileobj(original, dest)
        dest.seek(toc)
        for key, blob in sorted(additions.items()):
            dest.write(bytes(-dest.tell() % 16))
            entries[key] = dest.tell(), len(blob)
            dest.write(blob)
        dest.write(bytes(-dest.tell() % 16))
        start = dest.tell()
        struct.pack_into("<I", header, 8, len(entries))
        dest.write(header)
        for key, (offset, size) in sorted(entries.items()):
            name = key.encode()
            dest.write(struct.pack("<I", len(name)) + name + b"\0" + struct.pack("<QQ", size, offset))
        dest.truncate()
        dest.seek(16)
        dest.write(struct.pack("<Q", start))


def extend_manifest(stock, pc):
    meshes, mesh_start, textures, texture_start, length, strings = struct.unpack_from("<6Q", stock, len(stock)-48)
    if mesh_start + 24*meshes != texture_start or texture_start + 52*textures != strings or strings+length != len(stock)-48:
        raise ValueError("Unexpected catalog layout")
    names = bytearray(stock[strings:strings+length])
    tables = []
    counts = []
    for ext, start, count, width in [("compressed_mesh", mesh_start, meshes, 24), ("texture", texture_start, textures, 52)]:
        table = bytearray(stock[start:start+count*width])
        seen = set()
        for i in range(count):
            size, pos = struct.unpack_from("<II", table, (i+1)*width-8)
            seen.add(names[pos:pos+size].decode().casefold())
        files = sorted(pc.glob("red_panda_*."+ext))
        for file in files:
            name = file.stem.encode()
            if file.stem.casefold() in seen:
                raise ValueError(f"Duplicate appearance asset: {file.name}")
            seen.add(file.stem.casefold())
            with file.open("rb") as stream:
                header = stream.read(width-12)
            table.extend(header + struct.pack("<III", file.stat().st_size, len(name), len(names)))
            names.extend(name)
        tables.append(table)
        counts.append(count+len(files))
    textures_at = mesh_start+len(tables[0])
    names_at = textures_at+len(tables[1])
    return stock[:mesh_start]+tables[0]+tables[1]+names+struct.pack("<6Q",counts[0],mesh_start,counts[1],textures_at,len(names),names_at)


def build(source, stage):
    key = "data-pc/all.asset_manifest"
    with (source / "levels.package").open("rb") as stream:
        stock = read(stream, directory(stream)[key])
    materials = {p.relative_to(stage).as_posix(): p.read_bytes() for p in (stage/"data/materials").rglob("*.material")}
    for name, additions in [("materials.package", materials), ("levels.package", {key: extend_manifest(stock, stage/"data-pc")})]:
        extend_package(source/name, stage/"data"/name, additions)
