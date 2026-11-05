import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile


ROOT = Path(__file__).resolve().parent.parent
INDEXER = ROOT / "python3/android_dev.py"
GENERATOR = ROOT / "python3/new_project.py"


class ToolTests(unittest.TestCase):
    def test_jar_aar_index_import_and_methods(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source/org/example/Widget.java"
            source.parent.mkdir(parents=True)
            source.write_text("package org.example; public class Widget { public int count() { return 1; } }")
            classes = root / "compiled"
            classes.mkdir()
            subprocess.run(["javac", "-d", str(classes), str(source)], check=True)
            jar = root / "widget.jar"
            with zipfile.ZipFile(jar, "w") as archive:
                archive.write(classes / "org/example/Widget.class", "org/example/Widget.class")
            aar = root / "widget.aar"
            with zipfile.ZipFile(aar, "w") as archive:
                archive.write(jar, "classes.jar")
            for artifact in (jar, aar):
                manifest = root / ".vim-api/manifests" / (artifact.suffix[1:] + ".json")
                manifest.parent.mkdir(parents=True, exist_ok=True)
                manifest.write_text(json.dumps({"module": ":app", "variant": "debug",
                                                "artifacts": [{"path": str(artifact),
                                                               "coordinate": ":widget:"}]}))
                index = subprocess.check_output([sys.executable, str(INDEXER), "build", str(manifest)],
                                                text=True).strip()
                imported = subprocess.check_output([sys.executable, str(INDEXER), "imports", index,
                                                    "Widget"], text=True).strip()
                self.assertEqual(imported, "org.example.Widget")
                location = subprocess.check_output([sys.executable, str(INDEXER), "location", index,
                                                    imported], text=True).strip()
                self.assertTrue(Path(location).is_file())
                self.assertIn("count", (Path(index) / "tags").read_text())
                methods = subprocess.check_output([sys.executable, str(INDEXER), "methods", index,
                                                   imported], text=True)
                self.assertIn("public int count()", methods)

    def test_create_java_project(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sdk = root / "sdk/platforms/android-36"
            sdk.mkdir(parents=True)
            (sdk / "android.jar").touch()
            destination = root / "ExampleApp"
            env = {**os.environ, "ANDROID_HOME": str(root / "sdk")}
            subprocess.run([sys.executable, str(GENERATOR), "ExampleApp", "org.example.app",
                            str(destination), "23"], env=env, check=True, capture_output=True)
            self.assertTrue((destination / "gradlew").is_file())
            self.assertTrue((destination / "app/src/main/java/org/example/app/MainActivity.java").is_file())
            self.assertIn("compileSdk 36", (destination / "app/build.gradle").read_text())

    def test_project_module_source_and_r_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            module = root / "library"
            source = module / "src/main/java/org/example/library/LibraryApi.java"
            source.parent.mkdir(parents=True)
            source.write_text("package org.example.library; public class LibraryApi {}")
            compiled = root / "classes"
            compiled.mkdir()
            subprocess.run(["javac", "-d", str(compiled), str(source)], check=True)
            jar = root / "library.jar"
            with zipfile.ZipFile(jar, "w") as archive:
                archive.write(compiled / "org/example/library/LibraryApi.class",
                              "org/example/library/LibraryApi.class")
            symbols = module / "build/intermediates/compile_symbol_list/debug/generated/R.txt"
            symbols.parent.mkdir(parents=True)
            symbols.write_text("int string library_label 0x7f010001\n")
            manifest = root / ".vim-api/manifests/_app-debug.json"
            manifest.parent.mkdir(parents=True)
            manifest.write_text(json.dumps({"module": ":app", "variant": "debug",
                                            "projectModules": {":library": {
                                                "directory": str(module), "namespace": "org.example.library"}},
                                            "artifacts": [{"path": str(jar),
                                                           "coordinate": "project :library"}]}))
            index = subprocess.check_output([sys.executable, str(INDEXER), "build", str(manifest)],
                                            text=True).strip()
            location = subprocess.check_output([sys.executable, str(INDEXER), "location", index,
                                                "org.example.library.LibraryApi"], text=True).strip()
            self.assertEqual(Path(location), source)
            self.assertIn("library_label", (Path(index) / "tags").read_text())
            r_class = subprocess.check_output([sys.executable, str(INDEXER), "imports", index, "R"],
                                              text=True).strip()
            self.assertEqual(r_class, "org.example.library.R")


if __name__ == "__main__":
    unittest.main()
