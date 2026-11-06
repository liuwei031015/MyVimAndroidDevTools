"""Simulate typing in one Java file and compare suggestions with intent."""

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parent.parent
QUERY = ROOT / "python3/tag_completion.py"
SOURCE = """package example;

class AndroidAppUtils {}
class AndroidScreenOrientation {}
class BaseActivity {
    public void showLoading() {}
    public void showLoading(String message) {}
}
public class AboutActivity extends BaseActivity {
    void develop() {
        showLoading();
        AndroidAppUtils helper = null;
    }
}
"""


class CompletionWorkshop(unittest.TestCase):
    def test_development_suggestions_match_intent(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            (project / "gradlew").touch()
            source = project / "AboutActivity.java"
            source.write_text(SOURCE)
            tags = project / ".tags"
            subprocess.run(["ctags", "--options=NONE", "--languages=Java", "--fields=+nS",
                            "--output-format=e-ctags", "-f", str(tags), str(source)],
                           check=True, capture_output=True)
            index = project / ".vim-api/index/app-debug"
            index.mkdir(parents=True)
            (index / "classes.json").write_text(json.dumps({"external.AndroidRemote": {}}))
            (index / "class-names").write_text("AndroidRemote\n")
            external = project / "external.tags"
            external.write_text("!_TAG_FILE_SORTED\t1\t/0=unsorted/\n"
                                "show\tExternal.java\t1;\"\tm\tclass:ExternalDialog\tsignature:()\n")

            def suggest(prefix):
                output = subprocess.check_output([sys.executable, str(QUERY), str(index),
                                                  prefix, str(source), str(tags), str(external)],
                                                 text=True)
                return json.loads(output)

            show = suggest("show")
            self.assertEqual(show["methods"][0]["name"], "showLoading")
            self.assertEqual(show["methods"][0]["owner"], "BaseActivity")
            android = suggest("Android")
            self.assertEqual(android["project_classes"][0], "AndroidAppUtils")
            self.assertIn("AndroidRemote", android["classes"])
            self.assertEqual(android["methods"], [])


if __name__ == "__main__":
    unittest.main()
