#!/usr/bin/env python3
"""Run production Actions.qml in Qt with inert Quickshell types and fake owners.

Quickshell's native plugin is embedded in qs, not loadable by qmltestrunner.
Stage the action and wallpaper singletons with fake dependencies so unrelated
production singleton startup never runs. All subprocess/PipeWire APIs in this harness are in-memory test doubles.
"""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

suite = Path(__file__).resolve().parent
runtime = suite.parent.parent / "quickshell/sparrow"
with tempfile.TemporaryDirectory(prefix="sparrow-action-tests-") as directory:
    root = Path(directory)
    (root / "Singletons").mkdir()
    (root / "lib").mkdir()
    shutil.copy2(runtime / "Singletons/Actions.qml", root / "Singletons/Actions.qml")
    shutil.copy2(runtime / "Singletons/Walls.qml", root / "Singletons/Walls.qml")
    (root / "Singletons/qmldir").write_text("singleton Actions Actions.qml\nsingleton Walls Walls.qml\nsingleton Flags Flags.qml\nsingleton Niri Niri.qml\n")
    (root / "Singletons/Flags.qml").write_text('pragma Singleton\nimport QtQml\nQtObject { property string wallpaperDir: "" }\n')
    (root / "Singletons/Niri.qml").write_text('pragma Singleton\nimport QtQml\nQtObject { property var outputs: []; property string focusedOutput: "" }\n')
    shutil.copy2(runtime / "lib/action-engine.js", root / "lib/action-engine.js")
    shutil.copytree(suite, root / "tests/actions")
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen")
    result = subprocess.run(["/usr/lib/qt6/bin/qmltestrunner", "-input", str(root / "tests/actions"),
                             "-import", str(root / "tests/actions/imports")], env=env)
    raise SystemExit(result.returncode)
