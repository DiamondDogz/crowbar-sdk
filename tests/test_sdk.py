"""Tests for crowbar-sdk. Run: python -m unittest discover -s tests"""
import io
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "sdk" / "python"))

import crowbar  # noqa: E402
from crowbar_sdk import check, fake, manifest  # noqa: E402

HANDLER_C = r'''
#include <stdint.h>
static int32_t trophy_unlock(int32_t ctx, int32_t handle, int32_t id, int32_t *platinum) {
    (void)ctx; (void)handle;
    if (platinum) *platinum = -1;
    return 0;
}
static const struct { const char *name; void *fn; } exports[] = {
    {"sceNpTrophyUnlockTrophy", trophy_unlock},
};
'''


def make_runtime(base: Path, wired=False, manifest_data=None, glob=True) -> Path:
    rt = base / "rt"
    (rt / "src").mkdir(parents=True)
    (rt / "scripts").mkdir()
    (rt / "bin").mkdir()
    (rt / "bin" / "ps4rt").write_text("x")
    (rt / "scripts" / "ps4rt_launch.py").write_text("TITLE_ID = 'CUSA16429'\n# --dlc-pkg --no-dialogs --data-dir\n")
    code = HANDLER_C.replace("(void)ctx;", "crowbar_unlock(id); (void)ctx;") if wired else HANDLER_C
    (rt / "src" / "runtime_services.c").write_text(code)
    (rt / "gpu").mkdir()
    (rt / "gpu" / "CMakeLists.txt").write_text("file(GLOB R ../src/runtime*.c)\n" if glob else "add_executable(x ../src/runtime_services.c)\n")
    if manifest_data is not None:
        (rt / "crowbar.json").write_text(json.dumps(manifest_data))
    return rt


GOOD = {"crowbar": 1, "name": "Test", "game": "sakura-wars", "titleIds": ["CUSA16429"], "data": "out/{titleId}",
        "launch": {"linux": ["bin/ps4rt", "--game", "{game}", "--data-dir", "{data}"]},
        "features": {"trophies": True, "dlc": ["--dlc-pkg", "{file}"], "noDialogs": ["--no-dialogs"]}}


class PythonHelper(unittest.TestCase):
    def test_unlock_keeps_first_date_and_pads(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "u", "trophies.json")
            Path(d, "u").mkdir()
            Path(p).write_text('{"unlocked":{"7":"2026-01-01T00:00:00Z"}}')
            self.assertTrue(crowbar.unlock(14, p))
            self.assertFalse(crowbar.unlock(7, p))
            data = json.loads(Path(p).read_text())
            self.assertEqual(list(data["unlocked"]), ["007", "014"])
            self.assertEqual(data["unlocked"]["007"], "2026-01-01T00:00:00Z")
            self.assertFalse(Path(p + ".tmp").exists())
            with self.assertRaises(ValueError):
                crowbar.unlock(128, p)

    def test_trophy_file_from_environment(self):
        old = dict(os.environ)
        try:
            os.environ.pop("PS4RT_TROPHY_FILE", None)
            os.environ["PS4RT_DATA_DIR"] = "/data"
            self.assertEqual(Path(crowbar.trophy_file()), Path("/data/user/trophies.json"))
            os.environ["PS4RT_TROPHY_FILE"] = "/x.json"
            self.assertEqual(crowbar.trophy_file(), "/x.json")
        finally:
            os.environ.clear()
            os.environ.update(old)

    def test_packaged_copy_is_identical(self):
        self.assertEqual((ROOT / "sdk/python/crowbar.py").read_text(), (ROOT / "crowbar_sdk/_crowbar.py").read_text())


