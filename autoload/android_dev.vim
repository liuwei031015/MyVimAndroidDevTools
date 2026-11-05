let s:plugin_root = fnamemodify(expand('<sfile>:p'), ':h:h')
let s:script = s:plugin_root . '/python3/android_dev.py'
let s:init = s:plugin_root . '/gradle/android-dev.init.gradle'

function! s:root() abort
  let l:start = expand('%:p:h')
  if empty(l:start)
    let l:start = getcwd()
  endif
  let l:wrapper = findfile('gradlew', l:start . ';')
  if empty(l:wrapper)
    throw 'Android Gradle wrapper not found'
  endif
  return fnamemodify(l:wrapper, ':p:h')
endfunction

function! android_dev#project_root() abort
  return s:root()
endfunction

function! android_dev#select_variant(...) abort
  return s:choose(s:root(), a:000)
endfunction

function! s:gradle(root, task) abort
  let l:command = 'cd ' . shellescape(a:root) . ' && ./gradlew --console=plain -I '
        \ . shellescape(s:init) . ' ' . shellescape(a:task)
  let l:lines = systemlist(l:command)
  if v:shell_error
    throw join(l:lines[-15:], "\n")
  endif
  return l:lines
endfunction

function! s:variants(root) abort
  let l:variants = []
  for l:line in s:gradle(a:root, 'vimApiList')
    if l:line =~# '^VIM_ANDROID_VARIANT='
      let l:parts = split(strpart(l:line, strlen('VIM_ANDROID_VARIANT=')), '|')
      if len(l:parts) == 3
        call add(l:variants, {'module': l:parts[0], 'variant': l:parts[1], 'task': l:parts[2]})
      endif
    endif
  endfor
  if empty(l:variants)
    throw 'No Android application or library variants found'
  endif
  return l:variants
endfunction

function! s:choose(root, args) abort
  let l:variants = s:variants(a:root)
  if len(a:args) >= 2
    let l:variants = filter(l:variants, 'v:val.module ==# a:args[0] && v:val.variant ==# a:args[1]')
  elseif len(a:args) == 1
    let l:variants = filter(l:variants, 'v:val.variant ==# a:args[0]')
  endif
  if empty(l:variants)
    throw 'Requested Android variant not found'
  endif
  if len(l:variants) == 1
    return l:variants[0]
  endif
  let l:debug = filter(copy(l:variants), 'v:val.variant =~# "Debug$" || v:val.variant ==# "debug"')
  if len(l:debug) == 1 && empty(a:args)
    return l:debug[0]
  endif
  let l:source = resolve(expand('%:p'))
  let l:local = filter(copy(l:variants), 'stridx(l:source, resolve(a:root . substitute(v:val.module, ":", "/", "g")) . "/") == 0')
  if len(l:local) == 1
    return l:local[0]
  endif
  let l:labels = ['Select Android variant:']
  for l:item in l:variants
    call add(l:labels, len(l:labels) . '. ' . l:item.module . ' ' . l:item.variant)
  endfor
  let l:choice = inputlist(l:labels)
  if l:choice < 1 || l:choice > len(l:variants)
    throw 'Android variant selection cancelled'
  endif
  return l:variants[l:choice - 1]
endfunction

function! s:index_path(root, item) abort
  let l:filename = substitute(a:item.module, ':', '_', 'g') . '-' . a:item.variant
  return a:root . '/.vim-api/index/' . l:filename
endfunction

function! android_dev#index(...) abort
  try
    let l:root = s:root()
    let l:item = s:choose(l:root, a:000)
    let l:lines = s:gradle(l:root, l:item.task)
    let l:manifest = ''
    for l:line in l:lines
      if l:line =~# '^VIM_ANDROID_MANIFEST='
        let l:manifest = strpart(l:line, strlen('VIM_ANDROID_MANIFEST='))
      endif
    endfor
    if empty(l:manifest)
      throw 'Gradle did not export an Android dependency manifest'
    endif
    let l:index = system('python3 ' . shellescape(s:script) . ' build ' . shellescape(l:manifest))
    if v:shell_error
      throw l:index
    endif
    let g:android_dev_variant = l:item.variant
    call android_dev#attach_index()
    echom 'Android API index: ' . trim(l:index)
  catch
    echoerr v:exception
  endtry
