#!/usr/bin/env python3
"""Create a small Java/XML Android application without Android Studio."""

import os
from pathlib import Path
import re
import shutil
import sys
import tempfile


AGP_VERSION = "8.13.2"
GRADLE_VERSION = "8.13"


def sdk_location():
    candidates = [os.environ.get("ANDROID_HOME"), os.environ.get("ANDROID_SDK_ROOT"),
                  str(Path.home() / "Library/Android/sdk")]
    for candidate in candidates:
        if candidate and (Path(candidate) / "platforms").is_dir():
            return Path(candidate).resolve()
    raise ValueError("Android SDK not found; set ANDROID_HOME")


def create(name, package, destination, min_sdk):
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", name):
        raise ValueError("Project name must be an ASCII identifier")
    if not re.fullmatch(r"[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)+", package, re.ASCII):
        raise ValueError("Invalid Java package name")
    sdk = sdk_location()
    versions = [int(item.name[8:]) for item in (sdk / "platforms").glob("android-*")
                if item.name[8:].isdigit() and (item / "android.jar").exists()]
    if not versions:
        raise ValueError("No installed Android platform found")
    compile_sdk = max(versions)
    if not 1 <= min_sdk <= compile_sdk:
        raise ValueError("Minimum SDK exceeds installed compile SDK")
    destination = Path(destination).expanduser().resolve()
    if destination.exists() and any(destination.iterdir()):
        raise ValueError(f"Destination is not empty: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".android-project-", dir=destination.parent))

    def put(path, content):
        target = temporary / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

    try:
        put("settings.gradle", """pluginManagement { repositories { google(); mavenCentral(); gradlePluginPortal() } }
dependencyResolutionManagement { repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories { google(); mavenCentral() } }
rootProject.name = '%s'
include ':app'
""" % name)
        put("build.gradle", "plugins { id 'com.android.application' version '%s' apply false }\n" % AGP_VERSION)
        put("app/build.gradle", """plugins { id 'com.android.application' }
android {
    namespace '%s'
    compileSdk %d
    defaultConfig {
        applicationId '%s'
        minSdk %d
        targetSdk %d
    }
    compileOptions {
        sourceCompatibility JavaVersion.VERSION_17
        targetCompatibility JavaVersion.VERSION_17
    }
}
""" % (package, compile_sdk, package, min_sdk, compile_sdk))
        put("app/src/main/AndroidManifest.xml", """<manifest xmlns:android="http://schemas.android.com/apk/res/android">
    <application android:label="@string/app_name" android:theme="@android:style/Theme.Material.Light.NoActionBar">
        <activity android:name=".MainActivity" android:exported="true">
            <intent-filter>
                <action android:name="android.intent.action.MAIN" />
                <category android:name="android.intent.category.LAUNCHER" />
            </intent-filter>
        </activity>
    </application>
</manifest>
""")
        put("app/src/main/res/values/strings.xml", '<resources><string name="app_name">%s</string></resources>\n' % name)
        put("app/src/main/res/layout/activity_main.xml", """<?xml version="1.0" encoding="utf-8"?>
<FrameLayout xmlns:android="http://schemas.android.com/apk/res/android"
    android:layout_width="match_parent" android:layout_height="match_parent">
    <TextView android:layout_width="wrap_content" android:layout_height="wrap_content"
        android:layout_gravity="center" android:text="@string/app_name" />
</FrameLayout>
""")
        put("app/src/main/java/%s/MainActivity.java" % package.replace(".", "/"), """package %s;

import android.app.Activity;
import android.os.Bundle;

public class MainActivity extends Activity {
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);
    }
}
""" % package)
        put("gradle/wrapper/gradle-wrapper.properties",
            "distributionUrl=https\\://services.gradle.org/distributions/gradle-%s-bin.zip\n" % GRADLE_VERSION)
        put("gradle.properties", "org.gradle.jvmargs=-Xmx2048m -Dfile.encoding=UTF-8\nandroid.useAndroidX=true\n")
        put(".gitignore", ".gradle/\nbuild/\n.vim-api/\nlocal.properties\n")
        template = Path(__file__).resolve().parent.parent / "template"
        for source, target in (("gradlew", "gradlew"), ("gradlew.bat", "gradlew.bat"),
                               ("gradle/wrapper/gradle-wrapper.jar", "gradle/wrapper/gradle-wrapper.jar")):
            destination_file = temporary / target
            destination_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(template / source, destination_file)
        if destination.exists():
            destination.rmdir()
        temporary.rename(destination)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
    print(destination)


if __name__ == "__main__":
    try:
        create(sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4]))
    except (IndexError, ValueError, OSError) as error:
        raise SystemExit(str(error))