@unittest.skipUnless(shutil.which("cc") or shutil.which("gcc"), "no C compiler")
class CHelper(unittest.TestCase):
    def test_c_and_python_share_the_file(self):
        cc = shutil.which("cc") or shutil.which("gcc")
        with tempfile.TemporaryDirectory() as d:
            src = Path(d, "t.c")
            src.write_text('#include "crowbar.h"\n#include <stdio.h>\n#include <stdlib.h>\n'
                           'int main(int c,char**v){for(int i=1;i<c;i++)printf("%d ",crowbar_unlock(atoi(v[i])));return 0;}\n')
            exe = Path(d, "t")
            subprocess.run([cc, "-std=c11", "-Wall", "-Werror", "-I", str(ROOT / "sdk/c"), str(src), str(ROOT / "sdk/c/crowbar.c"), "-o", str(exe)], check=True)
            p = Path(d, "deep", "user", "trophies.json")
            env = dict(os.environ, PS4RT_TROPHY_FILE=str(p))
            out = subprocess.run([str(exe), "3", "3", "200", "0"], env=env, capture_output=True, text=True, check=True).stdout
            self.assertEqual(out.split(), ["1", "0", "-1", "1"])
            self.assertEqual(sorted(crowbar.read(str(p))), [0, 3])
            crowbar.unlock(9, str(p))
            out = subprocess.run([str(exe), "9", "10"], env=env, capture_output=True, text=True, check=True).stdout
            self.assertEqual(out.split(), ["0", "1"])
            self.assertEqual(sorted(crowbar.read(str(p))), [0, 3, 9, 10])