endfunction

function! android_dev#attach_index() abort
  try
    if exists('b:android_dev_tags')
      let l:existing = split(&l:tags, ',')
      call filter(l:existing, 'index(b:android_dev_tags, v:val) < 0')
      let &l:tags = join(l:existing, ',')
    endif
    let l:index = s:current_index()
    let l:indexes = [l:index . '/tags']
    for l:kind in ['sdk', 'jdk']
      let l:link = l:index . '/' . l:kind . '-tags'
      if filereadable(l:link)
        call add(l:indexes, trim(join(readfile(l:link), '')))
      endif
    endfor
    for l:tag in l:indexes
      if index(split(&l:tags, ','), l:tag) < 0
        let &l:tags .= ',' . escape(l:tag, ' ,')
      endif
    endfor
    let b:android_dev_tags = l:indexes
  catch
  endtry
endfunction

function! android_dev#jdk_sources() abort
  try
    let l:cache = trim(system('python3 ' . shellescape(s:script) . ' jdk'))
    if v:shell_error
      throw l:cache
    endif
    let l:tag = l:cache . '/tags'
    if filereadable(l:tag) && index(split(&l:tags, ','), l:tag) < 0
      let &l:tags .= ',' . escape(l:tag, ' ,')
    endif
    echom 'JDK source index: ' . l:cache
    try
      call s:root()
      echom 'Run :AndroidIndex to add JDK classes to the current project index'
    catch
    endtry
  catch
    echoerr v:exception
  endtry
endfunction

function! s:current_index() abort
  let l:root = s:root()
  let l:indexes = glob(l:root . '/.vim-api/index/*/classes.json', 0, 1)
  if empty(l:indexes)
    throw 'No API index. Run :AndroidIndex first'
  endif
  let l:preferred = get(g:, 'android_dev_variant', '')
  let l:current_file = resolve(expand('%:p'))
  let l:module_candidates = []
  for l:manifest_path in glob(l:root . '/.vim-api/manifests/*.json', 0, 1)
    try
      let l:manifest = json_decode(join(readfile(l:manifest_path), "\n"))
      let l:module = get(l:manifest, 'module', '')
      let l:directory = get(get(get(l:manifest, 'projectModules', {}), l:module, {}), 'directory', '')
      let l:index_path = l:root . '/.vim-api/index/' . fnamemodify(l:manifest_path, ':t:r')
      if !empty(l:directory) && stridx(l:current_file, resolve(l:directory) . '/') == 0
            \ && filereadable(l:index_path . '/classes.json')
        call add(l:module_candidates, {'index': l:index_path,
              \ 'variant': get(l:manifest, 'variant', '')})
      endif
    catch
    endtry
  endfor
  if !empty(l:module_candidates)
    for l:item in l:module_candidates
      if l:item.variant ==# l:preferred
        return l:item.index
      endif
    endfor
    return l:module_candidates[0].index
  endif
  if !empty(l:preferred)
    for l:entry in l:indexes
      if fnamemodify(l:entry, ':h:t') =~# '-' . l:preferred . '$'
        return fnamemodify(l:entry, ':h')
      endif
    endfor
  endif
  return fnamemodify(l:indexes[0], ':h')
endfunction

function! android_dev#current_index() abort
  return s:current_index()
endfunction

function! s:query(action, index, word) abort
  let l:cmd = 'python3 ' . shellescape(s:script) . ' ' . a:action . ' '
        \ . shellescape(a:index) . ' ' . shellescape(a:word)
  let l:lines = systemlist(l:cmd)
  if v:shell_error
    throw join(l:lines, "\n")
  endif
  return l:lines
endfunction

