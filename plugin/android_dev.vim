if exists('g:loaded_android_dev_tools')
  finish
endif
let g:loaded_android_dev_tools = 1

let g:UltiSnipsExpandTrigger = get(g:, 'UltiSnipsExpandTrigger', '<leader><tab>')
let g:UltiSnipsJumpForwardTrigger = get(g:, 'UltiSnipsJumpForwardTrigger', '<c-j>')
let g:UltiSnipsJumpBackwardTrigger = get(g:, 'UltiSnipsJumpBackwardTrigger', '<c-k>')
let g:UltiSnipsEditSplit = get(g:, 'UltiSnipsEditSplit', 'vertical')
let g:gutentags_project_root = get(g:, 'gutentags_project_root', ['.git', '.root', 'settings.gradle', 'settings.gradle.kts'])
let g:gutentags_modules = get(g:, 'gutentags_modules', ['ctags'])
let g:gutentags_ctags_tagfile = get(g:, 'gutentags_ctags_tagfile', '.tags')
let g:gutentags_ctags_auto_set_tags = get(g:, 'gutentags_ctags_auto_set_tags', 1)
let g:gutentags_cache_dir = get(g:, 'gutentags_cache_dir', expand('~/.cache/tags'))
let g:gutentags_ctags_extra_args = get(g:, 'gutentags_ctags_extra_args',
      \ ['--fields=+niazS', '--extras=+q', '--c++-kinds=+px', '--c-kinds=+px',
      \ '--java-kinds=+l', '--exclude=build', '--exclude=.gradle', '--exclude=.idea',
      \ '--exclude=.cxx', '--exclude=.vim-api', '--output-format=e-ctags'])
if !isdirectory(g:gutentags_cache_dir)
  call mkdir(g:gutentags_cache_dir, 'p')
endif

command! -nargs=* AndroidIndex call call('android_dev#index', split(<q-args>))
command! -nargs=* AndroidBuild call call('android_dev#build', ['assemble'] + split(<q-args>))
command! -nargs=* AndroidInstall call call('android_dev#build', ['install'] + split(<q-args>))
command! -nargs=0 AndroidLog terminal adb logcat -v threadtime
command! -nargs=? AndroidProjectFiles call android_dev#files(<q-args>)
command! -nargs=? AndroidClasses call android_dev#classes(<q-args>)
command! -nargs=? AndroidMethods call android_dev#methods(<q-args>)
command! -nargs=0 AndroidImport call android_dev#import()
command! -nargs=0 AndroidNewProject call android_dev#new_project()
command! -nargs=0 AndroidJdkSources call android_dev#jdk_sources()
command! -nargs=* AndroidRun call call('android_dev#extra#run', split(<q-args>))
command! -nargs=0 AndroidDevice call android_dev#extra#device()
command! -nargs=? AndroidAppLog call android_dev#extra#app_log(<q-args>)
command! -nargs=* AndroidLint call call('android_dev#extra#check', ['lint'] + split(<q-args>))
command! -nargs=* AndroidUnitTest call call('android_dev#extra#check', ['unit'] + split(<q-args>))
command! -nargs=* AndroidDeviceTest call call('android_dev#extra#check', ['device'] + split(<q-args>))
command! -nargs=* AndroidSources call call('android_dev#extra#sources', split(<q-args>))
command! -nargs=? AndroidResources call android_dev#extra#resources(<q-args>)
command! -nargs=? AndroidReferences call android_dev#extra#references(<q-args>)
command! -nargs=0 AndroidTasks call android_dev#extra#tasks()
command! -nargs=0 AndroidReports call android_dev#extra#reports()

if get(g:, 'android_dev_default_mappings', 1)
  nnoremap <silent> <leader>ff :AndroidProjectFiles<CR>
  nnoremap <silent> <leader>fc :execute 'AndroidProjectFiles ' . expand('<cword>')<CR>
  nnoremap <silent> <leader>fa :Files<CR>
  nnoremap <silent> <leader>fb :Buffers<CR>
  nnoremap <silent> <leader>ft :Lines<CR>
  nnoremap <silent> <leader>fw :execute 'Rg ' . expand('<cword>')<CR>
  nnoremap <silent> <leader>fT :execute 'Tags ' . expand('<cword>')<CR>
  nnoremap <silent> <leader>fB :BTags<CR>
  nnoremap <silent> <leader>fs :Snippets<CR>
  nnoremap <silent> <leader>q :AndroidImport<CR>
  nnoremap <silent> <leader>fr :AndroidResources<CR>
  nnoremap <silent> <leader>fu :AndroidReferences<CR>
endif

" Android Studio macOS keymap where Vim's normal-mode keys remain unbound.
if get(g:, 'android_dev_ide_mappings', 1)
  if empty(maparg('<M-CR>', 'n'))
    nnoremap <silent> <M-CR> :AndroidImport<CR>
  endif
  if empty(maparg('<D-o>', 'n'))
    nnoremap <silent> <D-o> :AndroidClasses<CR>
  endif
  if empty(maparg('<D-S-o>', 'n'))
    nnoremap <silent> <D-S-o> :AndroidProjectFiles<CR>
  endif
  if empty(maparg('<D-b>', 'n'))
    nnoremap <silent> <D-b> <C-]>
  endif
  if empty(maparg('<D-6>', 'n'))
    nnoremap <silent> <D-6> :AndroidLog<CR>
  endif
  if empty(maparg('<S-F10>', 'n'))
    nnoremap <silent> <S-F10> :AndroidRun<CR>
  endif
endif

augroup android_dev_tools
  autocmd!
  autocmd BufEnter *.java,*.kt,*.xml call android_dev#attach_index()
  autocmd FileType java,xml,gradle,groovy,python,sh,c,cpp call android_dev#path_setup()
  autocmd FileType java call android_dev#extra#completion_setup()
augroup END