class Check(unittest.TestCase):
    def test_options(self):
        good = dict(GOOD, settings="{data}/ps4rt.ini", options=[
            {"key": "output_res", "label": {"en": "Output resolution", "fr": "Résolution"}, "values": [["1920x1080", "1080p"], ["3840x2160", "4K"]], "default": "1920x1080"},
            {"key": "vsync", "label": "Vertical sync", "values": [["0", "Off"], ["1", {"en": "On"}]], "default": "1"}])
        with tempfile.TemporaryDirectory() as d:
            rt = make_runtime(Path(d), wired=True, manifest_data=good)
            (rt / "ps4rt.ini").write_text("output_res=1920x1080\nvsync=1\nupscaler=off\n")
            r = check.run(rt)
            self.assertTrue(r["ok"], r["errors"])
            self.assertIn("options.undeclared", {f["code"] for f in r["info"]})
        bad = dict(GOOD, options=[{"key": "a b", "label": {"fr": "x"}, "values": [["1", "x"]], "default": "2"}, "x"])
        with tempfile.TemporaryDirectory() as d:
            r = check.run(make_runtime(Path(d), wired=True, manifest_data=bad))
            codes = {e["code"] for e in r["errors"]}
            for c in ("options.settings", "options.key", "options.label", "options.values", "options.item"):
                self.assertIn(c, codes)
        with tempfile.TemporaryDirectory() as d:
            r = check.run(make_runtime(Path(d), wired=True, manifest_data=dict(GOOD, settings="ps4rt.ini")))
            self.assertIn("options.missing", {w["code"] for w in r["warnings"]})
            self.assertIn('"options"', check.handout(r) if hasattr(check, "handout") else json.dumps(r))

    def test_good_runtime_passes(self):
        with tempfile.TemporaryDirectory() as d:
            rt = make_runtime(Path(d), wired=True, manifest_data=GOOD)
            r = check.run(rt)
            self.assertTrue(r["ok"], r["errors"])
            self.assertTrue(r["trophies"]["wired"])

    def test_missing_manifest_and_unwired_handler(self):
        with tempfile.TemporaryDirectory() as d:
            rt = make_runtime(Path(d))
            r = check.run(rt, write_proposal=True)
            codes = {e["code"] for e in r["errors"]}
            self.assertIn("manifest.missing", codes)
            self.assertIn("trophies.not-wired", codes)
            self.assertEqual(r["trophies"]["handler"], "trophy_unlock")
            self.assertEqual(r["trophies"]["param"], "id")
            self.assertEqual(r["proposal"]["game"], "sakura-wars")
            self.assertEqual(r["proposal"]["features"]["dlc"], ["--dlc-pkg", "{file}"])
            self.assertTrue((rt / "crowbar.json.proposed").is_file())
            h = check.handout(r)
            self.assertIn("src/runtime_crowbar.c", h)
            self.assertIn("crowbar_unlock(id);", h)
            self.assertIn("Do not", h)

    def test_handout_without_wildcard_names_build_file(self):
        with tempfile.TemporaryDirectory() as d:
            rt = make_runtime(Path(d), glob=False)
            h = check.handout(check.run(rt))
            self.assertIn("gpu/CMakeLists.txt", h)
            self.assertNotIn("runtime_crowbar.c", h)

    def test_manifest_errors(self):
        bad = dict(GOOD, crowbar=1, game="Sakura Wars", titleIds=["X"], launch={"linux": ["bin/missing", "{nope}"]},
                   features={"dlc": ["--dlc-pkg"], "trophies": "yes"}, extra=1)
        with tempfile.TemporaryDirectory() as d:
            rt = make_runtime(Path(d), wired=True, manifest_data=bad)
            r = check.run(rt)
            codes = {e["code"] for e in r["errors"]}
            for c in ("game.invalid", "titleIds.invalid", "launch.program", "launch.placeholder", "features.placeholder", "features.flag"):
                self.assertIn(c, codes)
            self.assertIn("key.unknown", {w["code"] for w in r["warnings"]})

    def test_forbidden_files_by_signature(self):
        with tempfile.TemporaryDirectory() as d:
            rt = make_runtime(Path(d), wired=True, manifest_data=GOOD)
            (rt / "Containerfile.pkg").write_text("FROM ubuntu")  # not a PS4 package
            (rt / "dlc.pkg").write_bytes(b"\x7fCNT" + b"\0" * 60)
            (rt / "sce_sys").mkdir()
            r = check.run(rt)
            files = {e.get("file") for e in r["errors"]}
            self.assertIn("dlc.pkg", files)
            self.assertIn("sce_sys", files)
            self.assertNotIn("Containerfile.pkg", files)

    def test_trophy_file_validation(self):
        with tempfile.TemporaryDirectory() as d:
            rt = make_runtime(Path(d), wired=True, manifest_data=GOOD)
            u = rt / "out" / "CUSA16429" / "user"
            u.mkdir(parents=True)
            (u / "trophies.json").write_text('{"unlocked":{"300":"2026-01-01T00:00:00Z","5":"hier"}}')
            r = check.run(rt)
            self.assertIn("trophyfile.key", {e["code"] for e in r["errors"]})
            self.assertTrue({"trophyfile.padding", "trophyfile.date"} <= {w["code"] for w in r["warnings"]})

    def test_archive(self):
        with tempfile.TemporaryDirectory() as d:
            rt = make_runtime(Path(d), wired=True, manifest_data=GOOD)
            arc = Path(d, "release.tar.gz")
            with tarfile.open(arc, "w:gz") as t:
                t.add(rt, arcname="my-runtime")
            r = check.run(arc)
            self.assertTrue(r["ok"], r["errors"])

    def test_cli_exit_codes(self):
        with tempfile.TemporaryDirectory() as d:
            rt = make_runtime(Path(d))
            with redirect_stdout(io.StringIO()) as out:
                self.assertEqual(check.main([str(rt), "--json"]), 1)
            self.assertFalse(json.loads(out.getvalue())["ok"])
            with redirect_stdout(io.StringIO()):
                self.assertEqual(check.main([str(Path(d, "nothing"))]), 2)


