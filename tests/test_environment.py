"""Validate host/plugin compatibility checks without loading a shared object."""

import importlib.util
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch


SPEC = importlib.util.spec_from_file_location(
    "check_environment", Path(__file__).resolve().parents[1] / "tools/check_environment.py"
)
environment = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(environment)


class ElfChecks(unittest.TestCase):
    def read_machine(self, machine, order=1):
        header = bytearray(b"\x7fELF" + bytes([2, order]) + bytes(14))
        struct.pack_into("<H" if order == 1 else ">H", header, 18, machine)
        with tempfile.NamedTemporaryFile() as stream:
            stream.write(header)
            stream.flush()
            return environment.elf_machine(stream.name)

    def test_distinguishes_pi_and_x86_plugin(self):
        self.assertEqual(self.read_machine(62), "x86_64")
        self.assertEqual(self.read_machine(183), "aarch64")
        self.assertEqual(self.read_machine(40), "arm")

    def test_honors_elf_byte_order(self):
        self.assertEqual(self.read_machine(183, order=2), "aarch64")

    def test_rejects_truncated_or_non_elf_plugin(self):
        for data in (b"\x7fELF", b"not an ELF library" * 2):
            with self.subTest(data=data), tempfile.NamedTemporaryFile() as stream:
                stream.write(data)
                stream.flush()
                with self.assertRaises(ValueError):
                    environment.elf_machine(stream.name)

    @patch.object(environment.platform, "machine", return_value="armv7l")
    def test_normalizes_32_bit_pi_host(self, _machine):
        self.assertEqual(environment.host_machine(), "arm")


if __name__ == "__main__":
    unittest.main()
