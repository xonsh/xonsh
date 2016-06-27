__version__ = '0.4.2'

# amalgamate exclude jupyter_kernel parser_table parser_test_table pyghooks
# amalgamate exclude winutils wizard
import os as _os
if _os.getenv('XONSH_DEBUG', ''):
    pass
else:
    import sys as _sys
    try:
        from xonsh import __amalgam__
        bg_pkg_resources = __amalgam__
        _sys.modules['xonsh.bg_pkg_resources'] = __amalgam__
        completer = __amalgam__
        _sys.modules['xonsh.completer'] = __amalgam__
        lazyasd = __amalgam__
        _sys.modules['xonsh.lazyasd'] = __amalgam__
        lazyjson = __amalgam__
        _sys.modules['xonsh.lazyjson'] = __amalgam__
        pretty = __amalgam__
        _sys.modules['xonsh.pretty'] = __amalgam__
        timings = __amalgam__
        _sys.modules['xonsh.timings'] = __amalgam__
        ansi_colors = __amalgam__
        _sys.modules['xonsh.ansi_colors'] = __amalgam__
        codecache = __amalgam__
        _sys.modules['xonsh.codecache'] = __amalgam__
        openpy = __amalgam__
        _sys.modules['xonsh.openpy'] = __amalgam__
        platform = __amalgam__
        _sys.modules['xonsh.platform'] = __amalgam__
        teepty = __amalgam__
        _sys.modules['xonsh.teepty'] = __amalgam__
        jobs = __amalgam__
        _sys.modules['xonsh.jobs'] = __amalgam__
        parser = __amalgam__
        _sys.modules['xonsh.parser'] = __amalgam__
        tokenize = __amalgam__
        _sys.modules['xonsh.tokenize'] = __amalgam__
        tools = __amalgam__
        _sys.modules['xonsh.tools'] = __amalgam__
        vox = __amalgam__
        _sys.modules['xonsh.vox'] = __amalgam__
        ast = __amalgam__
        _sys.modules['xonsh.ast'] = __amalgam__
        contexts = __amalgam__
        _sys.modules['xonsh.contexts'] = __amalgam__
        diff_history = __amalgam__
        _sys.modules['xonsh.diff_history'] = __amalgam__
        dirstack = __amalgam__
        _sys.modules['xonsh.dirstack'] = __amalgam__
        foreign_shells = __amalgam__
        _sys.modules['xonsh.foreign_shells'] = __amalgam__
        inspectors = __amalgam__
        _sys.modules['xonsh.inspectors'] = __amalgam__
        lexer = __amalgam__
        _sys.modules['xonsh.lexer'] = __amalgam__
        proc = __amalgam__
        _sys.modules['xonsh.proc'] = __amalgam__
        xontribs = __amalgam__
        _sys.modules['xonsh.xontribs'] = __amalgam__
        commands_cache = __amalgam__
        _sys.modules['xonsh.commands_cache'] = __amalgam__
        environ = __amalgam__
        _sys.modules['xonsh.environ'] = __amalgam__
        history = __amalgam__
        _sys.modules['xonsh.history'] = __amalgam__
        base_shell = __amalgam__
        _sys.modules['xonsh.base_shell'] = __amalgam__
        replay = __amalgam__
        _sys.modules['xonsh.replay'] = __amalgam__
        tracer = __amalgam__
        _sys.modules['xonsh.tracer'] = __amalgam__
        xonfig = __amalgam__
        _sys.modules['xonsh.xonfig'] = __amalgam__
        aliases = __amalgam__
        _sys.modules['xonsh.aliases'] = __amalgam__
        readline_shell = __amalgam__
        _sys.modules['xonsh.readline_shell'] = __amalgam__
        built_ins = __amalgam__
        _sys.modules['xonsh.built_ins'] = __amalgam__
        execer = __amalgam__
        _sys.modules['xonsh.execer'] = __amalgam__
        imphooks = __amalgam__
        _sys.modules['xonsh.imphooks'] = __amalgam__
        shell = __amalgam__
        _sys.modules['xonsh.shell'] = __amalgam__
        main = __amalgam__
        _sys.modules['xonsh.main'] = __amalgam__
        del __amalgam__
    except ImportError:
        pass
    del _sys
del _os
# amalgamate end