class Launch(unittest.TestCase):
    def test_command_and_environment(self):
        root, game = Path("/rt"), Path("/games/SW")
        cmd = manifest.command(GOOD, "linux", root, game, "CUSA16429", dlc=[Path("/d/a.pkg"), Path("/d/b.pkg")])
        self.assertEqual(cmd, [str(root / "bin/ps4rt"), "--game", str(game), "--data-dir", str(root / "out/CUSA16429"),
                               "--dlc-pkg", str(Path("/d/a.pkg")), "--dlc-pkg", str(Path("/d/b.pkg")), "--no-dialogs"])
        env = manifest.environment(GOOD, root, game, "CUSA16429", "0.3.0", language=2, lang_code="fr")
        self.assertEqual(Path(env["PS4RT_TROPHY_FILE"]), root / "out/CUSA16429/user/trophies.json")
        self.assertEqual(env["CROWBAR"], "0.3.0")
        self.assertEqual(env["PS4RT_LANGUAGE"], "2")

    def test_fake_simulate(self):
        with tempfile.TemporaryDirectory() as d:
            rt = make_runtime(Path(d), wired=True, manifest_data=GOOD)
            with redirect_stdout(io.StringIO()) as out:
                self.assertEqual(fake.main([str(rt), "--simulate", "14"]), 0)
            self.assertIn("trophy 014 written", out.getvalue())
            self.assertEqual(sorted(crowbar.read(str(rt / "out/CUSA16429/user/trophies.json"))), [14])


if __name__ == "__main__":
    unittest.main()


def test_pause_exchange(tmp_path, monkeypatch):
    import importlib.util
    spec = importlib.util.spec_from_file_location("crowbar_helper", str(Path(__file__).resolve().parents[1] / "sdk" / "python" / "crowbar.py"))
    cb = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cb)
    monkeypatch.setenv("PS4RT_CONTROL_DIR", str(tmp_path))
    assert cb.poll() is None
    assert (tmp_path / "state").read_text().split() == ["0", "ready"]
    (tmp_path / "request").write_text("1 pause\n")
    assert cb.poll() == "pause"
    assert cb.poll() is None, "the same request is returned once"
    cb.answer(False)
    assert (tmp_path / "state").read_text().split() == ["1", "refused"]
    (tmp_path / "request").write_text("2 pause\n")
    assert cb.poll() == "pause"
    cb.answer(True)
    assert (tmp_path / "state").read_text().split() == ["2", "paused"]
    (tmp_path / "request").write_text("3 resume\n")
    assert cb.poll() == "resume"
    cb.answer()
    assert (tmp_path / "state").read_text().split() == ["3", "running"]
    (tmp_path / "request").write_text("4 unlock 12\n")
    assert cb.poll() == "unlock"
    assert cb.request_trophy() == 12
    cb.answer(True)
    assert (tmp_path / "state").read_text().split() == ["4", "unlocked"]
    (tmp_path / "request").write_text("5 unlock 200\n")
    assert cb.poll() is None, "a trophy number outside 0..127 is ignored"
    (tmp_path / "request").write_text("6 quit\n")
    assert cb.poll() == "quit"
    cb.answer()
    assert (tmp_path / "state").read_text().split() == ["6", "quitting"]


def test_manifest_14_keys(tmp_path):
    from crowbar_sdk import manifest
    m = {"crowbar": 1, "name": "T", "game": "t", "titleIds": ["CUSA00001"], "launch": {"linux": ["run"]},
         "trophyFile": "{data}/user/achievements/*/NPWR*.dat", "trophyFormat": "ps4rt-unlocks",
         "language": {"env": "DCP_LANGUAGE", "values": {"1": "english", "2": "french"}}}
    r = manifest.Report()
    manifest.validate(m, tmp_path, r)
    assert not [f for f in r.errors if f.code.startswith(("trophy", "language"))], [f.as_dict() for f in r.errors]
    env = manifest.environment(m, tmp_path, tmp_path, "CUSA00001", "0.2.9", language=2, button_style="xbox")
    assert env["DCP_LANGUAGE"] == "french" and env["PS4RT_LANGUAGE"] == "2" and env["PS4RT_BUTTON_STYLE"] == "xbox"
    bad = dict(m, trophyFormat="other", language={"env": "lower"}, trophyFile="../x")
    r = manifest.Report()
    manifest.validate(bad, tmp_path, r)
    codes = {f.code for f in r.errors}
    assert {"trophyFormat.invalid", "language.env", "trophyFile.outside"} <= codes, codes
