# -*- coding: utf-8 -*-
"""Tools for inspecting Python objects.

This file was forked from the IPython project:

* Copyright (c) 2008-2014, IPython Development Team
* Copyright (C) 2001-2007 Fernando Perez <fperez@colorado.edu>
* Copyright (c) 2001, Janko Hauser <jhauser@zscout.de>
* Copyright (c) 2001, Nathaniel Gray <n8gray@caltech.edu>
"""
import os
import io
import sys
import types
import inspect
import itertools
import linecache
import collections

from xonsh.lazyasd import LazyObject
from xonsh.tokenize import detect_encoding
from xonsh.openpy import read_py_file
from xonsh.tools import cast_unicode, safe_hasattr, indent, print_color, format_color
from xonsh.platform import HAS_PYGMENTS, PYTHON_VERSION_INFO
from xonsh.lazyimps import pygments, pyghooks
from xonsh.style_tools import partial_color_tokenize


# builtin docstrings to ignore
_func_call_docstring = LazyObject(
    lambda: types.FunctionType.__call__.__doc__, globals(), "_func_call_docstring"
)
_object_init_docstring = LazyObject(
    lambda: object.__init__.__doc__, globals(), "_object_init_docstring"
)
_builtin_type_docstrings = LazyObject(
    lambda: {
        t.__doc__ for t in (types.ModuleType, types.MethodType, types.FunctionType)
    },
    globals(),
    "_builtin_type_docstrings",
)

_builtin_func_type = LazyObject(lambda: type(all), globals(), "_builtin_func_type")
# Bound methods have the same type as builtin functions
_builtin_meth_type = LazyObject(
    lambda: type(str.upper), globals(), "_builtin_meth_type"
)

info_fields = LazyObject(
    lambda: [
        "type_name",
        "base_class",
        "string_form",
        "namespace",
        "length",
        "file",
        "definition",
        "docstring",
        "source",
        "init_definition",
        "class_docstring",
        "init_docstring",
        "call_def",
        "call_docstring",
        # These won't be printed but will be used to determine how to
        # format the object
        "ismagic",
        "isalias",
        "isclass",
        "argspec",
        "found",
        "name",
    ],
    globals(),
    "info_fields",
)


def object_info(**kw):
    """Make an object info dict with all fields present."""
    infodict = dict(itertools.zip_longest(info_fields, [None]))
    infodict.update(kw)
    return infodict


def get_encoding(obj):
    """Get encoding for python source file defining obj

    Returns None if obj is not defined in a sourcefile.
    """
    ofile = find_file(obj)
    # run contents of file through pager starting at line where the object
    # is defined, as long as the file isn't binary and is actually on the
    # filesystem.
    if ofile is None:
        return None
    elif ofile.endswith((".so", ".dll", ".pyd")):
        return None
    elif not os.path.isfile(ofile):
        return None
    else:
        # Print only text files, not extension binaries.  Note that
        # getsourcelines returns lineno with 1-offset and page() uses
        # 0-offset, so we must adjust.
        with io.open(ofile, "rb") as buf:  # Tweaked to use io.open for Python 2
            encoding, _ = detect_encoding(buf.readline)
        return encoding


def getdoc(obj):
    """Stable wrapper around inspect.getdoc.

    This can't crash because of attribute problems.

    It also attempts to call a getdoc() method on the given object.  This
    allows objects which provide their docstrings via non-standard mechanisms
    (like Pyro proxies) to still be inspected by ipython's ? system."""
    # Allow objects to offer customized documentation via a getdoc method:
    try:
        ds = obj.getdoc()
    except Exception:  # pylint:disable=broad-except
        pass
    else:
        # if we get extra info, we add it to the normal docstring.
        if isinstance(ds, str):
            return inspect.cleandoc(ds)

    try:
        docstr = inspect.getdoc(obj)
        encoding = get_encoding(obj)
        return cast_unicode(docstr, encoding=encoding)
    except Exception:  # pylint:disable=broad-except
        # Harden against an inspect failure, which can occur with
        # SWIG-wrapped extensions.
        raise


