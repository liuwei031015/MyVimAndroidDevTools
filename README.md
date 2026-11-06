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

Java buffers show class and method candidates automatically after three typed
characters. Project source classes rank before dependency classes for uppercase
prefixes such as `Android`; methods from the current class and its direct parent
rank before unrelated methods for lowercase prefixes such as `show`. Method
candidates include signatures and overloads; selecting one inserts a call with
jumpable argument placeholders. Queries run in a cancellable background job after
a short idle delay, so typing does not wait for ctags. Method candidates are not
filtered by receiver type, so check the displayed owner before accepting one.
Manual class-name completion remains available with `<C-x><C-u>`. Set
`g:android_dev_tag_completion = 0` to disable API candidates. Run
`:AndroidIndex` after updating to rebuild dependency tags with signatures.
The plugin does not perform semantic rename.

The included Gradle init script is passed by `:AndroidIndex` without changing a
project's build scripts. `:AndroidBuild` refreshes the index after a successful
build. External `./gradlew` invocations do not trigger this plugin's index task;
run `:AndroidIndex` after changing dependencies.

For the complete shortcut list and troubleshooting, see `:help android-dev-tools`.

Android project Java/XML buffers automatically merge the bundled Android
UltiSnips files with their normal filetype snippets. The templates cover
Activity Result, permissions, saved state, preferences, notification channels,
view events, resources, drawables, and manifest declarations. AndroidX templates
require the corresponding AndroidX dependency in the project. Browse triggers
with `:Snippets` or see `:help android-dev-snippet`.

In Java and XML, typing at least two letters opens Vim's native snippet menu.
Entries show Chinese descriptions; common snippets also match pinyin aliases
(for example, `quanxian` finds `permission`). Use Ctrl-N/Ctrl-P and Ctrl-Y to
select and expand, or keep using the UltiSnips expansion key. Set
`g:android_dev_snippet_popup = 0` before loading the plugin to disable the menu.
The included Java Stream templates need API 24+ or core library desugaring on
older Android versions. AndroidX and ViewBinding templates need their matching
project dependencies and build features.

Run focused checks with `python3 -m unittest discover -s tests -v`.