function! android_dev#files(query) abort
  try
    let l:root = s:root()
    let l:spec = fzf#vim#with_preview({'source': 'rg --files -g "*.java" -g "*.kt" -g "*.xml" -g "*.gradle" -g "*.gradle.kts" -g "*.c" -g "*.h" -g "*.py" -g "*.sh"'})
    if !empty(a:query)
      call extend(l:spec.options, ['--query', a:query])
    endif
    call fzf#vim#files(l:root, l:spec, 0)
  catch
    echoerr v:exception
  endtry
endfunction

function! android_dev#path_setup() abort
  if !get(g:, 'android_dev_auto_path', 1)
    return
  endif
  try
    call s:root()
  catch
    return
  endtry
  inoremap <buffer><expr> / android_dev#path_slash()
endfunction

function! android_dev#snippets_setup() abort
  if exists('b:android_dev_snippets') || exists(':UltiSnipsAddFiletypes') != 2
    return
  endif
  try
    call s:root()
  catch
    return
  endtry
  if &filetype ==# 'java'
    UltiSnipsAddFiletypes android_dev_java.java
  elseif &filetype ==# 'xml'
    UltiSnipsAddFiletypes android_dev_xml.xml
  else
    return
  endif
  let b:android_dev_snippets = 1
endfunction

function! android_dev#path_slash() abort
  let l:before = strpart(getline('.'), 0, col('.') - 1)
  let l:path = matchstr(l:before, '[^ \t"''=():;,]*$')
  if l:before =~# '^\s*//' || (empty(l:path) && l:before !~# '["''][^"'']*$')
    return '/'
  endif
  if empty(l:path) || isdirectory(expand(l:path))
    return "/\<C-x>\<C-f>"
  endif
  return '/'
endfunction

function! android_dev#classes(query) abort
  try
    let l:index = s:current_index()
    let l:source = s:query('classes', l:index, '')
    call fzf#run(fzf#wrap({'source': l:source, 'options': '--query=' . shellescape(a:query),
          \ 'sink': function('android_dev#class_selected')}))
  catch
    echoerr v:exception
  endtry
endfunction