def getsource(obj, is_binary=False):
    """Wrapper around inspect.getsource.

    This can be modified by other projects to provide customized source
    extraction.

    Inputs:

    - obj: an object whose source code we will attempt to extract.

    Optional inputs:

    - is_binary: whether the object is known to come from a binary source.
      This implementation will skip returning any output for binary objects,
      but custom extractors may know how to meaningfully process them."""

    if is_binary:
        return None
    else:
        # get source if obj was decorated with @decorator
        if hasattr(obj, "__wrapped__"):
            obj = obj.__wrapped__
        try:
            src = inspect.getsource(obj)
        except TypeError:
            if hasattr(obj, "__class__"):
                src = inspect.getsource(obj.__class__)
        encoding = get_encoding(obj)
        return cast_unicode(src, encoding=encoding)


def is_simple_callable(obj):
    """True if obj is a function ()"""
    return (
        inspect.isfunction(obj)
        or inspect.ismethod(obj)
        or isinstance(obj, _builtin_func_type)
        or isinstance(obj, _builtin_meth_type)
    )


def getargspec(obj):
    """Wrapper around :func:`inspect.getfullargspec` on Python 3, and
    :func:inspect.getargspec` on Python 2.

    In addition to functions and methods, this can also handle objects with a
    ``__call__`` attribute.
    """
    if safe_hasattr(obj, "__call__") and not is_simple_callable(obj):
        obj = obj.__call__

    return inspect.getfullargspec(obj)


def format_argspec(argspec):
    """Format argspect, convenience wrapper around inspect's.

    This takes a dict instead of ordered arguments and calls
    inspect.format_argspec with the arguments in the necessary order.
    """
    return inspect.formatargspec(
        argspec["args"], argspec["varargs"], argspec["varkw"], argspec["defaults"]
    )


def call_tip(oinfo, format_call=True):
    """Extract call tip data from an oinfo dict.

    Parameters
    ----------
    oinfo : dict

    format_call : bool, optional
      If True, the call line is formatted and returned as a string.  If not, a
      tuple of (name, argspec) is returned.

    Returns
    -------
    call_info : None, str or (str, dict) tuple.
      When format_call is True, the whole call information is formatted as a
      single string.  Otherwise, the object's name and its argspec dict are
      returned.  If no call information is available, None is returned.

    docstring : str or None
      The most relevant docstring for calling purposes is returned, if
      available.  The priority is: call docstring for callable instances, then
      constructor docstring for classes, then main object's docstring otherwise
      (regular functions).
    """
    # Get call definition
    argspec = oinfo.get("argspec")
    if argspec is None:
        call_line = None
    else:
        # Callable objects will have 'self' as their first argument, prune
        # it out if it's there for clarity (since users do *not* pass an
        # extra first argument explicitly).
        try:
            has_self = argspec["args"][0] == "self"
        except (KeyError, IndexError):
            pass
        else:
            if has_self:
                argspec["args"] = argspec["args"][1:]

        call_line = oinfo["name"] + format_argspec(argspec)

    # Now get docstring.
    # The priority is: call docstring, constructor docstring, main one.
    doc = oinfo.get("call_docstring")
    if doc is None:
        doc = oinfo.get("init_docstring")
    if doc is None:
        doc = oinfo.get("docstring", "")

    return call_line, doc


def find_file(obj):
    """Find the absolute path to the file where an object was defined.

    This is essentially a robust wrapper around `inspect.getabsfile`.

    Returns None if no file can be found.

    Parameters
    ----------
    obj : any Python object

    Returns
    -------
    fname : str
      The absolute path to the file where the object was defined.
    """
    # get source if obj was decorated with @decorator
    if safe_hasattr(obj, "__wrapped__"):
        obj = obj.__wrapped__

    fname = None
    try:
        fname = inspect.getabsfile(obj)
    except TypeError:
        # For an instance, the file that matters is where its class was
        # declared.
        if hasattr(obj, "__class__"):
            try:
                fname = inspect.getabsfile(obj.__class__)
            except TypeError:
                # Can happen for builtins
                pass
    except:  # pylint:disable=bare-except
        pass
    return cast_unicode(fname)


