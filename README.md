# MyVimAndroidDevTools

Vim 8.2+ / Vim 9 Android Java development without a language server. The plugin
combines UltiSnips, fzf, Universal Ctags, Gradle, `javap`, and `adb`.

## Requirements

- Vim with `+terminal`; Python 3, Java 17+, Universal Ctags, `rg`, `javap`
- `fzf`, `fzf.vim`, `UltiSnips`; `vim-gutentags` for project source tags
- Android SDK and an Android project with a Gradle wrapper
- Android Gradle Plugin with `androidComponents.onVariants` (tested with AGP 8.13.2)

With vim-plug:

```vim
Plug 'junegunn/fzf', { 'do': { -> fzf#install() } }
Plug 'junegunn/fzf.vim'
Plug 'SirVer/ultisnips'
Plug 'ludovicchabant/vim-gutentags'
Plug 'liuwei031015/MyVimAndroidDevTools'
```

Set `let mapleader = ','` before loading plugins to use the documented mappings.
Remove older copies of these snippets, commands, and mappings from `~/.vimrc` to
avoid duplicate definitions. Run `:helptags ALL`, then `:help android-dev-tools`.

## Commands

| Command | Purpose |
| --- | --- |
| `:AndroidIndex [module variant]` | Export resolved compile dependencies and update `.vim-api/` |
| `:AndroidClasses [query]` | fzf search for SDK and library classes; Enter opens source or declaration |
| `:AndroidMethods [qualified-class]` | Show public constructors and methods with `javap` |
| `:AndroidImport` | Import class under cursor from source tags or dependency index |
| `:AndroidProjectFiles [query]` | fzf search all Android source sets |
| `:AndroidBuild [module variant]` | Assemble chosen variant, then update index |
| `:AndroidInstall [module variant]` | Install chosen app variant |
| `:AndroidLog` | Open `adb logcat` in a Vim terminal |
| `:AndroidNewProject` | Create a minimal Java/XML Android app |
| `:AndroidJdkSources` | Index the installed JDK `src.zip`, or download OpenJDK sources if missing |
| `:AndroidSources [module variant]` | Resolve third-party source archives with Gradle and rebuild the index |
| `:AndroidResources [@type/name]` | Find a resource in the selected module/variant; open image files externally |
| `:AndroidReferences [text]` | Search literal references into quickfix |
| `:AndroidRun [module variant]` | Select device, install, and launch an app |
| `:AndroidDevice` | Change the active adb device |
| `:AndroidAppLog [V/D/I/W/E/F]` | Follow the running app process's log at a minimum level |
| `:AndroidLint`, `:AndroidUnitTest`, `:AndroidDeviceTest` | Run checks for a selected module/variant |
| `:AndroidTasks`, `:AndroidReports` | Pick a Gradle task or open a generated HTML report |

Example: `:AndroidIndex :app debug`. When the variant is ambiguous, the command
prompts for one. Set `g:android_dev_variant` to prefer a variant when querying
multiple existing indexes. The default build command finds a single debug variant
automatically.

Index results are generated in `<project>/.vim-api/`; add that path to `.gitignore`.
The Android SDK source tags are shared in `~/.cache/vim-android-dev/`. Install the
matching `sources;android-N` SDK package for SDK definition jumps. When source JARs
are missing, generated Java API declarations support ctags navigation while
`javap` shows the full public signature. These declarations are reference data,
not executable implementations.

JDK source tags are also shared in `~/.cache/vim-android-dev/`. The plugin uses
the active JDK's `src.zip` when present. `:AndroidJdkSources` downloads the
matching OpenJDK source archive from `github.com/openjdk` if needed, then builds
the public index. Run `:AndroidIndex` to include its classes in a project index.
The selected variant's generated `R.txt` is converted into a reference-only
`R.java`, so `R.id`, `R.layout`, and other resource fields are available to ctags.
For multi-module builds, the Gradle task resolves project library artifacts and
class navigation opens the module's actual Java source where available.

Java buffers also offer manual class-name completion with `<C-x><C-u>` from the
project API index. Set `g:android_dev_tag_completion = 0` to disable it. The
plugin does not infer receiver types or perform semantic rename.

The included Gradle init script is passed by `:AndroidIndex` without changing a
project's build scripts. `:AndroidBuild` refreshes the index after a successful
build. External `./gradlew` invocations do not trigger this plugin's index task;
run `:AndroidIndex` after changing dependencies.

For the complete shortcut list and troubleshooting, see `:help android-dev-tools`.

Run focused checks with `python3 -m unittest discover -s tests -v`.
