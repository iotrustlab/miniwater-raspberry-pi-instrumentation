#!/usr/bin/env python3
"""Read-only prerequisite checks for the MiniWater instrumented OpenPLC build."""

import argparse
import json
import os
import platform
from pathlib import Path
import re
import shutil
import struct
import subprocess


ROOT = Path(__file__).resolve().parents[1]
ELF_MACHINES = {3: "i386", 40: "arm", 62: "x86_64", 183: "aarch64"}


def elf_machine(path):
    """Read an ELF machine identifier without executing the binary."""
    with Path(path).open("rb") as stream:
        header = stream.read(20)
    if len(header) < 20 or header[:4] != b"\x7fELF":
        raise ValueError("not a complete ELF header")
    if header[4] not in (1, 2) or header[5] not in (1, 2):
        raise ValueError("invalid ELF class or byte order")
    machine = struct.unpack("<H" if header[5] == 1 else ">H", header[18:20])[0]
    return ELF_MACHINES.get(machine, "ELF machine {}".format(machine))


def host_machine():
    machine = platform.machine().lower()
    if machine in ("amd64", "x64"):
        return "x86_64"
    if machine == "arm64":
        return "aarch64"
    if machine.startswith("arm"):
        return "arm"
    return machine


def collect_checks(target):
    checks = []

    def add(name, status, detail):
        checks.append({"name": name, "status": status, "detail": detail})

    mode = os.environ.get("OPENPLC_INSTRUMENTATION", "1")
    if mode not in ("0", "1"):
        add("instrumentation mode", "error", "OPENPLC_INSTRUMENTATION must be 0 or 1")
    compiler = os.environ.get("CXX", "clang++-14")
    compiler_path = shutil.which(compiler)
    if compiler_path is None:
        add("compiler", "error", "{} is not on PATH; set CXX to a compiler executable".format(compiler))
    else:
        try:
            version = subprocess.run(
                [compiler_path, "--version"], capture_output=True, text=True, timeout=10,
                check=True,
            ).stdout
            major = re.search(r"clang version (\d+)", version)
            if mode != "0" and (major is None or major.group(1) != "14"):
                add("compiler", "error", "instrumentation requires Clang 14 and a matching legacy pass")
            else:
                add("compiler", "pass", version.splitlines()[0] if version else compiler_path)
        except (OSError, subprocess.SubprocessError) as exc:
            add("compiler", "error", "cannot query {}: {}".format(compiler_path, exc))

    if mode != "0":
        pass_path = Path(os.environ.get("OPENPLC_INSTRUMENTATION_PASS", str(ROOT / "instrument.so")))
        try:
            architecture = elf_machine(pass_path)
            host = host_machine()
            add("instrumentation pass", "pass" if architecture == host else "error",
                "{}: {}; compiler host is {}".format(pass_path, architecture, host))
        except (OSError, ValueError) as exc:
            add("instrumentation pass", "error", "{}: {}".format(pass_path, exc))
        add("pass ABI", "warning", "ELF architecture does not verify LLVM ABI or shared-library dependencies; a real build is required")
    else:
        add("instrumentation", "warning", "disabled: the resulting build is an uninstrumented baseline")

    for command in ("g++", "make", "cmake", "autoconf", "autoreconf", "automake", "libtoolize", "bison", "flex"):
        executable = shutil.which(command)
        add(command, "pass" if executable else "error", executable or "required by the source installer")

    pkg_config = shutil.which("pkg-config")
    if pkg_config is None:
        add("libmodbus", "error", "pkg-config is not on PATH")
    else:
        try:
            result = subprocess.run([pkg_config, "--exists", "libmodbus"], timeout=10, check=False)
            add("libmodbus", "pass" if result.returncode == 0 else "error",
                "found through pkg-config" if result.returncode == 0 else "install libmodbus and expose its .pc file via PKG_CONFIG_PATH")
        except (OSError, subprocess.SubprocessError) as exc:
            add("libmodbus", "error", str(exc))

    python = Path(os.environ.get("OPENPLC_PYTHON", str(ROOT / ".venv/bin/python3")))
    add("webserver Python", "pass" if python.is_file() and os.access(python, os.X_OK) else "warning",
        str(python) if python.is_file() else "{} will be created by the installer".format(python))

    for relative in ("webserver/iec2c", "webserver/st_optimizer", "webserver/core/glue_generator"):
        try:
            architecture = elf_machine(ROOT / relative)
            add(relative, "pass" if architecture == host_machine() else "warning",
                "{}; rebuild with ./install.sh {} on the target host".format(architecture, target))
        except (OSError, ValueError) as exc:
            add(relative, "warning", "rebuild with the installer: {}".format(exc))
    if target == "rpi":
        add("Raspberry Pi I/O", "warning", "WiringPi, the selected hardware layer, and physical I/O must be verified on the Pi")
    return checks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--platform", choices=("linux", "rpi"), default="rpi")
    parser.add_argument("--json", action="store_true", help="emit a machine-readable report")
    args = parser.parse_args()
    checks = collect_checks(args.platform)
    ready = all(check["status"] != "error" for check in checks)
    report = {"platform": args.platform, "host": host_machine(), "ready": ready, "checks": checks}
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        for check in checks:
            print("[{status}] {name}: {detail}".format(**check))
        print("Prerequisite checks {}. Hardware operation and end-to-end tracing require target validation.".format(
            "passed" if ready else "failed"))
    return 0 if ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
