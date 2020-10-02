"""A fast, drop-in replacement for pygments ``get_*()`` and ``guess_*()`` funtions.

The following pygments API functions are currently supplied here::

    from pygments_cache import get_lexer_for_filename, guess_lexer_for_filename
    from pygments_cache import get_formatter_for_filename, get_formatter_by_name
    from pygments_cache import get_style_by_name, get_all_styles
    from pygments_cache import get_filter_by_name

The cache itself is stored at the location given by the ``$PYGMENTS_CACHE_FILE``
environment variable, or by default at ``~/.local/share/pygments-cache/cache.py``.
The cache file is created on first use, if it does not already exist.


"""
import os
import importlib


# Global storage variables
__version__ = "0.1.1"
CACHE = None
DEBUG = False


def _print_duplicate_message(duplicates):
    import sys

    for filename, vals in sorted(duplicates.items()):
        msg = "for {0} ambiquity between:\n  ".format(filename)
        vals = [m + ":" + c for m, c in vals]
        msg += "\n  ".join(sorted(vals))
        print(msg, file=sys.stderr)


def _discover_lexers():
    import inspect
    from pygments.lexers import get_all_lexers, find_lexer_class

    # maps file extension (and names) to (module, classname) tuples
    default_exts = {
        # C / C++
        ".h": ("pygments.lexers.c_cpp", "CLexer"),
        ".hh": ("pygments.lexers.c_cpp", "CppLexer"),
        ".cp": ("pygments.lexers.c_cpp", "CppLexer"),
        # python
        ".py": ("pygments.lexers.python", "Python3Lexer"),
        ".pyw": ("pygments.lexers.python", "Python3Lexer"),
        ".sc": ("pygments.lexers.python", "Python3Lexer"),
        ".tac": ("pygments.lexers.python", "Python3Lexer"),
        "SConstruct": ("pygments.lexers.python", "Python3Lexer"),
        "SConscript": ("pygments.lexers.python", "Python3Lexer"),
        ".sage": ("pygments.lexers.python", "Python3Lexer"),
        ".pytb": ("pygments.lexers.python", "Python3TracebackLexer"),
        # perl
        ".t": ("pygments.lexers.perl", "Perl6Lexer"),
        ".pl": ("pygments.lexers.perl", "Perl6Lexer"),
        ".pm": ("pygments.lexers.perl", "Perl6Lexer"),
        # asm
        ".s": ("pygments.lexers.asm", "GasLexer"),
        ".S": ("pygments.lexers.asm", "GasLexer"),
        ".asm": ("pygments.lexers.asm", "NasmLexer"),
        ".ASM": ("pygments.lexers.asm", "NasmLexer"),
        # Antlr
        ".g": ("pygments.lexers.parsers", "AntlrCppLexer"),
        ".G": ("pygments.lexers.parsers", "AntlrCppLexer"),
        # XML
        ".xml": ("pygments.lexers.html", "XmlLexer"),
        ".xsl": ("pygments.lexers.html", "XsltLexer"),
        ".xslt": ("pygments.lexers.html", "XsltLexer"),
        # ASP
        ".axd": ("pygments.lexers.dotnet", "CSharpAspxLexer"),
        ".asax": ("pygments.lexers.dotnet", "CSharpAspxLexer"),
        ".ascx": ("pygments.lexers.dotnet", "CSharpAspxLexer"),
        ".ashx": ("pygments.lexers.dotnet", "CSharpAspxLexer"),
        ".asmx": ("pygments.lexers.dotnet", "CSharpAspxLexer"),
        ".aspx": ("pygments.lexers.dotnet", "CSharpAspxLexer"),
        # misc
        ".b": ("pygments.lexers.esoteric", "BrainfuckLexer"),
        ".j": ("pygments.lexers.jvm", "JasminLexer"),
        ".m": ("pygments.lexers.matlab", "MatlabLexer"),
        ".n": ("pygments.lexers.dotnet", "NemerleLexer"),
        ".p": ("pygments.lexers.pawn", "PawnLexer"),
        ".v": ("pygments.lexers.theorem", "CoqLexer"),
        ".as": ("pygments.lexers.actionscript", "ActionScript3Lexer"),
        ".fs": ("pygments.lexers.forth", "ForthLexer"),
        ".hy": ("pygments.lexers.lisp", "HyLexer"),
        ".ts": ("pygments.lexers.javascript", "TypeScriptLexer"),
        ".rl": ("pygments.lexers.parsers", "RagelCppLexer"),
        ".bas": ("pygments.lexers.basic", "QBasicLexer"),
        ".bug": ("pygments.lexers.modeling", "BugsLexer"),
        ".ecl": ("pygments.lexers.ecl", "ECLLexer"),
        ".inc": ("pygments.lexers.php", "PhpLexer"),
        ".inf": ("pygments.lexers.configs", "IniLexer"),
        ".pro": ("pygments.lexers.prolog", "PrologLexer"),
        ".sql": ("pygments.lexers.sql", "SqlLexer"),
        ".txt": ("pygments.lexers.special", "TextLexer"),
        ".html": ("pygments.lexers.html", "HtmlLexer"),
    }
    exts = {}
    lexers = {"exts": exts}
    if DEBUG:
        from collections import defaultdict

        duplicates = defaultdict(set)
    for longname, aliases, filenames, mimetypes in get_all_lexers():
        cls = find_lexer_class(longname)
        mod = inspect.getmodule(cls)
        val = (mod.__name__, cls.__name__)
        for filename in filenames:
            if filename.startswith("*."):
                filename = filename[1:]
            if "*" in filename:
                continue
            if (
                DEBUG
                and filename in exts
                and exts[filename] != val
                and filename not in default_exts
            ):
                duplicates[filename].add(val)
                duplicates[filename].add(exts[filename])
            exts[filename] = val
    # remove some ambiquity
    exts.update(default_exts)
    # print duplicate message
    if DEBUG:
        _print_duplicate_message(duplicates)
    return lexers


