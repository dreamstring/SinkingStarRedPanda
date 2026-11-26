"""Register alternate appearance resources alongside the game's original catalog entries."""
import shutil
import struct
import re
from pathlib import Path

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


def animation_aliases(package, assets):
    additions = {}
    clips = {}
    for clip in (assets / "data-common").glob("*.anim"):
        alias = "red_panda_" + clip.stem
        clips[clip.stem.lower().encode()] = alias.encode()
        additions["data-common/" + alias + ".anim"] = clip.read_bytes()
    with package.open("rb") as stream:
        table = directory(stream)
        for key in table.keys() | {p.relative_to(assets).as_posix() for p in assets.rglob("*.sound_events")}:
            path = Path(key)
            if path.suffix == ".sound_events" and path.stem.lower().encode() in clips:
                override = assets / path
                sound = override.read_bytes() if override.exists() else read(stream, table[key])
                additions[path.with_name("red_panda_" + path.name).as_posix()] = sound
        for names in (assets / "data/animations").glob("*.animation_names"):
            key = names.relative_to(assets)
            graph = key.with_suffix(".animation_graph")
            additions[graph.with_name("red_panda_" + graph.name).as_posix()] = read(stream, table[graph.as_posix()])
            def resolve(match):
                name = match[2]
                return match[1] + clips.get(name.lower(), name)
            additions[key.with_name("red_panda_" + key.name).as_posix()] = re.sub(
                rb"(?m)^([ \t]*[^#\s]+[ \t]+)([^#\s]+)", resolve, names.read_bytes())
    return additions


def build(source, stage):
    key = "data-pc/all.asset_manifest"
    with (source / "levels.package").open("rb") as stream:
        stock = read(stream, directory(stream)[key])
    materials = {p.relative_to(stage).as_posix(): p.read_bytes() for p in (stage/"data/materials").rglob("*.material")}
    assets = stage / "ssmods/RedPanda/assets"
    animations = animation_aliases(source / "animation.package", assets)
    for name, additions in [("materials.package", materials), ("animation.package", animations),
                            ("levels.package", {key: extend_manifest(stock, stage/"data-pc")})]:
        extend_package(source/name, stage/"data"/name, additions)
