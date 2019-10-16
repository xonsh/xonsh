#!/usr/bin/env xonsh
"""script for compiling elm source and dumping it to the js folder."""
import os
from xonsh.tools import print_color


SOURCES = [
    'App.elm',
]
$RAISE_SUBPROC_ERROR = True
$XONSH_SHOW_TRACEBACK = False
with ${...}.swap(RAISE_SUBPROC_ERROR=False):
    HAVE_UGLIFY = bool(!(which uglifyjs e>o))

UGLIFY_FLAGS = ('pure_funcs="F2,F3,F4,F5,F6,F7,F8,F9,A2,A3,A4,A5,A6,A7,A8,A9",'
                'pure_getters,keep_fargs=false,unsafe_comps,unsafe')


for source in SOURCES:
    base = os.path.splitext(source.lower())[0]
    src = os.path.join('elm-src', source)
    js_target = os.path.join('js', base + '.js')
    print_color('Compiling {YELLOW}' + src + '{NO_COLOR} -> {GREEN}' +
                js_target + '{NO_COLOR}')
    $XONSH_SHOW_TRACEBACK = False
    try:
        ![elm make --optimize --output @(js_target) @(src)]
    except Exception:
        import sys
        sys.exit(1)
    new_files = [js_target]
    min_target = os.path.join('js', base + '.min.js')
    if os.path.exists(min_target):
        ![rm -v @(min_target)]
    if HAVE_UGLIFY:
        print_color('Minifying {YELLOW}' + js_target + '{NO_COLOR} -> {GREEN}' +
                    min_target + '{NO_COLOR}')
        ![uglifyjs @(js_target) --compress @(UGLIFY_FLAGS) |
          uglifyjs --mangle --output @(min_target)]
        new_files.append(min_target)
    ![ls -l @(new_files)]