def _discover_formatters():
    import inspect
    from pygments.formatters import get_all_formatters

    # maps file extension (and names) to (module, classname) tuples
    default_exts = {}
    exts = {}
    # maps formatter 'name' (not the class name) and alias to (module, classname) tuples
    default_names = {}
    names = {}
    formatters = {"exts": exts, "names": names}
    if DEBUG:
        from collections import defaultdict

        duplicates = defaultdict(set)
    for cls in get_all_formatters():
        mod = inspect.getmodule(cls)
        val = (mod.__name__, cls.__name__)
        # add extentions
        for filename in cls.filenames:
            if filename.startswith("*."):
                filename = filename[1:]
            if "*" in filename:
                continue
            if (
                DEBUG
                and filename in exts
                and exts[filename] != val
                and filename not in default_exts
            ):
                duplicates[filename].add(val)
                duplicates[filename].add(exts[filename])
            exts[filename] = val
        # add names and aliases
        names[cls.name] = val
        for alias in cls.aliases:
            if (
                DEBUG
                and alias in names
                and names[alias] != val
                and alias not in default_names
            ):
                duplicates[alias].add(val)
                duplicates[alias].add(names[alias])
            names[alias] = val
    # remove some ambiquity
    exts.update(default_exts)
    names.update(default_names)
    # print dumplicate message
    if DEBUG:
        _print_duplicate_message(duplicates)
    return formatters


def _discover_styles():
    import inspect
    from pygments.styles import get_all_styles, get_style_by_name

    # maps style 'name' (not the class name) and aliases to (module, classname) tuples
    default_names = {}
    names = {}
    styles = {"names": names}
    if DEBUG:
        from collections import defaultdict

        duplicates = defaultdict(set)
    for name in get_all_styles():
        cls = get_style_by_name(name)
        mod = inspect.getmodule(cls)
        val = (mod.__name__, cls.__name__)
        if DEBUG and name in names and names[name] != val and name not in default_names:
            duplicates[name].add(val)
            duplicates[name].add(names[name])
        names[name] = val
    # remove some ambiquity
    names.update(default_names)
    # print dumplicate message
    if DEBUG:
        _print_duplicate_message(duplicates)
    return styles


def _discover_filters():
    import inspect
    from pygments.filters import get_all_filters, get_filter_by_name

    # maps filter 'name' (not the class name) to (module, classname) tuples
    default_names = {}
    names = {}
    filters = {"names": names}
    if DEBUG:
        from collections import defaultdict

        duplicates = defaultdict(set)
    for name in get_all_filters():
        filter = get_filter_by_name(name)
        cls = type(filter)
        mod = inspect.getmodule(cls)
        val = (mod.__name__, cls.__name__)
        if DEBUG and name in names and names[name] != val and name not in default_names:
            duplicates[name].add(val)
            duplicates[name].add(names[name])
        names[name] = val
    # remove some ambiquity
    names.update(default_names)
    # print dumplicate message
    if DEBUG:
        _print_duplicate_message(duplicates)
    return filters


def build_cache():
    """Does the hard work of building a cache from nothing."""
    cache = {}
    cache["lexers"] = _discover_lexers()
    cache["formatters"] = _discover_formatters()
    cache["styles"] = _discover_styles()
    cache["filters"] = _discover_filters()
    return cache


def cache_filename():
    """Gets the name of the cache file to use."""
    # Configuration variables read from the environment
    if "PYGMENTS_CACHE_FILE" in os.environ:
        return os.environ["PYGMENTS_CACHE_FILE"]
    else:
        return os.path.join(
            os.environ.get(
                "XDG_DATA_HOME",
                os.path.join(os.path.expanduser("~"), ".local", "share"),
            ),
            "pygments-cache",
            "cache.py",
        )


def load(filename):
    """Loads the cache from a filename."""
    global CACHE
    with open(filename) as f:
        s = f.read()
    ctx = globals()
    CACHE = eval(s, ctx, ctx)
    return CACHE


def write_cache(filename):
    """Writes the current cache to the file"""
    from pprint import pformat

    d = os.path.dirname(filename)
    os.makedirs(d, exist_ok=True)
    s = pformat(CACHE)
    with open(filename, "w") as f:
        f.write(s)


