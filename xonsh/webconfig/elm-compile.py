import os
from xonsh.tools import print_color
from xonsh.built_ins import subproc_captured_stdout as capt, subproc_uncaptured as run

#
# now compile the sources
#
SOURCES = [
    "App.elm",
]

HAVE_UGLIFY = False
UGLIFY_FLAGS = (
    'pure_funcs="F2,F3,F4,F5,F6,F7,F8,F9,A2,A3,A4,A5,A6,A7,A8,A9",'
    "pure_getters,keep_fargs=false,unsafe_comps,unsafe"
)


def compile(debug=False):
    if not debug:
        with XSH.env.swap(RAISE_SUBPROC_ERROR=False):
            HAVE_UGLIFY = bool(capt(["which", "uglifyjs"]))
    for source in SOURCES:
        base = os.path.splitext(source.lower())[0]
        src = os.path.join("elm-src", source)
        js_target = os.path.join("js", base + ".js")
        print_color(
            "Compiling {YELLOW}" + src + "{RESET} -> {GREEN}" + js_target + "{RESET}"
        )
        XSH.env["XONSH_SHOW_TRACEBACK"] = True
        try:
            args = ["elm", "make", "--output", js_target, src]
            if not debug:
                args.append("--optimize")
            run(args)
        except Exception as ex:
            print(ex)
            import sys

            sys.exit(1)
        new_files = [js_target]
        min_target = os.path.join("js", base + ".min.js")
        if os.path.exists(min_target):
            run(["rm", "-v", min_target])
        if (not debug) and HAVE_UGLIFY:
            print_color(
                "Minifying {YELLOW}"
                + js_target
                + "{RESET} -> {GREEN}"
                + min_target
                + "{RESET}"
            )
            run(
                ["uglifyjs", js_target, "--compress", UGLIFY_FLAGS],
                "|",
                ["uglifyjs", "--mangle", "--output", min_target],
            )
            new_files.append(min_target)
        run(["ls", "-l"] + new_files)


def main(*args):
    # write_xonsh_data()
    print(args)
    debug = "--debug" in args
    compile(debug)


if __name__ == "__main__":
    from xonsh.built_ins import XSH
    import sys

    XSH.load()
    main(*sys.argv)