function! android_dev#class_selected(line) abort
  let l:name = split(a:line, "\t")[0]
  try
    let l:path = s:query('location', s:current_index(), l:name)[0]
    execute 'edit ' . fnameescape(l:path)
    call search('\<' . escape(split(l:name, '\.')[-1], '\') . '\>', 'w')
  catch
    call android_dev#methods(l:name)
  endtry
endfunction

function! android_dev#methods(query) abort
  try
    let l:name = empty(a:query) ? expand('<cword>') : a:query
    let l:lines = s:query('methods', s:current_index(), l:name)
    botright new
    setlocal buftype=nofile bufhidden=wipe noswapfile filetype=java
    call setline(1, l:lines)
    setlocal nomodifiable
    execute 'file ' . fnameescape('Android API: ' . l:name)
  catch
    echoerr v:exception
  endtry
endfunction

function! android_dev#import() abort
  try
    if &filetype !=# 'java'
      throw 'AndroidImport requires a Java buffer'
    endif
    let l:name = expand('<cword>')
    let l:candidates = []
    let l:root = s:root() . '/'
    for l:tag in taglist('^' . escape(l:name, '\') . '$')
      if index(['c', 'i', 'g', 'a'], get(l:tag, 'kind', '')) < 0 || !filereadable(l:tag.filename)
        continue
      endif
      let l:path = fnamemodify(l:tag.filename, ':p')
      if stridx(l:path, l:root) != 0 || stridx(l:path, l:root . '.vim-api/') == 0
        continue
      endif
      if has_key(l:tag, 'class') || has_key(l:tag, 'interface') || has_key(l:tag, 'enum')
        continue
      endif
      for l:line in readfile(l:tag.filename, '', 100)
        let l:package = matchstr(l:line, '^\s*package\s\+\zs[A-Za-z0-9_.]\+\ze\s*;')
        if !empty(l:package)
          call add(l:candidates, l:package . '.' . l:name)
          break
        endif
      endfor
    endfor
    try
      call extend(l:candidates, s:query('imports', s:current_index(), l:name))
    catch
    endtry
    let l:candidates = uniq(sort(l:candidates))
    let l:current_package = matchstr(join(getline(1, min([line('$'), 100])), "\n"),
          \ '\<package\s\+\zs[A-Za-z0-9_.]\+\ze\s*;')
    call filter(l:candidates, 'v:val !=# "java.lang." . l:name && v:val !=# l:current_package . "." . l:name')
    if empty(l:candidates)
      throw 'No importable class found: ' . l:name
    endif
    let l:choice = len(l:candidates) == 1 ? 1 : inputlist(['Import ' . l:name . ':']
          \ + map(copy(l:candidates), 'v:key + 1 . ". " . v:val'))
    if l:choice < 1 || l:choice > len(l:candidates)
      return
    endif
    let l:statement = 'import ' . l:candidates[l:choice - 1] . ';'
    if index(getline(1, '$'), l:statement) >= 0
      echom 'Already imported: ' . l:statement
      return
    endif
    let l:position = 0
    let l:has_import = 0
    for l:line in range(1, line('$'))
      if getline(l:line) =~# '^\s*\%(package\|import\)\s'
        let l:position = l:line
        if getline(l:line) =~# '^\s*import\s'
          let l:has_import = 1
        endif
      endif
    endfor
    let l:view = winsaveview()
    if !l:has_import && getline(l:position + 1) =~# '^\s*$'
      let l:position += 1
    elseif !l:has_import && l:position > 0
      call append(l:position, '')
      let l:position += 1
    endif
    call append(l:position, l:statement)
    call winrestview(l:view)
  catch
    echoerr v:exception
  endtry
endfunction

function! android_dev#build(kind, ...) abort
  try
    let l:root = s:root()
    let l:item = s:choose(l:root, a:000)
    let l:variant = toupper(strpart(l:item.variant, 0, 1)) . strpart(l:item.variant, 1)
    let l:task = l:item.module . ':' . a:kind . l:variant
    let l:command = 'cd ' . shellescape(l:root) . ' && ./gradlew --console=plain ' . shellescape(l:task)
    let l:lines = systemlist(l:command)
    call setqflist([], 'r', {'lines': l:lines,
          \ 'efm': '%E%f:%l: error: %m,%W%f:%l: warning: %m,%E%f:%l: AAPT: error: %m,%-G%.%#'})
    cwindow
    if v:shell_error
      echoerr a:kind . ' failed; see :copen or :messages'
      return 0
    else
      echom a:kind . ' succeeded: ' . l:task
      call android_dev#index(l:item.module, l:item.variant)
      return 1
    endif
  catch
    echoerr v:exception
    return 0
  endtry
endfunction

function! android_dev#new_project() abort
  try
    let l:name = input('Project name: ')
    let l:package = input('Package name: ', 'com.example.' . tolower(l:name))
    let l:directory = input('Destination: ', getcwd() . '/' . l:name, 'dir')
    let l:min_sdk = input('Minimum SDK: ', '23')
    if l:name !~# '^[A-Za-z][A-Za-z0-9_]*$' ||
          \ l:package !~# '^[A-Za-z_][A-Za-z0-9_]*\(\.[A-Za-z_][A-Za-z0-9_]*\)\+$' ||
          \ l:min_sdk !~# '^\d\+$'
      throw 'Invalid project name, package, or minimum SDK'
    endif
    let l:command = 'python3 ' . shellescape(s:plugin_root . '/python3/new_project.py')
          \ . ' ' . shellescape(l:name) . ' ' . shellescape(l:package)
          \ . ' ' . shellescape(fnamemodify(l:directory, ':p')) . ' ' . shellescape(l:min_sdk)
    let l:result = system(l:command)
    if v:shell_error
      throw l:result
    endif
    echom trim(l:result)
  catch
    echoerr v:exception
  endtry
endfunction