def load_or_build():
    """Loads the cache from disk. If the cache does not exist,
    this will build and write it out.
    """
    global CACHE
    fname = cache_filename()
    if os.path.exists(fname):
        load(fname)
    else:
        import sys

        print("pygments cache not found, building...", file=sys.stderr)
        CACHE = build_cache()
        print("...writing cache to " + fname, file=sys.stderr)
        write_cache(fname)


#
# pygments interface
#


def get_lexer_for_filename(filename, text="", **options):
    """Gets a lexer from a filename (usually via the filename extension).
    This mimics the behavior of ``pygments.lexers.get_lexer_for_filename()``
    and ``pygments.lexers.guess_lexer_for_filename()``.
    """
    if CACHE is None:
        load_or_build()
    exts = CACHE["lexers"]["exts"]
    fname = os.path.basename(filename)
    key = fname if fname in exts else os.path.splitext(fname)[1]
    if key in exts:
        modname, clsname = exts[key]
        mod = importlib.import_module(modname)
        cls = getattr(mod, clsname)
        lexer = cls(**options)
    else:
        # couldn't find lexer in cache, fallback to the hard way
        import inspect
        from pygments.lexers import guess_lexer_for_filename

        lexer = guess_lexer_for_filename(filename, text, **options)
        # add this filename to the cache for future use
        cls = type(lexer)
        mod = inspect.getmodule(cls)
        exts[fname] = (mod.__name__, cls.__name__)
        write_cache(cache_filename())
    return lexer


guess_lexer_for_filename = get_lexer_for_filename


def get_formatter_for_filename(fn, **options):
    """Gets a formatter instance from a filename (usually via the filename
    extension). This mimics the behavior of
    ``pygments.formatters.get_formatter_for_filename()``.
    """
    if CACHE is None:
        load_or_build()
    exts = CACHE["formatters"]["exts"]
    fname = os.path.basename(fn)
    key = fname if fname in exts else os.path.splitext(fname)[1]
    if key in exts:
        modname, clsname = exts[key]
        mod = importlib.import_module(modname)
        cls = getattr(mod, clsname)
        formatter = cls(**options)
    else:
        # couldn't find formatter in cache, fallback to the hard way
        import inspect
        from pygments.formatters import get_formatter_for_filename

        formatter = get_formatter_for_filename(fn, **options)
        # add this filename to the cache for future use
        cls = type(formatter)
        mod = inspect.getmodule(cls)
        exts[fname] = (mod.__name__, cls.__name__)
        write_cache(cache_filename())
    return formatter


def get_formatter_by_name(alias, **options):
    """Gets a formatter instance from its name or alias.
    This mimics the behavior of ``pygments.formatters.get_formatter_by_name()``.
    """
    if CACHE is None:
        load_or_build()
    names = CACHE["formatters"]["names"]
    if alias in names:
        modname, clsname = names[alias]
        mod = importlib.import_module(modname)
        cls = getattr(mod, clsname)
        formatter = cls(**options)
    else:
        # couldn't find formatter in cache, fallback to the hard way
        import inspect
        from pygments.formatters import get_formatter_by_name

        formatter = get_formatter_by_name(alias, **options)
        # add this filename to the cache for future use
        cls = type(formatter)
        mod = inspect.getmodule(cls)
        names[alias] = (mod.__name__, cls.__name__)
        write_cache(cache_filename())
    return formatter


def get_style_by_name(name):
    """Gets a style class from its name or alias.
    This mimics the behavior of ``pygments.styles.get_style_by_name()``.
    """
    if CACHE is None:
        load_or_build()
    names = CACHE["styles"]["names"]
    if name in names:
        modname, clsname = names[name]
        mod = importlib.import_module(modname)
        style = getattr(mod, clsname)
    else:
        # couldn't find style in cache, fallback to the hard way
        import inspect
        from pygments.styles import get_style_by_name

        style = get_style_by_name(name)
        # add this style to the cache for future use
        mod = inspect.getmodule(style)
        names[name] = (mod.__name__, style.__name__)
        write_cache(cache_filename())
    return style


def get_all_styles():
    """Iterable through all known style names.
    This mimics the behavior of ``pygments.styles.get_all_styles``.
    """
    if CACHE is None:
        load_or_build()
    yield from CACHE["styles"]["names"]


def get_filter_by_name(filtername, **options):
    """Gets a filter instance from its name. This mimics the behavior of
    ``pygments.filters.get_filtere_by_name()``.
    """
    if CACHE is None:
        load_or_build()
    names = CACHE["filters"]["names"]
    if filtername in names:
        modname, clsname = names[filtername]
        mod = importlib.import_module(modname)
        cls = getattr(mod, clsname)
        filter = cls(**options)
    else:
        # couldn't find style in cache, fallback to the hard way
        import inspect
        from pygments.filters import get_filter_by_name

        filter = get_filter_by_name(filtername, **options)
        # add this filter to the cache for future use
        cls = type(filter)
        mod = inspect.getmodule(cls)
        names[filtername] = (mod.__name__, cls.__name__)
        write_cache(cache_filename())
    return filter
