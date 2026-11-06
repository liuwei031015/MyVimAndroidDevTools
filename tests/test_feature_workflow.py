"""Exercise layout, resources, Activity, ViewModel, and build as one workflow."""

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parent.parent
EXAMPLE = ROOT / "examples/device-name/app/src/main"
RESOURCE_QUERY = ROOT / "python3/resource_completion.py"
TAG_QUERY = ROOT / "python3/tag_completion.py"
PACKAGE = "dev.example.devicename"


class FeatureWorkflow(unittest.TestCase):
    def prepare(self, destination):
        project = Path(destination)
        (project / "gradlew").touch()
        shutil.copytree(EXAMPLE, project / "app/src/main")
        return project

    def resource_names(self, path, context, lines=None):
        command = [sys.executable, str(RESOURCE_QUERY), str(path), context]
        if lines is not None:
            command.append("--buffer")
        output = subprocess.check_output(command, input=json.dumps(lines) if lines else None,
                                         text=True)
        return [item["word"] for item in json.loads(output)]

    def test_layout_to_viewmodel_completion(self):
        with tempfile.TemporaryDirectory() as directory:
            project = self.prepare(directory)
            layout = project / "app/src/main/res/layout/activity_main.xml"
            strings = project / "app/src/main/res/values/strings.xml"
            activity = project / "app/src/main/java/dev/example/devicename/MainActivity.java"
            view_model = activity.with_name("DeviceNameViewModel.java")
            ET.parse(layout)
            ET.parse(strings)

            self.assertIn('text=""', self.resource_names(layout, "attribute:android:te"))
            self.assertIn('singleLine=""', self.resource_names(layout, "attribute:android:single"))
            self.assertIn('layout_constraintTop_toTopOf=""',
                          self.resource_names(layout, "attribute:app:layout_constraintTop"))
            self.assertIn("device_name_hint", self.resource_names(layout, "resource:string:device"))
            self.assertIn("device_name_input", self.resource_names(activity, "resource:id:device"))
            self.assertIn("activity_main", self.resource_names(activity, "resource:layout:activity"))
            self.assertIn("save_device_name", self.resource_names(layout, "resource:id:save"))

            declarations = {item.get("name") for item in ET.parse(strings).getroot()}
            layout_text = layout.read_text()
            self.assertTrue(set(re.findall(r"@string/(\w+)", layout_text)) <= declarations)
            ids = set(re.findall(r"@\+id/(\w+)", layout_text))
            self.assertTrue(set(re.findall(r"R\.id\.(\w+)", activity.read_text())) <= ids)
            self.assertIn("getName", view_model.read_text())
            self.assertIn("saveName", view_model.read_text())

            tags = project / ".tags"
            subprocess.run(["ctags", "--options=NONE", "--languages=Java",
                            "--fields=+nS", "--output-format=e-ctags", "-R",
                            "-f", str(tags), str(activity.parent)], check=True,
                           capture_output=True)
            index = project / ".vim-api/index/app-debug"
            index.mkdir(parents=True)
            (index / "classes.json").write_text("{}")
            (index / "class-names").write_text("")
            output = subprocess.check_output([sys.executable, str(TAG_QUERY), str(index),
                                              "DeviceName", str(activity), str(tags)], text=True)
            self.assertIn("DeviceNameViewModel", json.loads(output)["project_classes"])
            output = subprocess.check_output([sys.executable, str(TAG_QUERY), str(index),
                                              "saveN", str(activity), str(tags),
                                              "--receiver=viewModel", "--buffer"],
                                             input=json.dumps({"lines": activity.read_text().splitlines(),
                                                               "row": 33}), text=True)
            self.assertEqual([(item["name"], item["owner"])
                              for item in json.loads(output)["methods"]],
                             [("saveName", "DeviceNameViewModel")])

            strings.write_text(strings.read_text().replace("</resources>",
                                 '    <string name="device_name_updated">Updated</string>\n</resources>'))
            self.assertIn("device_name_updated",
                          self.resource_names(layout, "resource:string:device_name_u"))
            self.assertIn("unsaved_name", self.resource_names(
                layout, "resource:id:unsaved", layout_text.splitlines() +
                ['<View android:id="@+id/unsaved_name" />']))

    @unittest.skipUnless(os.environ.get("ANDROID_WORKFLOW_BUILD"),
                         "Set ANDROID_WORKFLOW_BUILD=1 to compile the example")
    def test_generated_project_builds(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "DeviceName"
            subprocess.run([sys.executable, str(ROOT / "python3/new_project.py"),
                            "DeviceName", PACKAGE, str(destination), "23"], check=True,
                           capture_output=True)
            shutil.copytree(EXAMPLE, destination / "app/src/main", dirs_exist_ok=True)
            build_file = destination / "app/build.gradle"
            build_file.write_text(build_file.read_text() + """
dependencies {
    implementation 'androidx.activity:activity:1.9.2'
    implementation 'androidx.lifecycle:lifecycle-livedata:2.8.0'
}
""")
            build = subprocess.run([str(destination / "gradlew"), "--console=plain",
                                    ":app:assembleDebug"], cwd=destination,
                                   capture_output=True, text=True, timeout=600)
            self.assertEqual(build.returncode, 0, (build.stdout + build.stderr)[-5000:])
            self.assertTrue((destination / "app/build/outputs/apk/debug/app-debug.apk").is_file())

            manifest = subprocess.run([str(destination / "gradlew"), "--console=plain",
                                       "-I", str(ROOT / "gradle/android-dev.init.gradle"),
                                       ":app:vimApiManifestDebug"], cwd=destination,
                                      capture_output=True, text=True, timeout=600)
            self.assertEqual(manifest.returncode, 0,
                             (manifest.stdout + manifest.stderr)[-5000:])
            path = re.search(r"VIM_ANDROID_MANIFEST=(.+)", manifest.stdout)
            self.assertIsNotNone(path, manifest.stdout[-2000:])
            index = subprocess.check_output([sys.executable, str(ROOT / "python3/android_dev.py"),
                                             "build", path.group(1)], text=True).strip()
            imports = subprocess.check_output([sys.executable, str(ROOT / "python3/android_dev.py"),
                                               "imports", index, "ViewModelProvider"], text=True)
            self.assertIn("androidx.lifecycle.ViewModelProvider", imports)


if __name__ == "__main__":
    unittest.main()
