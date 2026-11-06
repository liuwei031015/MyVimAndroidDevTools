# Device name workflow

This example exercises one complete Java/XML workflow: edit a device name, reject
empty input, persist the value with `SharedPreferences`, and render it from a
`ViewModel` through `LiveData`.

Create a project with `:AndroidNewProject` using package
`dev.example.devicename`. Copy the `app/src/main` files from this directory into
the new project, then add these dependencies to `app/build.gradle`:

```gradle
dependencies {
    implementation 'androidx.activity:activity:1.9.2'
    implementation 'androidx.lifecycle:lifecycle-livedata:2.8.0'
}
```

The generated manifest already launches `MainActivity`. Run `:AndroidBuild` or
`:AndroidRun` from the project.
