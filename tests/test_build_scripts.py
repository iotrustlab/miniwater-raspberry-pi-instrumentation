"""Exercise build/launcher failure handling without PLC hardware or Clang.

The fake toolchain records argument boundaries and can fail at each stage.
These tests verify orchestration; they do not validate the LLVM pass or I/O.
"""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


SOURCE_ROOT = Path(__file__).resolve().parents[1]


class BuildScriptTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="miniwater scripts ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "repo with spaces"
        self.web = self.root / "webserver"
        self.scripts = self.web / "scripts"
        self.core = self.web / "core"
        self.bin = self.root / "fake bin"
        for directory in (self.scripts, self.core, self.web / "st_files", self.bin):
            directory.mkdir(parents=True, exist_ok=True)
        for name in ("install.sh", "start_openplc.sh", "webserver/scripts/compile_program.sh"):
            shutil.copy2(SOURCE_ROOT / name, self.root / name)
        (self.scripts / "openplc_platform").write_text("linux\n")
        (self.scripts / "openplc_driver").write_text("blank_linux\n")
        (self.web / "st_files" / "sample.st").write_text("PROGRAM sample\nEND_PROGRAM\n")
        (self.web / "active_program").write_text("previous.st\n")
        (self.core / "openplc").write_text("previous working runtime")
        (self.core / "main.cpp").write_text("// fake runtime translation unit\n")
        (self.root / "instrument.so").write_text("fixture plugin")
        self.calls = self.root / "compiler-calls.jsonl"
        self.env = os.environ.copy()
        for name in ("CXX", "OPENPLC_INSTRUMENTATION", "OPENPLC_INSTRUMENTATION_PASS", "OPENPLC_PYTHON"):
            self.env.pop(name, None)
        self.env.update(PATH=str(self.bin) + os.pathsep + self.env["PATH"], CALLS=str(self.calls))
        self.executable(self.web / "st_optimizer", "import os, sys\nsys.exit(2 if os.environ.get('FAIL_STAGE') == 'optimizer' else 0)\n")
        self.executable(self.web / "iec2c", """import os, sys
from pathlib import Path
if os.environ.get('FAIL_STAGE') == 'iec2c':
    sys.exit(3)
for name in ('POUS.c', 'POUS.h', 'LOCATED_VARIABLES.h', 'VARIABLES.csv', 'Config0.c', 'Config0.h', 'Res0.c'):
    Path(name).write_text('// generated fixture\\n' * 10)
""")
        self.executable(self.core / "glue_generator", "import os, sys\nsys.exit(4 if os.environ.get('FAIL_STAGE') == 'glue' else 0)\n")
        self.executable(self.bin / "pkg-config", "print('-I/fake/include -L/fake/lib -lmodbus')\n")
        self.executable(self.bin / "clang++-14", """import json, os, sys
from pathlib import Path
args = sys.argv[1:]
with open(os.environ['CALLS'], 'a') as stream:
    stream.write(json.dumps(args) + '\\n')
output = Path(args[args.index('-o') + 1])
output.write_text('new runtime' if '-c' not in args else 'fixture object')
stage = os.environ.get('FAIL_STAGE', '')
if (stage == 'compile' and '-c' in args) or (stage == 'link' and '-c' not in args):
    sys.exit(5)
""")
        shutil.copy2(self.bin / "clang++-14", self.bin / "g++")

    def executable(self, path, body):
        path.write_text(f"#!{sys.executable}\n" + body)
        path.chmod(0o755)

    def run_compile(self, program="sample.st", **changes):
        return subprocess.run(
            ["bash", str(self.scripts / "compile_program.sh"), program],
            cwd=self.temp.name,
            env={**self.env, **changes},
            text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        )

    def compiler_calls(self):
        return [json.loads(line) for line in self.calls.read_text().splitlines()]

    def assert_previous_runtime(self):
        self.assertEqual((self.web / "active_program").read_text(), "previous.st\n")
        self.assertEqual((self.core / "openplc").read_text(), "previous working runtime")

    def test_build_from_unrelated_directory_and_paths_with_spaces(self):
        result = self.run_compile()
        self.assertEqual(result.returncode, 0, result.stdout)
        calls = self.compiler_calls()
        self.assertEqual(len(calls), 3)
        for args in calls:
            self.assertIn(str(self.root / "instrument.so"), args)
            self.assertIn("-flegacy-pass-manager", args)
        self.assertEqual((self.web / "active_program").read_text(), "sample.st\n")
        self.assertEqual((self.core / "openplc").read_text(), "new runtime")

    def test_custom_compiler_and_relative_plugin_path(self):
        plugin = Path(self.temp.name) / "custom pass.so"
        plugin.write_text("fixture plugin")
        compiler = self.bin / "custom compiler"
        shutil.copy2(self.bin / "clang++-14", compiler)
        result = self.run_compile(CXX=str(compiler), OPENPLC_INSTRUMENTATION_PASS=plugin.name)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn(str(plugin), self.compiler_calls()[0])

    def test_missing_plugin_fails_before_mutating_program(self):
        result = self.run_compile(OPENPLC_INSTRUMENTATION_PASS="missing.so")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Instrumentation pass not found", result.stdout)
        self.assertFalse(self.calls.exists())
        self.assert_previous_runtime()

    def test_missing_compiler_fails_before_mutating_program(self):
        result = self.run_compile(CXX="no-such-miniwater-compiler")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Compiler not found", result.stdout)
        self.assert_previous_runtime()

    def test_reject_path_traversal(self):
        result = self.run_compile("../sample.st")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.calls.exists())
        self.assert_previous_runtime()

    def test_stage_failures_preserve_working_runtime_and_program(self):
        for stage in ("optimizer", "iec2c", "compile", "glue", "link"):
            with self.subTest(stage=stage):
                result = self.run_compile(FAIL_STAGE=stage)
                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assert_previous_runtime()
                self.assertFalse((self.core / "openplc.new").exists())

    def test_explicit_baseline_does_not_require_plugin(self):
        (self.root / "instrument.so").unlink()
        result = self.run_compile(OPENPLC_INSTRUMENTATION="0", CXX="g++")
        self.assertEqual(result.returncode, 0, result.stdout)
        for args in self.compiler_calls():
            self.assertNotIn("-Xclang", args)

    def test_invalid_instrumentation_setting_is_rejected(self):
        result = self.run_compile(OPENPLC_INSTRUMENTATION="perhaps")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("must be 0 or 1", result.stdout)

    def test_driver_defines_and_pi_libraries(self):
        for platform, driver, define in (("linux", "sl_rp4", "-DSL_RP4"), ("rpi", "sequent", "-DSEQUENT")):
            with self.subTest(platform=platform):
                self.calls.unlink(missing_ok=True)
                (self.scripts / "openplc_platform").write_text(platform)
                (self.scripts / "openplc_driver").write_text(driver)
                result = self.run_compile()
                self.assertEqual(result.returncode, 0, result.stdout)
                for args in self.compiler_calls():
                    self.assertIn(define, args)
                if platform == "rpi":
                    self.assertIn("-lwiringPi", self.compiler_calls()[-1])

    def test_native_launcher_uses_repo_directory_and_interpreter(self):
        interpreter = self.bin / "test python"
        self.executable(interpreter, "import json, os, sys\nprint(json.dumps([os.getcwd(), sys.argv[1:]]))\n")
        result = subprocess.run(
            ["bash", str(self.root / "start_openplc.sh")], cwd=self.temp.name,
            env={**self.env, "OPENPLC_PYTHON": str(interpreter)},
            text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        )
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(json.loads(result.stdout), [str(self.web), ["webserver.py"]])

    def test_install_wrapper_preserves_failure_status_and_arguments(self):
        self.executable(self.root / "background_installer.sh", "import json, os, sys\nprint(json.dumps([os.getcwd(), sys.argv[1:]]))\nsys.exit(37)\n")
        result = subprocess.run(
            ["bash", str(self.root / "install.sh"), "linux", "ethercat"], cwd=self.temp.name,
            env=self.env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        )
        self.assertEqual(result.returncode, 37, result.stdout)
        self.assertEqual(json.loads(result.stdout), [str(self.root), ["linux", "ethercat"]])

    def test_invalid_installer_arguments_do_not_invoke_installer(self):
        self.executable(self.root / "background_installer.sh", "raise AssertionError('must not be called')\n")
        for args in ([], ["invalid"], ["linux", "invalid"], ["linux", "ethercat", "extra"]):
            with self.subTest(args=args):
                result = subprocess.run(
                    ["bash", str(self.root / "install.sh"), *args], env=self.env,
                    text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse((self.root / "install_log.txt").exists())


if __name__ == "__main__":
    unittest.main()
