let s:root = fnamemodify(expand('<sfile>:p'), ':h:h:h')
let s:metadata = json_decode(join(readfile(s:root . '/data/snippet_labels.json'), "\n"))
let s:completion_tool = s:root . '/python3/tag_completion.py'
let s:resource_tool = s:root . '/python3/resource_completion.py'

function! android_dev#snippets#map_manual() abort
  for l:key in ['<C-Space>', '<F2>']
    if empty(maparg(l:key, 'i'))
      execute 'inoremap <buffer><silent><expr> ' . l:key . ' android_dev#snippets#manual()'
    endif
  endfor
endfunction

function! android_dev#snippets#manual() abort
  if pumvisible()
    return "\<C-n>"
  endif
  let l:before = strpart(getline('.'), 0, col('.') - 1)
  let l:piece = matchstr(l:before, '[^ \t"''=():;,]*$')
  if l:piece =~# '/' && l:piece !~# '^@'
    return "\<C-x>\<C-f>"
  endif
  if index(['java', 'xml'], &filetype) < 0
    return "\<C-n>"
  endif
  if &filetype ==# 'java' && l:before =~# '^\s*\(import\|package\)\s'
    return "\<C-n>"
  endif
  if l:before !~# '[A-Za-z0-9_]$' && l:before !~# '\%(@+\?\w\+/\|\<R\.\w\+\.\|\<\%(android\|app\|tools\):\)$'
    return "\<C-n>"
  endif
  call android_dev#snippets#reset()
  call timer_start(0, function('android_dev#snippets#popup',
        \ [bufnr('%'), line('.'), col('.'), 1]))
  return ''
endfunction

function! android_dev#snippets#setup() abort
  let l:items = []
  if exists(':UltiSnipsAddFiletypes') == 2
    call UltiSnips#SnippetsInCurrentScope(1)
    for [l:trigger, l:info] in items(get(g:, 'current_ulti_dict_info', {}))
      if !has_key(s:metadata.labels, l:trigger)
        continue
      endif
      call add(l:items, {'trigger': l:trigger,
            \ 'label': get(s:metadata.labels, l:trigger, l:info.description),
            \ 'description': l:info.description,
            \ 'aliases': get(s:metadata.aliases, l:trigger, '')})
    endfor
  endif
  let b:android_dev_snippet_items = l:items
  setlocal completeopt+=menuone,noselect
  setlocal completefunc=android_dev#snippets#complete
endfunction

function! s:rank(item, query) abort
  let l:name = tolower(a:item.trigger)
  if l:name ==# a:query
    return 0
  endif
  if stridx(l:name, a:query) == 0
    return 1
  endif
  for l:word in split(tolower(a:item.aliases . ' ' . a:item.description), '[^a-z0-9_]\+')
    if stridx(l:word, a:query) == 0
      return 2
    endif
  endfor
  return stridx(l:name, a:query) >= 0 ? 3 : 99
endfunction

function! android_dev#snippets#candidates(query) abort
  let l:query = tolower(a:query)
  if strlen(l:query) < 2 || !exists('b:android_dev_snippet_items')
    return []
  endif
  let l:ranked = []
  for l:item in b:android_dev_snippet_items
    let l:rank = s:rank(l:item, l:query)
    if l:rank < 99
      call add(l:ranked, [l:rank, l:item.trigger, l:item])
    endif
  endfor
  call sort(l:ranked)
  let l:result = []
  for l:entry in l:ranked[:11]
    let l:item = l:entry[2]
    call add(l:result, {'word': l:item.trigger, 'abbr': l:item.trigger,
          \ 'menu': l:item.label, 'kind': 'S', 'info': l:item.description,
          \ 'user_data': 'android_dev_snippet'})
  endfor
  return l:result
endfunction

