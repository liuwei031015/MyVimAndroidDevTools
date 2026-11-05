import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
import zipfile


ROOT = Path(__file__).resolve().parent.parent
INDEXER = ROOT / "python3/android_dev.py"
GENERATOR = ROOT / "python3/new_project.py"
PROJECT_TOOLS = ROOT / "python3/project_tools.py"
TAG_COMPLETION = ROOT / "python3/tag_completion.py"


class ToolTests(unittest.TestCase):
    def test_tag_method_signatures_and_class_prefix(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "classes.json").write_text(json.dumps({"org.example.Widget": {}}))
            (root / "class-names").write_text("Widget\n")
            tags = root / "tags"
            tags.write_text("!_TAG_FILE_SORTED\t1\t/0=unsorted/\n"
                            "set\tWidget.java\t1;\"\tm\tclass:Widget\tsignature:(int count)\n"
                            "set\tWidget.java\t2;\"\tm\tclass:Widget\tsignature:(String text)\n"
                            "setHidden\tWidget.java\t3;\"\tm\tclass:Widget\taccess:private\n"
                            "size\tWidget.java\t4;\"\tm\tclass:Widget\tsignature:()\n")
            output = subprocess.check_output([sys.executable, str(TAG_COMPLETION), str(root),
                                              "set", "", str(tags)], text=True)
            data = json.loads(output)
            self.assertEqual(data["classes"], [])
            self.assertEqual([item["signature"] for item in data["methods"]],
                             ["(int count)", "(String text)"])
            output = subprocess.check_output([sys.executable, str(TAG_COMPLETION), str(root),
                                              "Wid", "", str(tags)], text=True)
            self.assertEqual(json.loads(output)["classes"], ["Widget"])

    def test_method_call_parameter_placeholders(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "template"
            command = ("set rtp^=" + str(ROOT) + " | call writefile(["
                       "android_dev#snippets#call_template('(Map<String, Integer> values, int flags)'), "
                       "android_dev#snippets#call_template('()')], '" + str(output) + "') | qa!")
            subprocess.run(["vim", "-Nu", "NONE", "-n", "-es", "-c", command], check=True)
            self.assertEqual(output.read_text().splitlines(),
                             ["(${1:values}, ${2:flags})", "()"])

    def test_snippet_menu_labels_cover_bundled_triggers(self):
        labels = json.loads((ROOT / "data/snippet_labels.json").read_text())["labels"]
        for path in (ROOT / "UltiSnips").glob("*.snippets"):
            triggers = set(re.findall(r"^snippet\s+(\S+)", path.read_text(), re.MULTILINE))
            self.assertFalse(triggers - labels.keys(), f"Missing labels in {path.name}")

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
                tags = (Path(index) / "tags").read_text()
                self.assertRegex(tags, r"count\t[^\n]*signature:\(\)")
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

    def test_resource_lookup_by_module_variant_and_type(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            main = root / "app/src/main/res"
            debug = root / "app/src/debug/res"
            library = root / "library/src/main/res"
            for folder in (main / "values", main / "drawable", debug / "values",
                           library / "values"):
                folder.mkdir(parents=True)
            (main / "values/colors.xml").write_text(
                '<resources>\n<color name="brand">#ff0000</color>\n</resources>\n')
            (debug / "values/colors.xml").write_text(
                '<resources><color name="brand">#00ff00</color></resources>')
            (library / "values/colors.xml").write_text(
                '<resources><color name="brand">#0000ff</color></resources>')
            (main / "drawable/icon.png").write_bytes(b"png")
            output = subprocess.check_output([sys.executable, str(PROJECT_TOOLS), "resources",
                                              str(root), ":app", "debug", "@color/brand"], text=True)
            self.assertEqual(len(output.splitlines()), 2)
            self.assertNotIn("library", output)
            output = subprocess.check_output([sys.executable, str(PROJECT_TOOLS), "resources",
                                              str(root), ":app", "release", "R.color.brand"], text=True)
            self.assertEqual(len(output.splitlines()), 1)
            output = subprocess.check_output([sys.executable, str(PROJECT_TOOLS), "resources",
                                              str(root), ":app", "debug", "@drawable/icon"], text=True)
            self.assertIn("drawable/icon", output)

    def test_lint_report_to_quickfix_lines(self):
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / "lint-results-debug.xml"
            report.write_text('<issues><issue id="Missing" severity="Warning" message="Missing icon">'
                              '<location file="/tmp/app/AndroidManifest.xml" line="3" column="2"/>'
                              '</issue></issues>')
            output = subprocess.check_output([sys.executable, str(PROJECT_TOOLS), "lint",
                                              str(report)], text=True)
            self.assertEqual(output.strip(),
                             "/tmp/app/AndroidManifest.xml:3:2: warning: Missing icon [Missing]")


if __name__ == "__main__":
    unittest.main()
