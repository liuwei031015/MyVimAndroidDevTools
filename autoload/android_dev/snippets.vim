let s:root = fnamemodify(expand('<sfile>:p'), ':h:h:h')
let s:metadata = json_decode(join(readfile(s:root . '/data/snippet_labels.json'), "\n"))

function! android_dev#snippets#setup() abort
  if !get(g:, 'android_dev_snippet_popup', 1) || exists(':UltiSnipsAddFiletypes') != 2
    return
  endif
  call UltiSnips#SnippetsInCurrentScope(1)
  let l:items = []
  for [l:trigger, l:info] in items(get(g:, 'current_ulti_dict_info', {}))
    if !has_key(s:metadata.labels, l:trigger)
      continue
    endif
    call add(l:items, {'trigger': l:trigger,
          \ 'label': get(s:metadata.labels, l:trigger, l:info.description),
          \ 'description': l:info.description,
          \ 'aliases': get(s:metadata.aliases, l:trigger, '')})
  endfor
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

function! android_dev#snippets#schedule() abort
  if !exists('b:android_dev_snippet_items') || empty(b:android_dev_snippet_items)
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
  let b:android_dev_snippet_timer = timer_start(90,
        \ function('android_dev#snippets#popup', [bufnr('%'), line('.'), col('.')]))
endfunction

function! android_dev#snippets#popup(buffer, row, column, timer) abort
  if bufnr('%') != a:buffer || mode() !=# 'i' || pumvisible()
        \ || !empty(complete_info(['mode']).mode)
        \ || line('.') != a:row || col('.') != a:column
    return
  endif
  let l:before = strpart(getline('.'), 0, col('.') - 1)
  let l:prefix = matchstr(l:before, '[A-Za-z][A-Za-z0-9_]*$')
  let l:start = strlen(l:before) - strlen(l:prefix)
  if strlen(l:prefix) < 2 || (l:start > 0 && strpart(l:before, l:start - 1, 1) =~# '[.@/:<]')
    return
  endif
  let l:items = android_dev#snippets#candidates(l:prefix)
  if !empty(l:items)
    let b:android_dev_snippet_pending = {'start': l:start, 'items': l:items}
    call feedkeys("\<C-x>\<C-u>", 'n')
  endif
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
  if &filetype ==# 'java' && get(g:, 'android_dev_tag_completion', 1)
    return android_dev#extra#complete(a:findstart, a:base)
  endif
  if a:findstart
    let l:before = strpart(getline('.'), 0, col('.') - 1)
    return match(l:before, '[A-Za-z][A-Za-z0-9_]*$')
  endif
  return android_dev#snippets#candidates(a:base)
endfunction

function! android_dev#snippets#expand_selected() abort
  if get(v:completed_item, 'user_data', '') ==# 'android_dev_snippet'
    call timer_start(0, function('android_dev#snippets#expand'))
  endif
endfunction

function! android_dev#snippets#expand(timer) abort
  if mode() ==# 'i' && exists('*UltiSnips#ExpandSnippet')
    call UltiSnips#ExpandSnippet()
  endif
endfunction
