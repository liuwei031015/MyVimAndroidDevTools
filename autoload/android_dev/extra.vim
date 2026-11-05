let s:root = fnamemodify(expand('<sfile>:p'), ':h:h:h')
let s:project_tool = s:root . '/python3/project_tools.py'
let s:index_tool = s:root . '/python3/android_dev.py'

function! s:execute(command) abort
  let l:lines = systemlist(a:command)
  if v:shell_error
    throw join(l:lines[-15:], "\n")
  endif
  return l:lines
endfunction

function! s:device() abort
  let l:items = s:execute('python3 ' . shellescape(s:project_tool) . ' devices')
  if empty(l:items)
    throw 'No connected Android device; check adb devices'
  endif
  if exists('g:android_dev_device')
    for l:item in l:items
      if split(l:item, "\t")[0] ==# g:android_dev_device
        return g:android_dev_device
      endif
    endfor
  endif
  if len(l:items) == 1
    let g:android_dev_device = split(l:items[0], "\t")[0]
    return g:android_dev_device
  endif
  let l:choice = inputlist(['Android device:'] + map(copy(l:items), 'v:key + 1 . ". " . v:val'))
  if l:choice < 1 || l:choice > len(l:items)
    throw 'Device selection cancelled'
  endif
  let g:android_dev_device = split(l:items[l:choice - 1], "\t")[0]
  return g:android_dev_device
endfunction

function! android_dev#extra#device() abort
  try
    unlet! g:android_dev_device
    echom 'Android device: ' . s:device()
  catch
    echoerr v:exception
  endtry
endfunction

function! s:manifest(item) abort
  let l:name = substitute(a:item.module, ':', '_', 'g') . '-' . a:item.variant
  let l:path = android_dev#project_root() . '/.vim-api/manifests/' . l:name . '.json'
  if !filereadable(l:path)
    throw 'Run :AndroidIndex for this module and variant first'
  endif
  return json_decode(join(readfile(l:path), "\n"))
endfunction

function! android_dev#extra#run(...) abort
  try
    let l:item = call('android_dev#select_variant', a:000)
    let l:device = s:device()
    if !android_dev#build('install', l:item.module, l:item.variant)
      return
    endif
    let l:package = get(s:manifest(l:item), 'applicationId', '')
    if empty(l:package)
      throw 'The selected module has no application ID; choose an app module'
    endif
    call s:execute('python3 ' . shellescape(s:project_tool) . ' launch '
          \ . shellescape(l:device) . ' ' . shellescape(l:package))
    echom 'Started ' . l:package . ' on ' . l:device
  catch
    echoerr v:exception
  endtry
endfunction

function! android_dev#extra#app_log(level) abort
  try
    let l:device = s:device()
    let l:item = android_dev#select_variant()
    let l:package = get(s:manifest(l:item), 'applicationId', '')
    if empty(l:package)
      throw 'No application ID; select an application module'
    endif
    let l:pid = trim(system('adb -s ' . shellescape(l:device) . ' shell pidof -s ' . shellescape(l:package)))
    if v:shell_error || l:pid !~# '^\d\+$'
      throw 'App is not running: ' . l:package
    endif
    let l:level = empty(a:level) ? 'V' : toupper(a:level)
    if l:level !~# '^[VDIWEF]$'
      throw 'Log level must be V, D, I, W, E, or F'
    endif
    execute 'terminal adb -s ' . shellescape(l:device) . ' logcat -v threadtime --pid=' . l:pid
          \ . ' ' . shellescape('*:' . l:level)
  catch
    echoerr v:exception
  endtry
endfunction

function! s:gradle_task(task, extra) abort
  let l:root = android_dev#project_root()
  let l:command = 'cd ' . shellescape(l:root) . ' && ./gradlew --console=plain '
        \ . shellescape(a:task) . ' ' . a:extra
  let l:lines = systemlist(l:command)
  call setqflist([], 'r', {'lines': l:lines,
        \ 'efm': '%E%f:%l:%c: error: %m,%E%f:%l: error: %m,%W%f:%l:%c: warning: %m,%W%f:%l: warning: %m,%-G%.%#'})
  cwindow
  if v:shell_error
    throw 'Gradle task failed: ' . a:task . '; see :copen or :messages'
  endif
  echom 'Gradle task succeeded: ' . a:task
endfunction

function! android_dev#extra#check(kind, ...) abort
  try
    let l:item = call('android_dev#select_variant', a:000)
    let l:suffix = toupper(l:item.variant[0]) . l:item.variant[1:]
    let l:task = l:item.module . ':'
    if a:kind ==# 'lint'
      let l:task .= 'lint' . l:suffix
    elseif a:kind ==# 'unit'
      let l:task .= 'test' . l:suffix . 'UnitTest'
    else
      call s:device()
      let l:task .= 'connected' . l:suffix . 'AndroidTest'
    endif
    call s:gradle_task(l:task, '')
    if a:kind ==# 'lint'
      let l:module_path = substitute(l:item.module[1:], ':', '/', 'g')
      let l:report = android_dev#project_root() . '/' . l:module_path
            \ . '/build/reports/lint-results-' . l:item.variant . '.xml'
      let l:lines = s:execute('python3 ' . shellescape(s:project_tool) . ' lint ' . shellescape(l:report))
      call setqflist([], 'r', {'lines': l:lines,
            \ 'efm': '%f:%l:%c: %m', 'title': 'Android Lint: ' . l:item.module})
      cwindow
    endif
  catch
    echoerr v:exception
  endtry