function! s:api_candidates(data, query, member) abort
  let l:methods = []
  for l:item in get(a:data, 'methods', [])[:9]
    let l:signature = get(l:item, 'signature', '')
    call add(l:methods, {'word': l:item.name,
          \ 'abbr': l:item.name . l:signature,
          \ 'menu': get(l:item, 'owner', ''), 'info': l:item.name . l:signature,
          \ 'kind': 'm', 'dup': 1,
          \ 'user_data': json_encode({'type': 'method', 'signature': l:signature})})
  endfor
  if a:member
    return l:methods
  endif
  let l:classes = []
  for l:name in get(a:data, 'project_classes', [])[:6]
    call add(l:classes, {'word': l:name, 'abbr': l:name,
          \ 'menu': '工程类', 'kind': 'C', 'user_data': 'android_dev_class'})
  endfor
  for l:name in get(a:data, 'classes', [])
    if len(l:classes) >= 9
      break
    endif
    if index(get(a:data, 'project_classes', []), l:name) >= 0
      continue
    endif
    call add(l:classes, {'word': l:name, 'abbr': l:name,
          \ 'menu': '依赖类', 'kind': 'C', 'user_data': 'android_dev_class'})
  endfor
  return a:query =~# '^[A-Z]' ? l:classes + l:methods : l:methods + l:classes
endfunction

function! s:show(buffer, row, column, line, start, items) abort
  if empty(a:items) || bufnr('%') != a:buffer || mode() !=# 'i'
        \ || pumvisible() || !empty(complete_info(['mode']).mode)
        \ || line('.') != a:row || col('.') != a:column || getline('.') !=# a:line
    return
  endif
  let b:android_dev_snippet_pending = {'start': a:start, 'items': a:items}
  call feedkeys("\<C-x>\<C-u>", 'n')
endfunction

function! s:api_ready(buffer, row, column, line, start, query, member, snippets, channel, message) abort
  try
    let l:data = json_decode(a:message)
    let l:api = s:api_candidates(l:data, a:query, a:member)
    let l:variables = map(get(l:data, 'variables', []),
          \ "{'word': v:val, 'abbr': v:val, 'menu': '本文件变量', 'kind': 'v'}")
    let l:items = a:query =~# '^[A-Z]' ? l:api + a:snippets : l:variables + a:snippets + l:api
    call s:show(a:buffer, a:row, a:column, a:line, a:start, l:items)
  catch
  endtry
endfunction

function! s:resource_ready(buffer, row, column, line, start, channel, message) abort
  try
    call s:show(a:buffer, a:row, a:column, a:line, a:start, json_decode(a:message))
  catch
  endtry
endfunction

function! s:resource_popup(buffer, row, column, line, start, context) abort
  let l:command = ['python3', s:resource_tool, expand('%:p'), a:context, '--buffer']
  let b:android_dev_snippet_job = job_start(l:command, {'out_cb': function('s:resource_ready',
        \ [a:buffer, a:row, a:column, a:line, a:start])})
  if job_status(b:android_dev_snippet_job) ==# 'run'
    call ch_sendraw(b:android_dev_snippet_job, json_encode(getline(1, '$')) . "\n")
    call ch_close_in(b:android_dev_snippet_job)
  endif
endfunction

function! android_dev#snippets#schedule() abort
  if !get(g:, 'android_dev_snippet_popup', 1)
        \ || pumvisible() || !empty(complete_info(['mode']).mode)
    return
  endif
  let l:position = [line('.'), col('.'), getline('.')]
  if get(b:, 'android_dev_snippet_last', []) ==# l:position
    return
  endif
  let b:android_dev_snippet_last = l:position
  if exists('b:android_dev_snippet_timer')
    call timer_stop(b:android_dev_snippet_timer)
  endif
  if exists('b:android_dev_snippet_job') && job_status(b:android_dev_snippet_job) ==# 'run'
    call job_stop(b:android_dev_snippet_job)
  endif
  let b:android_dev_snippet_timer = timer_start(150,
        \ function('android_dev#snippets#popup', [bufnr('%'), line('.'), col('.'), 0]))
endfunction

function! android_dev#snippets#reset() abort
  if exists('b:android_dev_snippet_timer')
    call timer_stop(b:android_dev_snippet_timer)
  endif
  if exists('b:android_dev_snippet_job') && job_status(b:android_dev_snippet_job) ==# 'run'
    call job_stop(b:android_dev_snippet_job)
  endif
  unlet! b:android_dev_snippet_last b:android_dev_snippet_pending
