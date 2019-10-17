#!/usr/bin/env xonsh
"""script for compiling elm source and dumping it to the js folder."""
import os
import io

from pygments.formatters import HtmlFormatter

from xonsh.tools import print_color, format_color
from xonsh.style_tools import partial_color_tokenize


$RAISE_SUBPROC_ERROR = True
$XONSH_SHOW_TRACEBACK = False

def escape(s):
    return s.replace("\n", "").replace('"', '\\"')

#
# first, write out elm-src/XonshData.elm
#
xonsh_data_header = """-- A collection of xonsh values for the web-ui
module XonshData exposing (..)

import List
import String

type alias PromptData =
    { name : String
    , value : String
    , display : String
    }
"""

xonsh_data = [xonsh_data_header]

# render prompts
prompts = [
    ("Default", '{env_name}{BOLD_GREEN}{user}@{hostname}{BOLD_BLUE} {cwd}{gitstatus: {}}{NO_COLOR} {BOLD_BLUE}{prompt_end}{NO_COLOR} '),
    ("Just a Dollar", "$ "),
]
xonsh_data.append("""prompts : List PromptData
prompts =""")
for i, (name, value) in enumerate(prompts):
    buf = io.StringIO()
    formatter = HtmlFormatter(noclasses=True, style="default")
    formatter.format(partial_color_tokenize(value), buf)
    display = buf.getvalue()
    item = 'name = "' + name + '", '
    item += 'value = "' + escape(value) + '", '
    item += 'display = "' + escape(display) + '"'
    pre = "    [ " if i == 0 else "    , "
    xonsh_data.append(pre + "{ " + item + " }")
xonsh_data.append("    ]")

# write XonshData.elm
src = "\n".join(xonsh_data) + "\n"
xdelm = os.path.join('elm-src', 'XonshData.elm')
with open(xdelm, 'w') as f:
    f.write(src)

#
# now compile the sources
#
SOURCES = [
    'App.elm',
]
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


