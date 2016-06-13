__version__ = '0.3.4'

# amalgamate exclude jupyter_kernel parser_table parser_test_table pyghooks winutils
import sys as _sys
try:
    from xonsh import __amalgam__
    _sys.modules['xonsh.ansi_colors'] = __amalgam__
    _sys.modules['xonsh.codecache'] = __amalgam__
    _sys.modules['xonsh.completer'] = __amalgam__
    _sys.modules['xonsh.lazyjson'] = __amalgam__
    _sys.modules['xonsh.openpy'] = __amalgam__
    _sys.modules['xonsh.platform'] = __amalgam__
    _sys.modules['xonsh.pretty'] = __amalgam__
    _sys.modules['xonsh.teepty'] = __amalgam__
    _sys.modules['xonsh.timings'] = __amalgam__
    _sys.modules['xonsh.jobs'] = __amalgam__
    _sys.modules['xonsh.parser'] = __amalgam__
    _sys.modules['xonsh.tokenize'] = __amalgam__
    _sys.modules['xonsh.tools'] = __amalgam__
    _sys.modules['xonsh.vox'] = __amalgam__
    _sys.modules['xonsh.ast'] = __amalgam__
    _sys.modules['xonsh.contexts'] = __amalgam__
    _sys.modules['xonsh.diff_history'] = __amalgam__
    _sys.modules['xonsh.dirstack'] = __amalgam__
    _sys.modules['xonsh.foreign_shells'] = __amalgam__
    _sys.modules['xonsh.inspectors'] = __amalgam__
    _sys.modules['xonsh.lexer'] = __amalgam__
    _sys.modules['xonsh.proc'] = __amalgam__
    _sys.modules['xonsh.wizard'] = __amalgam__
    _sys.modules['xonsh.xontribs'] = __amalgam__
    _sys.modules['xonsh.environ'] = __amalgam__
    _sys.modules['xonsh.history'] = __amalgam__
    _sys.modules['xonsh.base_shell'] = __amalgam__
    _sys.modules['xonsh.replay'] = __amalgam__
    _sys.modules['xonsh.tracer'] = __amalgam__
    _sys.modules['xonsh.xonfig'] = __amalgam__
    _sys.modules['xonsh.aliases'] = __amalgam__
    _sys.modules['xonsh.readline_shell'] = __amalgam__
    _sys.modules['xonsh.built_ins'] = __amalgam__
    _sys.modules['xonsh.execer'] = __amalgam__
    _sys.modules['xonsh.imphooks'] = __amalgam__
    _sys.modules['xonsh.shell'] = __amalgam__
    _sys.modules['xonsh.main'] = __amalgam__
    del __amalgam__
except ImportError:
    pass
del _sys
# amalgamate end