endfunction

function! android_dev#snippets#popup(buffer, row, column, force, timer) abort
  if bufnr('%') != a:buffer || mode() !=# 'i' || pumvisible()
        \ || !empty(complete_info(['mode']).mode)
        \ || line('.') != a:row || col('.') != a:column
    return
  endif
  let l:before = strpart(getline('.'), 0, col('.') - 1)
  if &filetype ==# 'java' && l:before =~# '^\s*\(import\|package\)\s'
    return
  endif
  if &filetype ==# 'xml'
    let l:resource = matchlist(l:before,
          \ '@+\?\(string\|color\|dimen\|drawable\|mipmap\|layout\|id\|style\|array\)/\([A-Za-z0-9_]*\)$')
    if !empty(l:resource) && (a:force || strlen(l:resource[2]) >= 1)
      call s:resource_popup(a:buffer, a:row, a:column, getline('.'),
            \ strlen(l:before) - strlen(l:resource[2]),
            \ 'resource:' . l:resource[1] . ':' . l:resource[2])
      return
    endif
    let l:attribute = matchlist(l:before, '\s\(android\|app\|tools\):\([A-Za-z_]*\)$')
    if !empty(l:attribute) && (a:force || strlen(l:attribute[2]) >= 2)
      call s:resource_popup(a:buffer, a:row, a:column, getline('.'),
            \ strlen(l:before) - strlen(l:attribute[2]),
            \ 'attribute:' . l:attribute[1] . ':' . l:attribute[2])
      return
    endif
  elseif &filetype ==# 'java'
    let l:resource = matchlist(l:before,
          \ '\<R\.\(string\|color\|dimen\|drawable\|mipmap\|layout\|id\|style\|array\)\.\([A-Za-z0-9_]*\)$')
    if !empty(l:resource) && (a:force || strlen(l:resource[2]) >= 2)
      call s:resource_popup(a:buffer, a:row, a:column, getline('.'),
            \ strlen(l:before) - strlen(l:resource[2]),
            \ 'resource:' . l:resource[1] . ':' . l:resource[2])
      return
    endif
  endif
  let l:prefix = matchstr(l:before, '[A-Za-z][A-Za-z0-9_]*$')
  let l:start = strlen(l:before) - strlen(l:prefix)
  let l:previous = l:start > 0 ? strpart(l:before, l:start - 1, 1) : ''
  if strlen(l:prefix) < (a:force ? 1 : 2) || l:previous =~# '[@/:<]'
    return
  endif
  let l:member = l:previous ==# '.'
  let l:items = l:member ? [] : android_dev#snippets#candidates(l:prefix)[:5]
  let l:receiver = l:member ? matchstr(strpart(l:before, 0, l:start - 1), '[A-Za-z_$][A-Za-z0-9_$]*$') : ''
  if &filetype ==# 'java' && strlen(l:prefix) >= (a:force ? 1 : 3)
        \ && get(g:, 'android_dev_tag_completion', 1) && has('job')
    try
      let l:index = android_dev#current_index()
    catch
      let l:index = ''
    endtry
    let l:command = ['python3', s:completion_tool, l:index, l:prefix, expand('%:p')]
          \ + tagfiles()
    call add(l:command, '--buffer')
    if !empty(l:receiver)
      call add(l:command, '--receiver=' . l:receiver)
    endif
    let b:android_dev_snippet_job = job_start(l:command, {'out_cb': function('s:api_ready',
          \ [a:buffer, a:row, a:column, getline('.'), l:start, l:prefix, l:member, l:items])})
    if job_status(b:android_dev_snippet_job) ==# 'fail'
      call s:show(a:buffer, a:row, a:column, getline('.'), l:start, l:items)
    else
      call ch_sendraw(b:android_dev_snippet_job,
            \ json_encode({'lines': getline(1, '$'), 'row': a:row}) . "\n")
      call ch_close_in(b:android_dev_snippet_job)
    endif
    return
  endif
  call s:show(a:buffer, a:row, a:column, getline('.'), l:start, l:items)
