"""Assemble the private installer payload from verified assets and built binaries."""
import argparse
import hashlib
import json
import shutil
import tempfile
from pathlib import Path

from build_menu_strings import build as build_strings
from build_mesh_aliases import build as build_aliases
from build_catalogs import build as build_catalogs
from build_game_menu import build as build_game_menu, STOCK


def verify_runtime(path):
    # Map the candidate without running its entry point or loading dependencies.
    import ctypes
    from ctypes import wintypes

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.LoadLibraryExW.argtypes = [wintypes.LPCWSTR, wintypes.HANDLE, wintypes.DWORD]
    kernel.LoadLibraryExW.restype = wintypes.HMODULE
    kernel.GetProcAddress.argtypes = [wintypes.HMODULE, ctypes.c_char_p]
    kernel.GetProcAddress.restype = ctypes.c_void_p
    kernel.FreeLibrary.argtypes = [wintypes.HMODULE]
    handle = kernel.LoadLibraryExW(str(path.resolve()), None, 1)
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        for name in ("RedPandaMenuRow", "RedPandaConfirmMenuRow", "RedPandaSelectedStyle",
                     "RedPandaProfessionName", "RedPandaApplyScene", "RedPandaDrawInstalledPage",
                     "RedPandaUpdateInstalledScene", "RedPandaClassifyInstalledProfession"):
            if not kernel.GetProcAddress(handle, name.encode("ascii")):
                raise ValueError(f"{path} lacks required runtime export {name}")
    finally:
        kernel.FreeLibrary(handle)


def stage_resources(assets, strings, stage):
    root = stage / "ssmods" / "RedPanda" / "assets"
    root.mkdir(parents=True)
    index = assets / "assets.json"
    for record in json.loads(index.read_bytes()):
        key = record["key"]
        source = (assets / key).resolve()
        source.relative_to(assets.resolve())
        dest = (root / key).resolve()
        dest.relative_to(root.resolve())
        data = source.read_bytes()
        if hashlib.sha256(data).hexdigest() != record["sha256"] or dest.exists():
            raise ValueError(f"Invalid or duplicate asset: {key}")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
    shutil.copyfile(index, root / "assets.json")
    build_strings(strings, stage / "data" / "strings")


def build(assets, strings, loader, runtime, output, stock=None, rules=None):
    if output.exists():
        raise FileExistsError(output)
    verify_runtime(runtime)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent) as tmp:
        stage = Path(tmp) / "payload"
        stage_resources(assets, strings, stage)
        build_aliases(assets, strings.parent / "materials.package", stage)
        build_catalogs(strings.parent, stage)
        shutil.copyfile(loader, stage / "winmm.dll")
        shutil.copyfile(runtime, stage / "ssmods" / "RedPanda" / "RedPanda.dll")
        build_game_menu(strings.parent.parent / "sinking_star.exe", stage / "sinking_star.exe")
        entries = []
        for path in sorted(stage.rglob("*")):
            if path.is_file():
                target = path.relative_to(stage).as_posix()
                entries.append(dict(source=target, target=target,
                                    sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
        executable = next(entry for entry in entries if entry["target"] == "sinking_star.exe")
        executable["migrateFrom"] = STOCK
        outlines = next(entry for entry in entries if entry["target"] == "data/mesh_outlines.mesh_outlines")
        outlines["migrateFrom"] = hashlib.sha256((strings.parent / "mesh_outlines.mesh_outlines").read_bytes()).hexdigest()
        if (stock is None) != (rules is None):
            raise ValueError("Supply both stock and rules for direct-install migration")
        if stock is not None:
            for rule in json.loads(rules.read_bytes()):
                target = rule["file"]
                if target in {"data/materials.package", "data/animation.package", "data/levels.package"}:
                    with (strings.parent / Path(target).name).open("rb") as stream:
                        if hashlib.file_digest(stream, "sha256").hexdigest() != rule["original"]:
                            raise ValueError(f"Original catalog mismatch: {target}")
                    entry = next(item for item in entries if item["target"] == target)
                    entry.update(migrateFrom=rule["modified"], stockFrom=rule["original"])
                    continue
                source = Path("migration") / target
                destination = stage / source
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(stock / target, destination)
                with destination.open("rb") as stream:
                    digest = hashlib.file_digest(stream, "sha256").hexdigest()
                if digest != rule["original"]:
                    raise ValueError(f"Original asset mismatch: {target}")
                entries.append(dict(source=source.as_posix(), target=target, sha256=digest,
                                    migrateFrom=rule["modified"]))
        (stage / "plugin.json").write_text(json.dumps(entries, indent=2), encoding="utf-8")
        stage.rename(output)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("assets", "strings", "loader", "runtime", "output"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--stock", type=Path)
    parser.add_argument("--rules", type=Path)
    build(**vars(parser.parse_args()))
