set nocompatible
let s:root = fnamemodify(expand('<sfile>:p'), ':h:h')
let &runtimepath .= ',' . s:root
let g:android_dev_snippet_popup = 0
execute 'source ' . fnameescape(s:root . '/plugin/android_dev.vim')

let s:project = tempname()
call mkdir(s:project . '/app/src/main/java/com/sample/app', 'p')
call mkdir(s:project . '/app/src/main/java/com/sample/lib', 'p')
call writefile([], s:project . '/gradlew')
let s:activity = s:project . '/app/src/main/java/com/sample/app/Activity.java'
let s:widget = s:project . '/app/src/main/java/com/sample/lib/Widget.java'
call writefile(['package com.sample.app;', '', 'class Activity { Widget widget; }'], s:activity)
call writefile(['package com.sample.lib;', 'public class Widget {}'], s:widget)
call system('ctags --options=NONE --languages=Java --output-format=e-ctags -f '
      \ . shellescape(s:project . '/tags') . ' ' . shellescape(s:widget))
call assert_equal(0, v:shell_error)

execute 'edit ' . fnameescape(s:activity)
setlocal filetype=java
let &l:tags = s:project . '/tags'
call assert_match('android_dev#snippets#manual()', maparg('<C-Space>', 'i'))
call assert_match('android_dev#snippets#manual()', maparg('<F2>', 'i'))
call assert_equal('android_dev#snippets#complete', &l:completefunc)

call setline(3, 'String path = "src/main/";')
call cursor(3, match(getline(3), '/') + 2)
call assert_equal("\<C-x>\<C-f>", android_dev#snippets#manual())
call setline(3, 'import com.sample.Wid')
call cursor(3, strlen(getline(3)) + 1)
call assert_equal("\<C-n>", android_dev#snippets#manual())
call setline(3, 'R.id.')
call cursor(3, strlen(getline(3)) + 1)
call assert_equal('', android_dev#snippets#manual())
setlocal filetype=xml
call setline(3, 'android:text="@string/"')
call cursor(3, match(getline(3), '/') + 2)
call assert_equal('', android_dev#snippets#manual())
setlocal filetype=java
call setline(3, 'class Activity { Widget widget; }')
call cursor(3, 20)
let b:android_dev_pending_imports = ['Widget']
call android_dev#snippets#import_pending()
call assert_equal(1, count(getline(1, '$'), 'import com.sample.lib.Widget;'))
call assert_false(exists('b:android_dev_pending_imports'))
call android_dev#import_name('Widget', 0, 0)
call assert_equal(1, count(getline(1, '$'), 'import com.sample.lib.Widget;'))

call delete(s:project, 'rf')
if !empty(v:errors)
  for s:error in v:errors
    echomsg s:error
  endfor
  cquit
endif
qa!