endfunction

function! android_dev#extra#sources(...) abort
  try
    let l:item = call('android_dev#select_variant', a:000)
    let l:suffix = toupper(l:item.variant[0]) . l:item.variant[1:]
    let l:task = l:item.module . ':vimApiSources' . l:suffix
    let l:command = 'cd ' . shellescape(android_dev#project_root())
          \ . ' && ./gradlew --console=plain -I ' . shellescape(s:root . '/gradle/android-dev.init.gradle')
          \ . ' ' . shellescape(l:task)
    let l:lines = s:execute(l:command)
    let l:count = len(filter(copy(l:lines), 'v:val =~# "^VIM_ANDROID_SOURCE="'))
    echom 'Resolved ' . l:count . ' source archives; updating index'
    call android_dev#index(l:item.module, l:item.variant)
  catch
    echoerr v:exception
  endtry
endfunction

function! android_dev#extra#resources(query) abort
  try
    let l:item = android_dev#select_variant()
    let l:query = empty(a:query) ? expand('<cWORD>') : a:query
    let l:command = 'python3 ' . shellescape(s:project_tool) . ' resources '
          \ . shellescape(android_dev#project_root()) . ' ' . shellescape(l:item.module)
          \ . ' ' . shellescape(l:item.variant) . ' ' . shellescape(l:query)
    let l:items = s:execute(l:command)
    if empty(l:items)
      throw 'No matching resources: ' . l:query
    endif
    call fzf#run(fzf#wrap({'source': l:items, 'sink': function('android_dev#extra#open_resource')}))
  catch
    echoerr v:exception
  endtry
endfunction

function! android_dev#extra#open_resource(item) abort
  let l:parts = split(a:item, "\t")
  if len(l:parts) < 3
    return
  endif
  let l:path = l:parts[1]
  if l:path =~? '\v\.(png|jpe?g|webp|gif|bmp|ico)$'
    let l:opener = executable('open') ? 'open' : 'xdg-open'
    call system(l:opener . ' ' . shellescape(l:path))
  else
    execute 'edit ' . fnameescape(l:path)
    call cursor(str2nr(l:parts[2]), 1)
  endif
endfunction

function! android_dev#extra#references(query) abort
  try
    let l:word = empty(a:query) ? expand('<cword>') : a:query
    let l:command = 'rg --vimgrep --fixed-strings --glob "!**/build/**" --glob "!**/.vim-api/**" '
          \ . shellescape(l:word) . ' ' . shellescape(android_dev#project_root())
    let l:lines = systemlist(l:command)
    if v:shell_error > 1
      throw join(l:lines, "\n")
    endif
    call setqflist([], 'r', {'lines': l:lines, 'efm': '%f:%l:%c:%m', 'title': 'References: ' . l:word})
    copen
  catch
    echoerr v:exception
  endtry
endfunction

function! android_dev#extra#tasks() abort
  try
    let l:root = android_dev#project_root()
    let l:lines = s:execute('cd ' . shellescape(l:root) . ' && ./gradlew --console=plain tasks --all')
    let l:tasks = []
    for l:line in l:lines
      let l:name = matchstr(l:line, '^\s*\zs[:A-Za-z0-9_-]\+\ze\s\+-')
      if !empty(l:name)
        call add(l:tasks, l:name)
      endif
    endfor
    call fzf#run(fzf#wrap({'source': uniq(sort(l:tasks)), 'sink': function('android_dev#extra#task_selected')}))
  catch
    echoerr v:exception
  endtry
endfunction

function! android_dev#extra#task_selected(task) abort
  try
    call s:gradle_task(a:task, '')
  catch
    echoerr v:exception
  endtry
endfunction

function! android_dev#extra#reports() abort
  try
    let l:root = android_dev#project_root()
    let l:reports = globpath(l:root, '**/build/reports/**/*.html', 0, 1)
    call fzf#run(fzf#wrap({'source': l:reports, 'sink': function('android_dev#extra#open_report')}))
  catch
    echoerr v:exception
  endtry
endfunction

function! android_dev#extra#open_report(path) abort
  call system((executable('open') ? 'open' : 'xdg-open') . ' ' . shellescape(a:path))
endfunction

function! android_dev#extra#complete(findstart, base) abort
  if a:findstart
    let l:line = getline('.')[0 : col('.') - 2]
    return match(l:line, '[A-Za-z_$][A-Za-z0-9_$]*$')
  endif
  try
    let l:command = 'python3 ' . shellescape(s:index_tool) . ' completions '
          \ . shellescape(android_dev#current_index()) . ' ' . shellescape(a:base)
    return s:execute(l:command)
  catch
    return []
  endtry
endfunction

function! android_dev#extra#completion_setup() abort
  if get(g:, 'android_dev_tag_completion', 1) && &filetype ==# 'java'
    if !get(g:, 'android_dev_snippet_popup', 1)
      setlocal completefunc=android_dev#extra#complete
    endif
  endif
endfunction