def find_source_lines(obj):
    """Find the line number in a file where an object was defined.

    This is essentially a robust wrapper around `inspect.getsourcelines`.

    Returns None if no file can be found.

    Parameters
    ----------
    obj : any Python object

    Returns
    -------
    lineno : int
      The line number where the object definition starts.
    """
    # get source if obj was decorated with @decorator
    if safe_hasattr(obj, "__wrapped__"):
        obj = obj.__wrapped__

    try:
        try:
            lineno = inspect.getsourcelines(obj)[1]
        except TypeError:
            # For instances, try the class object like getsource() does
            if hasattr(obj, "__class__"):
                lineno = inspect.getsourcelines(obj.__class__)[1]
            else:
                lineno = None
    except:  # pylint:disable=bare-except
        return None

    return lineno


if PYTHON_VERSION_INFO < (3, 5, 0):
    FrameInfo = collections.namedtuple(
        "FrameInfo",
        ["frame", "filename", "lineno", "function", "code_context", "index"],
    )

    def getouterframes(frame, context=1):
        """Wrapper for getouterframes so that it acts like the Python v3.5 version."""
        return [FrameInfo(*f) for f in inspect.getouterframes(frame, context=context)]


else:
    getouterframes = inspect.getouterframes


class Inspector(object):
    """Inspects objects."""

    def __init__(self, str_detail_level=0):
        self.str_detail_level = str_detail_level

    def _getdef(self, obj, oname=""):
        """Return the call signature for any callable object.

        If any exception is generated, None is returned instead and the
        exception is suppressed.
        """
        try:
            hdef = oname + inspect.signature(*getargspec(obj))
            return cast_unicode(hdef)
        except:  # pylint:disable=bare-except
            return None

    def noinfo(self, msg, oname):
        """Generic message when no information is found."""
        print("No %s found" % msg, end=" ")
        if oname:
            print("for %s" % oname)
        else:
            print()

    def pdef(self, obj, oname=""):
        """Print the call signature for any callable object.

        If the object is a class, print the constructor information.
        """

        if not callable(obj):
            print("Object is not callable.")
            return

        header = ""

        if inspect.isclass(obj):
            header = self.__head("Class constructor information:\n")
            obj = obj.__init__

        output = self._getdef(obj, oname)
        if output is None:
            self.noinfo("definition header", oname)
        else:
            print(header, output, end=" ", file=sys.stdout)

    def pdoc(self, obj, oname=""):
        """Print the docstring for any object.

        Optional

        -formatter: a function to run the docstring through for specially
        formatted docstrings.
        """

        head = self.__head  # For convenience
        lines = []
        ds = getdoc(obj)
        if ds:
            lines.append(head("Class docstring:"))
            lines.append(indent(ds))
        if inspect.isclass(obj) and hasattr(obj, "__init__"):
            init_ds = getdoc(obj.__init__)
            if init_ds is not None:
                lines.append(head("Init docstring:"))
                lines.append(indent(init_ds))
        elif hasattr(obj, "__call__"):
            call_ds = getdoc(obj.__call__)
            if call_ds:
                lines.append(head("Call docstring:"))
                lines.append(indent(call_ds))

        if not lines:
            self.noinfo("documentation", oname)
        else:
            print("\n".join(lines))

    def psource(self, obj, oname=""):
        """Print the source code for an object."""
        # Flush the source cache because inspect can return out-of-date source
        linecache.checkcache()
        try:
            src = getsource(obj)
        except:  # pylint:disable=bare-except
            self.noinfo("source", oname)
        else:
            print(src)

    def pfile(self, obj, oname=""):
        """Show the whole file where an object was defined."""
        lineno = find_source_lines(obj)
        if lineno is None:
            self.noinfo("file", oname)
            return

        ofile = find_file(obj)
        # run contents of file through pager starting at line where the object
        # is defined, as long as the file isn't binary and is actually on the
        # filesystem.
        if ofile.endswith((".so", ".dll", ".pyd")):
            print("File %r is binary, not printing." % ofile)
        elif not os.path.isfile(ofile):
            print("File %r does not exist, not printing." % ofile)
        else:
            # Print only text files, not extension binaries.  Note that
            # getsourcelines returns lineno with 1-offset and page() uses
            # 0-offset, so we must adjust.
            o = read_py_file(ofile, skip_encoding_cookie=False)
            print(o, lineno - 1)

    def _format_fields_str(self, fields, title_width=0):
        """Formats a list of fields for display using color strings.

        Parameters
        ----------
        fields : list
          A list of 2-tuples: (field_title, field_content)
        title_width : int
          How many characters to pad titles to. Default to longest title.
        """
        out = []
        if title_width == 0:
            title_width = max(len(title) + 2 for title, _ in fields)
        for title, content in fields:
            title_len = len(title)
            title = "{BOLD_RED}" + title + ":{NO_COLOR}"
            if len(content.splitlines()) > 1:
                title += "\n"
            else:
                title += " ".ljust(title_width - title_len)
            out.append(cast_unicode(title) + cast_unicode(content))
        return format_color("\n".join(out) + "\n")

    def _format_fields_tokens(self, fields, title_width=0):
        """Formats a list of fields for display using color tokens from
        pygments.

        Parameters
        ----------
        fields : list
          A list of 2-tuples: (field_title, field_content)
        title_width : int
          How many characters to pad titles to. Default to longest title.
        """
        out = []
        if title_width == 0:
            title_width = max(len(title) + 2 for title, _ in fields)
        for title, content in fields:
            title_len = len(title)
            title = "{BOLD_RED}" + title + ":{NO_COLOR}"
            if not isinstance(content, str) or len(content.splitlines()) > 1:
                title += "\n"
            else:
                title += " ".ljust(title_width - title_len)
            out += partial_color_tokenize(title)
            if isinstance(content, str):
                out[-1] = (out[-1][0], out[-1][1] + content + "\n")
            else:
                out += content
                out[-1] = (out[-1][0], out[-1][1] + "\n")
        out[-1] = (out[-1][0], out[-1][1] + "\n")
        return out

    def _format_fields(self, fields, title_width=0):
        """Formats a list of fields for display using color tokens from
        pygments.

        Parameters
        ----------
        fields : list
          A list of 2-tuples: (field_title, field_content)
        title_width : int
          How many characters to pad titles to. Default to longest title.
        """
        if HAS_PYGMENTS:
            rtn = self._format_fields_tokens(fields, title_width=title_width)
        else:
            rtn = self._format_fields_str(fields, title_width=title_width)
        return rtn

    # The fields to be displayed by pinfo: (fancy_name, key_in_info_dict)
    pinfo_fields1 = [("Type", "type_name")]

    pinfo_fields2 = [("String form", "string_form")]

    pinfo_fields3 = [
        ("Length", "length"),
        ("File", "file"),
        ("Definition", "definition"),
    ]

    pinfo_fields_obj = [
        ("Class docstring", "class_docstring"),
        ("Init docstring", "init_docstring"),
        ("Call def", "call_def"),
        ("Call docstring", "call_docstring"),
    ]

    def pinfo(self, obj, oname="", info=None, detail_level=0):
        """Show detailed information about an object.

        Parameters
        ----------
        obj : object
        oname : str, optional
            name of the variable pointing to the object.
        info : dict, optional
            a structure with some information fields which may have been
            precomputed already.
        detail_level : int, optional
            if set to 1, more information is given.
        """
        info = self.info(obj, oname=oname, info=info, detail_level=detail_level)
        displayfields = []

        def add_fields(fields):
            for title, key in fields:
                field = info[key]
                if field is not None:
                    displayfields.append((title, field.rstrip()))

        add_fields(self.pinfo_fields1)
        add_fields(self.pinfo_fields2)

        # Namespace
        if info["namespace"] is not None and info["namespace"] != "Interactive":
            displayfields.append(("Namespace", info["namespace"].rstrip()))

        add_fields(self.pinfo_fields3)
        if info["isclass"] and info["init_definition"]:
            displayfields.append(("Init definition", info["init_definition"].rstrip()))

        # Source or docstring, depending on detail level and whether
        # source found.
        if detail_level > 0 and info["source"] is not None:
            displayfields.append(("Source", cast_unicode(info["source"])))
        elif info["docstring"] is not None:
            displayfields.append(("Docstring", info["docstring"]))

        # Constructor info for classes
        if info["isclass"]:
            if info["init_docstring"] is not None:
                displayfields.append(("Init docstring", info["init_docstring"]))

        # Info for objects:
        else:
            add_fields(self.pinfo_fields_obj)

        # Finally send to printer/pager:
        if displayfields:
            print_color(self._format_fields(displayfields))

    def info(self, obj, oname="", info=None, detail_level=0):
        """Compute a dict with detailed information about an object.

        Optional arguments:

        - oname: name of the variable pointing to the object.

        - info: a structure with some information fields which may have been
          precomputed already.

        - detail_level: if set to 1, more information is given.
        """
        obj_type = type(obj)
        if info is None:
            ismagic = 0
            isalias = 0
            ospace = ""
        else:
            ismagic = info.ismagic
            isalias = info.isalias
            ospace = info.namespace
        # Get docstring, special-casing aliases:
        if isalias:
            if not callable(obj):
                if len(obj) >= 2 and isinstance(obj[1], str):
                    ds = "Alias to the system command:\n  {0}".format(obj[1])
                else:  # pylint:disable=bare-except
                    ds = "Alias: " + str(obj)
            else:
                ds = "Alias to " + str(obj)
                if obj.__doc__:
                    ds += "\nDocstring:\n" + obj.__doc__
        else:
            ds = getdoc(obj)
            if ds is None:
                ds = "<no docstring>"

        # store output in a dict, we initialize it here and fill it as we go
        out = dict(name=oname, found=True, isalias=isalias, ismagic=ismagic)

        string_max = 200  # max size of strings to show (snipped if longer)
        shalf = int((string_max - 5) / 2)

        if ismagic:
            obj_type_name = "Magic function"
        elif isalias:
            obj_type_name = "System alias"
        else:
            obj_type_name = obj_type.__name__
        out["type_name"] = obj_type_name

        try:
            bclass = obj.__class__
            out["base_class"] = str(bclass)
        except:  # pylint:disable=bare-except
            pass

        # String form, but snip if too long in ? form (full in ??)
        if detail_level >= self.str_detail_level:
            try:
                ostr = str(obj)
                str_head = "string_form"
                if not detail_level and len(ostr) > string_max:
                    ostr = ostr[:shalf] + " <...> " + ostr[-shalf:]
                    ostr = ("\n" + " " * len(str_head.expandtabs())).join(
                        q.strip() for q in ostr.split("\n")
                    )
                out[str_head] = ostr
            except:  # pylint:disable=bare-except
                pass

        if ospace:
            out["namespace"] = ospace

        # Length (for strings and lists)
        try:
            out["length"] = str(len(obj))
        except:  # pylint:disable=bare-except
            pass

        # Filename where object was defined
        binary_file = False
        fname = find_file(obj)
        if fname is None:
            # if anything goes wrong, we don't want to show source, so it's as
            # if the file was binary
            binary_file = True
        else:
            if fname.endswith((".so", ".dll", ".pyd")):
                binary_file = True
            elif fname.endswith("<string>"):
                fname = "Dynamically generated function. " "No source code available."
            out["file"] = fname

        # Docstrings only in detail 0 mode, since source contains them (we
        # avoid repetitions).  If source fails, we add them back, see below.
        if ds and detail_level == 0:
            out["docstring"] = ds

        # Original source code for any callable
        if detail_level:
            # Flush the source cache because inspect can return out-of-date
            # source
            linecache.checkcache()
            source = None
            try:
                try:
                    source = getsource(obj, binary_file)
                except TypeError:
                    if hasattr(obj, "__class__"):
                        source = getsource(obj.__class__, binary_file)
                if source is not None:
                    source = source.rstrip()
                    if HAS_PYGMENTS:
                        lexer = pyghooks.XonshLexer()
                        source = list(pygments.lex(source, lexer=lexer))
                    out["source"] = source
            except Exception:  # pylint:disable=broad-except
                pass

            if ds and source is None:
                out["docstring"] = ds

        # Constructor docstring for classes
        if inspect.isclass(obj):
            out["isclass"] = True
            # reconstruct the function definition and print it:
            try:
                obj_init = obj.__init__
            except AttributeError:
                init_def = init_ds = None
            else:
                init_def = self._getdef(obj_init, oname)
                init_ds = getdoc(obj_init)
                # Skip Python's auto-generated docstrings
                if init_ds == _object_init_docstring:
                    init_ds = None

            if init_def or init_ds:
                if init_def:
                    out["init_definition"] = init_def
                if init_ds:
                    out["init_docstring"] = init_ds

        # and class docstring for instances:
        else:
            # reconstruct the function definition and print it:
            defln = self._getdef(obj, oname)
            if defln:
                out["definition"] = defln

            # First, check whether the instance docstring is identical to the
            # class one, and print it separately if they don't coincide.  In
            # most cases they will, but it's nice to print all the info for
            # objects which use instance-customized docstrings.
            if ds:
                try:
                    cls = getattr(obj, "__class__")
                except:  # pylint:disable=bare-except
                    class_ds = None
                else:
                    class_ds = getdoc(cls)
                # Skip Python's auto-generated docstrings
                if class_ds in _builtin_type_docstrings:
                    class_ds = None
                if class_ds and ds != class_ds:
                    out["class_docstring"] = class_ds

            # Next, try to show constructor docstrings
            try:
                init_ds = getdoc(obj.__init__)
                # Skip Python's auto-generated docstrings
                if init_ds == _object_init_docstring:
                    init_ds = None
            except AttributeError:
                init_ds = None
            if init_ds:
                out["init_docstring"] = init_ds

            # Call form docstring for callable instances
            if safe_hasattr(obj, "__call__") and not is_simple_callable(obj):
                call_def = self._getdef(obj.__call__, oname)
                if call_def:
                    call_def = call_def
                    # it may never be the case that call def and definition
                    # differ, but don't include the same signature twice
                    if call_def != out.get("definition"):
                        out["call_def"] = call_def
                call_ds = getdoc(obj.__call__)
                # Skip Python's auto-generated docstrings
                if call_ds == _func_call_docstring:
                    call_ds = None
                if call_ds:
                    out["call_docstring"] = call_ds

        # Compute the object's argspec as a callable.  The key is to decide
        # whether to pull it from the object itself, from its __init__ or
        # from its __call__ method.

        if inspect.isclass(obj):
            # Old-style classes need not have an __init__
            callable_obj = getattr(obj, "__init__", None)
        elif callable(obj):
            callable_obj = obj
        else:
            callable_obj = None

        if callable_obj:
            try:
                argspec = getargspec(callable_obj)
            except (TypeError, AttributeError):
                # For extensions/builtins we can't retrieve the argspec
                pass
            else:
                # named tuples' _asdict() method returns an OrderedDict, but we
                # we want a normal
                out["argspec"] = argspec_dict = dict(argspec._asdict())
                # We called this varkw before argspec became a named tuple.
                # With getfullargspec it's also called varkw.
                if "varkw" not in argspec_dict:
                    argspec_dict["varkw"] = argspec_dict.pop("keywords")

        return object_info(**out)