endfunction

function! android_dev#snippets#complete(findstart, base) abort
  if exists('b:android_dev_snippet_pending')
    if a:findstart
      return b:android_dev_snippet_pending.start
    endif
    let l:items = b:android_dev_snippet_pending.items
    unlet b:android_dev_snippet_pending
    return l:items
  endif
  if a:findstart
    let l:before = strpart(getline('.'), 0, col('.') - 1)
    return match(l:before, '[A-Za-z][A-Za-z0-9_]*$')
  endif
  return android_dev#snippets#candidates(a:base)
endfunction

function! android_dev#snippets#expand_selected() abort
  let l:data = get(v:completed_item, 'user_data', '')
  if l:data ==# 'android_dev_snippet'
    call timer_start(0, function('android_dev#snippets#expand'))
  elseif l:data ==# 'android_dev_xml_attr'
    call timer_start(0, function('android_dev#snippets#xml_attr_cursor'))
  elseif l:data ==# 'android_dev_class' && &filetype ==# 'java'
    let l:name = get(v:completed_item, 'word', '')
    let b:android_dev_pending_imports = get(b:, 'android_dev_pending_imports', [])
    if !empty(l:name) && index(b:android_dev_pending_imports, l:name) < 0
      call add(b:android_dev_pending_imports, l:name)
    endif
  elseif l:data =~# '{'
    let l:item = json_decode(l:data)
    if get(l:item, 'type', '') ==# 'method'
      call timer_start(0, function('android_dev#snippets#expand_method',
            \ [get(v:completed_item, 'word', ''), get(l:item, 'signature', '')]))
    endif
  endif
endfunction

function! android_dev#snippets#import_pending() abort
  let l:names = get(b:, 'android_dev_pending_imports', [])
  unlet! b:android_dev_pending_imports
  for l:name in l:names
    call android_dev#import_name(l:name, 1, 0)
  endfor
endfunction

function! android_dev#snippets#xml_attr_cursor(timer) abort
  if mode() ==# 'i'
    call feedkeys("\<Left>", 'n')
  endif
endfunction

function! s:parameter_names(signature) abort
  let l:body = matchstr(a:signature, '^(\zs.*\ze)')
  if empty(l:body)
    return []
  endif
  let l:parts = []
  let l:part = ''
  let l:depth = 0
  for l:character in split(l:body, '\zs')
    if index(['<', '(', '['], l:character) >= 0
      let l:depth += 1
    elseif index(['>', ')', ']'], l:character) >= 0
      let l:depth = max([0, l:depth - 1])
    elseif l:character ==# ',' && l:depth == 0
      call add(l:parts, trim(l:part))
      let l:part = ''
      continue
    endif
    let l:part .= l:character
  endfor
  call add(l:parts, trim(l:part))
  let l:names = []
  for l:part in l:parts
    let l:name = l:part =~# '\s' ? matchstr(l:part, '[A-Za-z_$][A-Za-z0-9_$]*$') : ''
    call add(l:names, empty(l:name) ? 'arg' . (len(l:names) + 1) : l:name)
  endfor
  return l:names
endfunction

function! android_dev#snippets#call_template(signature) abort
  let l:arguments = []
  for l:name in s:parameter_names(a:signature)
    call add(l:arguments, '${' . (len(l:arguments) + 1) . ':' . substitute(l:name, '\$', '_', 'g') . '}')
  endfor
  if empty(a:signature)
    let l:arguments = ['${1}']
  endif
  return '(' . join(l:arguments, ', ') . ')'
endfunction

function! android_dev#snippets#expand_method(name, signature, timer) abort
  if mode() !=# 'i' || empty(a:name)
    return
  endif
  if strpart(getline('.'), col('.') - 1, 1) ==# '('
    return
  endif
  call UltiSnips#Anon(android_dev#snippets#call_template(a:signature))
endfunction

function! android_dev#snippets#expand(timer) abort
  if mode() ==# 'i' && exists('*UltiSnips#ExpandSnippet')
    call UltiSnips#ExpandSnippet()
  endif
endfunction
