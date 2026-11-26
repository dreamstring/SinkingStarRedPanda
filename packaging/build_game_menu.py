"""Build the graphics menu adapter for the supported Steam executable."""
import hashlib
import struct
from pathlib import Path

import lief
import pefile

STOCK = "69ddb71fb6768a097f9bff204201f3a9ce960f1a325f5ed3a5c9160dc64a6ae8"
PLUGIN = r"ssmods\RedPanda\RedPanda.dll"


def build(stock, output):
    if hashlib.sha256(stock.read_bytes()).hexdigest() != STOCK or output.exists():
        raise ValueError("Expected the supported stock executable and a new output file")
    binary = lief.PE.parse(str(stock))
    plugin = binary.add_import(PLUGIN)
    for export in ("RedPandaDrawInstalledPage", "RedPandaConfirmMenuRow"):
        plugin.add_entry(export)
    config = lief.PE.Builder.config_t()
    config.imports = True
    binary.write(str(output), config)
    with pefile.PE(str(output)) as pe:
        table = next(m for m in pe.DIRECTORY_ENTRY_IMPORT if m.dll.decode() == PLUGIN)
        imports = {i.name.decode(): i.address - pe.OPTIONAL_HEADER.ImageBase for i in table.imports}
        data = bytearray(output.read_bytes())
        section = pe.sections[0]
        start = section.VirtualAddress + section.Misc_VirtualSize
        code = bytearray()

        def relative(op, target):
            code.extend(op)
            code.extend(struct.pack("<i", target - (start + len(code) + 4)))

        def replace(rva, expected, replacement):
            offset = pe.get_offset_from_rva(rva)
            if data[offset:offset + len(expected)] != expected or len(expected) != len(replacement):
                raise ValueError(f"Unexpected graphics page at {rva:x}")
            data[offset:offset + len(expected)] = replacement

        relative(b"\xff\x25", imports["RedPandaDrawInstalledPage"])
        replace(0x200072, bytes.fromhex("e8d921ebff"), b"\xe8" + struct.pack("<i", start - 0x200077))
        for address, previous, changed in ((0x81c0b, 6, 7), (0x81c16, 250, 249), (0x81c1a, 6, 7)):
            replace(address, bytes([previous]), bytes([changed]))

        confirm = start + len(code)
        # Fullscreen keeps its existing path. Row one was handled earlier.
        code.extend(bytes.fromhex("48 85 c0"))
        relative(b"\x0f\x84", 0x16fd6a)
        code.extend(bytes.fromhex("48 83 f8 06"))
        relative(b"\x0f\x85", 0x1710c7)
        code.extend(bytes.fromhex("89 c1"))
        relative(b"\xff\x15", imports["RedPandaConfirmMenuRow"])
        relative(b"\xe9", 0x1710c7)
        replace(0x16fd61, bytes.fromhex("4885c00f855d130000"),
                b"\xe9" + struct.pack("<i", confirm - 0x16fd66) + b"\x90" * 4)
        end = section.PointerToRawData + section.Misc_VirtualSize
        if len(code) > section.SizeOfRawData - section.Misc_VirtualSize or any(data[end:end + len(code)]):
            raise ValueError("Unexpected end of Steam graphics code")
        data[end:end + len(code)] = code
        struct.pack_into("<I", data, section.get_field_absolute_offset("Misc_VirtualSize"),
                         section.Misc_VirtualSize + len(code))
    output.write_bytes(data)
