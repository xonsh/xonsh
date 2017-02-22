"""Tools for helping with ANSI color codes."""
import sys
import string
import warnings
import builtins

from xonsh.platform import HAS_PYGMENTS
from xonsh.lazyasd import LazyDict
from xonsh.color_tools import (RE_BACKGROUND, BASE_XONSH_COLORS, make_pallete,
                               find_closest_color, rgb2short, rgb_to_256)


def ansi_partial_color_format(template, style='default', cmap=None, hide=False):
    """Formats a template string but only with respect to the colors.
    Another template string is returned, with the color values filled in.

    Parameters
    ----------
    template : str
        The template string, potentially with color names.
    style : str, optional
        Sytle name to look up color map from.
    cmap : dict, optional
        A color map to use, this will prevent the color map from being
        looked up via the style name.
    hide : bool, optional
        Whether to wrap the color codes in the \\001 and \\002 escape
        codes, so that the color codes are not counted against line
        length.

    Returns
    -------
    A template string with the color values filled in.
    """
    try:
        return _ansi_partial_color_format_main(template, style=style, cmap=cmap, hide=hide)
    except Exception:
        return template


def _ansi_partial_color_format_main(template, style='default', cmap=None, hide=False):
    if cmap is not None:
        pass
    elif style in ANSI_STYLES:
        cmap = ANSI_STYLES[style]
    else:
        try:  # dynamically loading the style
            cmap = ansi_style_by_name(style)
        except Exception:
            msg = 'Could not find color style {0!r}, using default.'
            print(msg.format(style), file=sys.stderr)
            builtins.__xonsh_env__['XONSH_COLOR_STYLE'] = 'default'
            cmap = ANSI_STYLES['default']
    formatter = string.Formatter()
    esc = ('\001' if hide else '') + '\033['
    m = 'm' + ('\002' if hide else '')
    bopen = '{'
    bclose = '}'
    colon = ':'
    expl = '!'
    toks = []
    for literal, field, spec, conv in formatter.parse(template):
        toks.append(literal)
        if field is None:
            pass
        elif field in cmap:
            toks.extend([esc, cmap[field], m])
        elif '#' in field:
            field = field.lower()
            pre, _, post = field.partition('#')
            f_or_b = '38' if RE_BACKGROUND.search(pre) is None else '48'
            rgb, _, post = post.partition('_')
            c256, _ = rgb_to_256(rgb)
            color = f_or_b + ';5;' + c256
            mods = pre + '_' + post
            if 'underline' in mods:
                color = '4;' + color
            if 'bold' in mods:
                color = '1;' + color
            toks.extend([esc, color, m])
        elif field is not None:
            toks.append(bopen)
            toks.append(field)
            if conv is not None and len(conv) > 0:
                toks.append(expl)
                toks.append(conv)
            if spec is not None and len(spec) > 0:
                toks.append(colon)
                toks.append(spec)
            toks.append(bclose)
    return ''.join(toks)


def ansi_color_style_names():
    """Returns an iterable of all ANSI color style names."""
    return ANSI_STYLES.keys()


def ansi_color_style(style='default'):
    """Returns the current color map."""
    if style in ANSI_STYLES:
        cmap = ANSI_STYLES[style]
    else:
        msg = 'Could not find color style {0!r}, using default.'.format(style)
        warnings.warn(msg, RuntimeWarning)
        cmap = ANSI_STYLES['default']
    return cmap


def _ansi_expand_style(cmap):
    """Expands a style in order to more quickly make color map changes."""
    for key, val in list(cmap.items()):
        if key == 'NO_COLOR':
            continue
        elif len(val) == 0:
            cmap['BOLD_'+key] = '1'
            cmap['UNDERLINE_'+key] = '4'
            cmap['BOLD_UNDERLINE_'+key] = '1;4'
            cmap['BACKGROUND_'+key] = val
        else:
            cmap['BOLD_'+key] = '1;' + val
            cmap['UNDERLINE_'+key] = '4;' + val
            cmap['BOLD_UNDERLINE_'+key] = '1;4;' + val
            cmap['BACKGROUND_'+key] = val.replace('38', '48', 1)


def _bw_style():
    style = {
        'BLACK': '',
        'BLUE': '',
        'CYAN': '',
        'GREEN': '',
        'INTENSE_BLACK': '',
        'INTENSE_BLUE': '',
        'INTENSE_CYAN': '',
        'INTENSE_GREEN': '',
        'INTENSE_PURPLE': '',
        'INTENSE_RED': '',
        'INTENSE_WHITE': '',
        'INTENSE_YELLOW': '',
        'NO_COLOR': '0',
        'PURPLE': '',
        'RED': '',
        'WHITE': '',
        'YELLOW': '',
        }
    _ansi_expand_style(style)
    return style


def _default_style():
    style = {
        # Reset
        'NO_COLOR': '0',  # Text Reset
        # Regular Colors
        'BLACK': '0;30',  # BLACK
        'RED': '0;31',  # RED
        'GREEN': '0;32',  # GREEN
        'YELLOW': '0;33',  # YELLOW
        'BLUE': '0;34',  # BLUE
        'PURPLE': '0;35',  # PURPLE
        'CYAN': '0;36',  # CYAN
        'WHITE': '0;37',  # WHITE
        # Bold
        'BOLD_BLACK': '1;30',  # BLACK
        'BOLD_RED': '1;31',  # RED
        'BOLD_GREEN': '1;32',  # GREEN
        'BOLD_YELLOW': '1;33',  # YELLOW
        'BOLD_BLUE': '1;34',  # BLUE
        'BOLD_PURPLE': '1;35',  # PURPLE
        'BOLD_CYAN': '1;36',  # CYAN
        'BOLD_WHITE': '1;37',  # WHITE
        # Underline
        'UNDERLINE_BLACK': '4;30',  # BLACK
        'UNDERLINE_RED': '4;31',  # RED
        'UNDERLINE_GREEN': '4;32',  # GREEN
        'UNDERLINE_YELLOW': '4;33',  # YELLOW
        'UNDERLINE_BLUE': '4;34',  # BLUE
        'UNDERLINE_PURPLE': '4;35',  # PURPLE
        'UNDERLINE_CYAN': '4;36',  # CYAN
        'UNDERLINE_WHITE': '4;37',  # WHITE
        # Bold, Underline
        'BOLD_UNDERLINE_BLACK': '1;4;30',  # BLACK
        'BOLD_UNDERLINE_RED': '1;4;31',  # RED
        'BOLD_UNDERLINE_GREEN': '1;4;32',  # GREEN
        'BOLD_UNDERLINE_YELLOW': '1;4;33',  # YELLOW
        'BOLD_UNDERLINE_BLUE': '1;4;34',  # BLUE
        'BOLD_UNDERLINE_PURPLE': '1;4;35',  # PURPLE
        'BOLD_UNDERLINE_CYAN': '1;4;36',  # CYAN
        'BOLD_UNDERLINE_WHITE': '1;4;37',  # WHITE
        # Background
        'BACKGROUND_BLACK': '40',  # BLACK
        'BACKGROUND_RED': '41',  # RED
        'BACKGROUND_GREEN': '42',  # GREEN
        'BACKGROUND_YELLOW': '43',  # YELLOW
        'BACKGROUND_BLUE': '44',  # BLUE
        'BACKGROUND_PURPLE': '45',  # PURPLE
        'BACKGROUND_CYAN': '46',  # CYAN
        'BACKGROUND_WHITE': '47',  # WHITE
        # High Intensity
        'INTENSE_BLACK': '0;90',  # BLACK
        'INTENSE_RED': '0;91',  # RED
        'INTENSE_GREEN': '0;92',  # GREEN
        'INTENSE_YELLOW': '0;93',  # YELLOW
        'INTENSE_BLUE': '0;94',  # BLUE
        'INTENSE_PURPLE': '0;95',  # PURPLE
        'INTENSE_CYAN': '0;96',  # CYAN
        'INTENSE_WHITE': '0;97',  # WHITE
        # Bold High Intensity
        'BOLD_INTENSE_BLACK': '1;90',  # BLACK
        'BOLD_INTENSE_RED': '1;91',  # RED
        'BOLD_INTENSE_GREEN': '1;92',  # GREEN
        'BOLD_INTENSE_YELLOW': '1;93',  # YELLOW
        'BOLD_INTENSE_BLUE': '1;94',  # BLUE
        'BOLD_INTENSE_PURPLE': '1;95',  # PURPLE
        'BOLD_INTENSE_CYAN': '1;96',  # CYAN
        'BOLD_INTENSE_WHITE': '1;97',  # WHITE
        # Underline High Intensity
        'UNDERLINE_INTENSE_BLACK': '4;90',  # BLACK
        'UNDERLINE_INTENSE_RED': '4;91',  # RED
        'UNDERLINE_INTENSE_GREEN': '4;92',  # GREEN
        'UNDERLINE_INTENSE_YELLOW': '4;93',  # YELLOW
        'UNDERLINE_INTENSE_BLUE': '4;94',  # BLUE
        'UNDERLINE_INTENSE_PURPLE': '4;95',  # PURPLE
        'UNDERLINE_INTENSE_CYAN': '4;96',  # CYAN
        'UNDERLINE_INTENSE_WHITE': '4;97',  # WHITE
        # Bold Underline High Intensity
        'BOLD_UNDERLINE_INTENSE_BLACK': '1;4;90',  # BLACK
        'BOLD_UNDERLINE_INTENSE_RED': '1;4;91',  # RED
        'BOLD_UNDERLINE_INTENSE_GREEN': '1;4;92',  # GREEN
        'BOLD_UNDERLINE_INTENSE_YELLOW': '1;4;93',  # YELLOW
        'BOLD_UNDERLINE_INTENSE_BLUE': '1;4;94',  # BLUE
        'BOLD_UNDERLINE_INTENSE_PURPLE': '1;4;95',  # PURPLE
        'BOLD_UNDERLINE_INTENSE_CYAN': '1;4;96',  # CYAN
        'BOLD_UNDERLINE_INTENSE_WHITE': '1;4;97',  # WHITE
        # High Intensity backgrounds
        'BACKGROUND_INTENSE_BLACK': '0;100',  # BLACK
        'BACKGROUND_INTENSE_RED': '0;101',  # RED
        'BACKGROUND_INTENSE_GREEN': '0;102',  # GREEN
        'BACKGROUND_INTENSE_YELLOW': '0;103',  # YELLOW
        'BACKGROUND_INTENSE_BLUE': '0;104',  # BLUE
        'BACKGROUND_INTENSE_PURPLE': '0;105',  # PURPLE
        'BACKGROUND_INTENSE_CYAN': '0;106',  # CYAN
        'BACKGROUND_INTENSE_WHITE': '0;107',  # WHITE
        }
    return style


def _monokai_style():
    style = {
        'NO_COLOR': '0',
        'BLACK': '38;5;16',
        'BLUE': '38;5;63',
        'CYAN': '38;5;81',
        'GREEN': '38;5;40',
        'PURPLE': '38;5;89',
        'RED': '38;5;124',
        'WHITE': '38;5;188',
        'YELLOW': '38;5;184',
        'INTENSE_BLACK': '38;5;59',
        'INTENSE_BLUE': '38;5;20',
        'INTENSE_CYAN': '38;5;44',
        'INTENSE_GREEN': '38;5;148',
        'INTENSE_PURPLE': '38;5;141',
        'INTENSE_RED': '38;5;197',
        'INTENSE_WHITE': '38;5;15',
        'INTENSE_YELLOW': '38;5;186',
        }
    _ansi_expand_style(style)
    return style


####################################
# Auto-generated below this line   #
####################################

def _algol_style():
    style = {
        'BLACK': '38;5;59',
        'BLUE': '38;5;59',
        'CYAN': '38;5;59',
        'GREEN': '38;5;59',
        'INTENSE_BLACK': '38;5;59',
        'INTENSE_BLUE': '38;5;102',
        'INTENSE_CYAN': '38;5;102',
        'INTENSE_GREEN': '38;5;102',
        'INTENSE_PURPLE': '38;5;102',
        'INTENSE_RED': '38;5;09',
        'INTENSE_WHITE': '38;5;102',
        'INTENSE_YELLOW': '38;5;102',
        'NO_COLOR': '0',
        'PURPLE': '38;5;59',
        'RED': '38;5;09',
        'WHITE': '38;5;102',
        'YELLOW': '38;5;09',
        }
    _ansi_expand_style(style)
    return style


def _algol_nu_style():
    style = {
        'BLACK': '38;5;59',
        'BLUE': '38;5;59',
        'CYAN': '38;5;59',
        'GREEN': '38;5;59',
        'INTENSE_BLACK': '38;5;59',
        'INTENSE_BLUE': '38;5;102',
        'INTENSE_CYAN': '38;5;102',
        'INTENSE_GREEN': '38;5;102',
        'INTENSE_PURPLE': '38;5;102',
        'INTENSE_RED': '38;5;09',
        'INTENSE_WHITE': '38;5;102',
        'INTENSE_YELLOW': '38;5;102',
        'NO_COLOR': '0',
        'PURPLE': '38;5;59',
        'RED': '38;5;09',
        'WHITE': '38;5;102',
        'YELLOW': '38;5;09',
        }
    _ansi_expand_style(style)
    return style


def _autumn_style():
    style = {
        'BLACK': '38;5;18',
        'BLUE': '38;5;19',
        'CYAN': '38;5;37',
        'GREEN': '38;5;34',
        'INTENSE_BLACK': '38;5;59',
        'INTENSE_BLUE': '38;5;33',
        'INTENSE_CYAN': '38;5;33',
        'INTENSE_GREEN': '38;5;64',
        'INTENSE_PURPLE': '38;5;217',
        'INTENSE_RED': '38;5;130',
        'INTENSE_WHITE': '38;5;145',
        'INTENSE_YELLOW': '38;5;217',
        'NO_COLOR': '0',
        'PURPLE': '38;5;90',
        'RED': '38;5;124',
        'WHITE': '38;5;145',
        'YELLOW': '38;5;130',
    }
    _ansi_expand_style(style)
    return style


def _borland_style():
    style = {
        'BLACK': '38;5;16',
        'BLUE': '38;5;18',
        'CYAN': '38;5;30',
        'GREEN': '38;5;28',
        'INTENSE_BLACK': '38;5;59',
        'INTENSE_BLUE': '38;5;21',
        'INTENSE_CYAN': '38;5;194',
        'INTENSE_GREEN': '38;5;102',
        'INTENSE_PURPLE': '38;5;188',
        'INTENSE_RED': '38;5;09',
        'INTENSE_WHITE': '38;5;224',
        'INTENSE_YELLOW': '38;5;188',
        'NO_COLOR': '0',
        'PURPLE': '38;5;90',
        'RED': '38;5;124',
        'WHITE': '38;5;145',
        'YELLOW': '38;5;124',
        }
    _ansi_expand_style(style)
    return style


def _colorful_style():
    style = {
        'BLACK': '38;5;16',
        'BLUE': '38;5;20',
        'CYAN': '38;5;31',
        'GREEN': '38;5;34',
        'INTENSE_BLACK': '38;5;59',
        'INTENSE_BLUE': '38;5;61',
        'INTENSE_CYAN': '38;5;145',
        'INTENSE_GREEN': '38;5;102',
        'INTENSE_PURPLE': '38;5;217',
        'INTENSE_RED': '38;5;166',
        'INTENSE_WHITE': '38;5;15',
        'INTENSE_YELLOW': '38;5;217',
        'NO_COLOR': '0',
        'PURPLE': '38;5;90',
        'RED': '38;5;124',
        'WHITE': '38;5;145',
        'YELLOW': '38;5;130',
    }
    _ansi_expand_style(style)
    return style


def _emacs_style():
    style = {
        'BLACK': '38;5;28',
        'BLUE': '38;5;18',
        'CYAN': '38;5;26',
        'GREEN': '38;5;34',
        'INTENSE_BLACK': '38;5;59',
        'INTENSE_BLUE': '38;5;26',
        'INTENSE_CYAN': '38;5;145',
        'INTENSE_GREEN': '38;5;34',
        'INTENSE_PURPLE': '38;5;129',
        'INTENSE_RED': '38;5;167',
        'INTENSE_WHITE': '38;5;145',
        'INTENSE_YELLOW': '38;5;145',
        'NO_COLOR': '0',
        'PURPLE': '38;5;90',
        'RED': '38;5;124',
        'WHITE': '38;5;145',
        'YELLOW': '38;5;130',
    }
    _ansi_expand_style(style)
    return style


def _friendly_style():
    style = {
        'BLACK': '38;5;22',
        'BLUE': '38;5;18',
        'CYAN': '38;5;31',
        'GREEN': '38;5;34',
        'INTENSE_BLACK': '38;5;59',
        'INTENSE_BLUE': '38;5;74',
        'INTENSE_CYAN': '38;5;74',
        'INTENSE_GREEN': '38;5;71',
        'INTENSE_PURPLE': '38;5;134',
        'INTENSE_RED': '38;5;167',
        'INTENSE_WHITE': '38;5;15',
        'INTENSE_YELLOW': '38;5;145',
        'NO_COLOR': '0',
        'PURPLE': '38;5;90',
        'RED': '38;5;124',
        'WHITE': '38;5;145',
        'YELLOW': '38;5;166',
    }
    _ansi_expand_style(style)
    return style


def _fruity_style():
    style = {
        'BLACK': '38;5;16',
        'BLUE': '38;5;32',
        'CYAN': '38;5;32',
        'GREEN': '38;5;28',
        'INTENSE_BLACK': '38;5;59',
        'INTENSE_BLUE': '38;5;33',
        'INTENSE_CYAN': '38;5;33',
        'INTENSE_GREEN': '38;5;102',
        'INTENSE_PURPLE': '38;5;198',
        'INTENSE_RED': '38;5;202',
        'INTENSE_WHITE': '38;5;15',
        'INTENSE_YELLOW': '38;5;187',
        'NO_COLOR': '0',
        'PURPLE': '38;5;198',
        'RED': '38;5;09',
        'WHITE': '38;5;187',
        'YELLOW': '38;5;202',
        }
    _ansi_expand_style(style)
    return style


def _igor_style():
    style = {
        'BLACK': '38;5;34',
        'BLUE': '38;5;21',
        'CYAN': '38;5;30',
        'GREEN': '38;5;34',
        'INTENSE_BLACK': '38;5;30',
        'INTENSE_BLUE': '38;5;21',
        'INTENSE_CYAN': '38;5;30',
        'INTENSE_GREEN': '38;5;34',
        'INTENSE_PURPLE': '38;5;163',
        'INTENSE_RED': '38;5;166',
        'INTENSE_WHITE': '38;5;163',
        'INTENSE_YELLOW': '38;5;166',
        'NO_COLOR': '0',
        'PURPLE': '38;5;163',
        'RED': '38;5;166',
        'WHITE': '38;5;163',
        'YELLOW': '38;5;166',
        }
    _ansi_expand_style(style)
    return style


def _lovelace_style():
    style = {
        'BLACK': '38;5;59',
        'BLUE': '38;5;25',
        'CYAN': '38;5;29',
        'GREEN': '38;5;65',
        'INTENSE_BLACK': '38;5;59',
        'INTENSE_BLUE': '38;5;25',
        'INTENSE_CYAN': '38;5;102',
        'INTENSE_GREEN': '38;5;29',
        'INTENSE_PURPLE': '38;5;133',
        'INTENSE_RED': '38;5;131',
        'INTENSE_WHITE': '38;5;102',
        'INTENSE_YELLOW': '38;5;136',
        'NO_COLOR': '0',
        'PURPLE': '38;5;133',
        'RED': '38;5;124',
        'WHITE': '38;5;102',
        'YELLOW': '38;5;130',
        }
    _ansi_expand_style(style)
    return style


def _manni_style():
    style = {
        'BLACK': '38;5;16',
        'BLUE': '38;5;18',
        'CYAN': '38;5;30',
        'GREEN': '38;5;40',
        'INTENSE_BLACK': '38;5;59',
        'INTENSE_BLUE': '38;5;105',
        'INTENSE_CYAN': '38;5;45',
        'INTENSE_GREEN': '38;5;113',
        'INTENSE_PURPLE': '38;5;165',
        'INTENSE_RED': '38;5;202',
        'INTENSE_WHITE': '38;5;224',
        'INTENSE_YELLOW': '38;5;221',
        'NO_COLOR': '0',
        'PURPLE': '38;5;165',
        'RED': '38;5;124',
        'WHITE': '38;5;145',
        'YELLOW': '38;5;166',
        }
    _ansi_expand_style(style)
    return style


def _murphy_style():
    style = {
        'BLACK': '38;5;16',
        'BLUE': '38;5;18',
        'CYAN': '38;5;31',
        'GREEN': '38;5;34',
        'INTENSE_BLACK': '38;5;59',
        'INTENSE_BLUE': '38;5;63',
        'INTENSE_CYAN': '38;5;86',
        'INTENSE_GREEN': '38;5;86',
        'INTENSE_PURPLE': '38;5;213',
        'INTENSE_RED': '38;5;209',
        'INTENSE_WHITE': '38;5;15',
        'INTENSE_YELLOW': '38;5;222',
        'NO_COLOR': '0',
        'PURPLE': '38;5;90',
        'RED': '38;5;124',
        'WHITE': '38;5;145',
        'YELLOW': '38;5;166',
        }
    _ansi_expand_style(style)
    return style


def _native_style():
    style = {
        'BLACK': '38;5;52',
        'BLUE': '38;5;67',
        'CYAN': '38;5;31',
        'GREEN': '38;5;64',
        'INTENSE_BLACK': '38;5;59',
        'INTENSE_BLUE': '38;5;68',
        'INTENSE_CYAN': '38;5;87',
        'INTENSE_GREEN': '38;5;70',
        'INTENSE_PURPLE': '38;5;188',
        'INTENSE_RED': '38;5;160',
        'INTENSE_WHITE': '38;5;15',
        'INTENSE_YELLOW': '38;5;214',
        'NO_COLOR': '0',
        'PURPLE': '38;5;59',
        'RED': '38;5;124',
        'WHITE': '38;5;145',
        'YELLOW': '38;5;124',
        }
    _ansi_expand_style(style)
    return style


def _paraiso_dark_style():
    style = {
        'BLACK': '38;5;95',
        'BLUE': '38;5;97',
        'CYAN': '38;5;39',
        'GREEN': '38;5;72',
        'INTENSE_BLACK': '38;5;95',
        'INTENSE_BLUE': '38;5;97',
        'INTENSE_CYAN': '38;5;79',
        'INTENSE_GREEN': '38;5;72',
        'INTENSE_PURPLE': '38;5;188',
        'INTENSE_RED': '38;5;203',
        'INTENSE_WHITE': '38;5;188',
        'INTENSE_YELLOW': '38;5;220',
        'NO_COLOR': '0',
        'PURPLE': '38;5;97',
        'RED': '38;5;203',
        'WHITE': '38;5;79',
        'YELLOW': '38;5;214',
        }
    _ansi_expand_style(style)
    return style


def _paraiso_light_style():
    style = {
        'BLACK': '38;5;16',
        'BLUE': '38;5;16',
        'CYAN': '38;5;39',
        'GREEN': '38;5;72',
        'INTENSE_BLACK': '38;5;16',
        'INTENSE_BLUE': '38;5;97',
        'INTENSE_CYAN': '38;5;79',
        'INTENSE_GREEN': '38;5;72',
        'INTENSE_PURPLE': '38;5;97',
        'INTENSE_RED': '38;5;203',
        'INTENSE_WHITE': '38;5;79',
        'INTENSE_YELLOW': '38;5;220',
        'NO_COLOR': '0',
        'PURPLE': '38;5;97',
        'RED': '38;5;16',
        'WHITE': '38;5;102',
        'YELLOW': '38;5;214',
        }
    _ansi_expand_style(style)
    return style


def _pastie_style():
    style = {
        'BLACK': '38;5;16',
        'BLUE': '38;5;20',
        'CYAN': '38;5;25',
        'GREEN': '38;5;28',
        'INTENSE_BLACK': '38;5;59',
        'INTENSE_BLUE': '38;5;61',
        'INTENSE_CYAN': '38;5;194',
        'INTENSE_GREEN': '38;5;34',
        'INTENSE_PURPLE': '38;5;188',
        'INTENSE_RED': '38;5;172',
        'INTENSE_WHITE': '38;5;15',
        'INTENSE_YELLOW': '38;5;188',
        'NO_COLOR': '0',
        'PURPLE': '38;5;125',
        'RED': '38;5;124',
        'WHITE': '38;5;145',
        'YELLOW': '38;5;130',
        }
    _ansi_expand_style(style)
    return style


def _perldoc_style():
    style = {
        'BLACK': '38;5;18',
        'BLUE': '38;5;18',
        'CYAN': '38;5;31',
        'GREEN': '38;5;34',
        'INTENSE_BLACK': '38;5;59',
        'INTENSE_BLUE': '38;5;134',
        'INTENSE_CYAN': '38;5;145',
        'INTENSE_GREEN': '38;5;28',
        'INTENSE_PURPLE': '38;5;134',
        'INTENSE_RED': '38;5;167',
        'INTENSE_WHITE': '38;5;188',
        'INTENSE_YELLOW': '38;5;188',
        'NO_COLOR': '0',
        'PURPLE': '38;5;90',
        'RED': '38;5;124',
        'WHITE': '38;5;145',
        'YELLOW': '38;5;166',
        }
    _ansi_expand_style(style)
    return style


def _rrt_style():
    style = {
        'BLACK': '38;5;09',
        'BLUE': '38;5;117',
        'CYAN': '38;5;117',
        'GREEN': '38;5;46',
        'INTENSE_BLACK': '38;5;117',
        'INTENSE_BLUE': '38;5;117',
        'INTENSE_CYAN': '38;5;122',
        'INTENSE_GREEN': '38;5;46',
        'INTENSE_PURPLE': '38;5;213',
        'INTENSE_RED': '38;5;09',
        'INTENSE_WHITE': '38;5;188',
        'INTENSE_YELLOW': '38;5;222',
        'NO_COLOR': '0',
        'PURPLE': '38;5;213',
        'RED': '38;5;09',
        'WHITE': '38;5;117',
        'YELLOW': '38;5;09',
        }
    _ansi_expand_style(style)
    return style


def _tango_style():
    style = {
        'BLACK': '38;5;16',
        'BLUE': '38;5;20',
        'CYAN': '38;5;61',
        'GREEN': '38;5;34',
        'INTENSE_BLACK': '38;5;24',
        'INTENSE_BLUE': '38;5;62',
        'INTENSE_CYAN': '38;5;15',
        'INTENSE_GREEN': '38;5;64',
        'INTENSE_PURPLE': '38;5;15',
        'INTENSE_RED': '38;5;09',
        'INTENSE_WHITE': '38;5;15',
        'INTENSE_YELLOW': '38;5;178',
        'NO_COLOR': '0',
        'PURPLE': '38;5;90',
        'RED': '38;5;124',
        'WHITE': '38;5;15',
        'YELLOW': '38;5;94',
        }
    _ansi_expand_style(style)
    return style


def _trac_style():
    style = {
        'BLACK': '38;5;16',
        'BLUE': '38;5;18',
        'CYAN': '38;5;30',
        'GREEN': '38;5;100',
        'INTENSE_BLACK': '38;5;59',
        'INTENSE_BLUE': '38;5;60',
        'INTENSE_CYAN': '38;5;194',
        'INTENSE_GREEN': '38;5;102',
        'INTENSE_PURPLE': '38;5;188',
        'INTENSE_RED': '38;5;137',
        'INTENSE_WHITE': '38;5;224',
        'INTENSE_YELLOW': '38;5;188',
        'NO_COLOR': '0',
        'PURPLE': '38;5;90',
        'RED': '38;5;124',
        'WHITE': '38;5;145',
        'YELLOW': '38;5;100',
        }
    _ansi_expand_style(style)
    return style


def _vim_style():
    style = {
        'BLACK': '38;5;18',
        'BLUE': '38;5;18',
        'CYAN': '38;5;44',
        'GREEN': '38;5;40',
        'INTENSE_BLACK': '38;5;60',
        'INTENSE_BLUE': '38;5;68',
        'INTENSE_CYAN': '38;5;44',
        'INTENSE_GREEN': '38;5;40',
        'INTENSE_PURPLE': '38;5;164',
        'INTENSE_RED': '38;5;09',
        'INTENSE_WHITE': '38;5;188',
        'INTENSE_YELLOW': '38;5;184',
        'NO_COLOR': '0',
        'PURPLE': '38;5;164',
        'RED': '38;5;160',
        'WHITE': '38;5;188',
        'YELLOW': '38;5;160',
        }
    _ansi_expand_style(style)
    return style


def _vs_style():
    style = {
        'BLACK': '38;5;28',
        'BLUE': '38;5;21',
        'CYAN': '38;5;31',
        'GREEN': '38;5;28',
        'INTENSE_BLACK': '38;5;31',
        'INTENSE_BLUE': '38;5;31',
        'INTENSE_CYAN': '38;5;31',
        'INTENSE_GREEN': '38;5;31',
        'INTENSE_PURPLE': '38;5;31',
        'INTENSE_RED': '38;5;09',
        'INTENSE_WHITE': '38;5;31',
        'INTENSE_YELLOW': '38;5;31',
        'NO_COLOR': '0',
        'PURPLE': '38;5;124',
        'RED': '38;5;124',
        'WHITE': '38;5;31',
        'YELLOW': '38;5;124',
        }
    _ansi_expand_style(style)
    return style


def _xcode_style():
    style = {
        'BLACK': '38;5;16',
        'BLUE': '38;5;20',
        'CYAN': '38;5;60',
        'GREEN': '38;5;28',
        'INTENSE_BLACK': '38;5;60',
        'INTENSE_BLUE': '38;5;20',
        'INTENSE_CYAN': '38;5;60',
        'INTENSE_GREEN': '38;5;60',
        'INTENSE_PURPLE': '38;5;126',
        'INTENSE_RED': '38;5;160',
        'INTENSE_WHITE': '38;5;60',
        'INTENSE_YELLOW': '38;5;94',
        'NO_COLOR': '0',
        'PURPLE': '38;5;126',
        'RED': '38;5;160',
        'WHITE': '38;5;60',
        'YELLOW': '38;5;94',
        }
    _ansi_expand_style(style)
    return style


ANSI_STYLES = LazyDict({
    'algol': _algol_style,
    'algol_nu': _algol_nu_style,
    'autumn': _autumn_style,
    'borland': _borland_style,
    'bw': _bw_style,
    'colorful': _colorful_style,
    'default': _default_style,
    'emacs': _emacs_style,
    'friendly': _friendly_style,
    'fruity': _fruity_style,
    'igor': _igor_style,
    'lovelace': _lovelace_style,
    'manni': _manni_style,
    'monokai': _monokai_style,
    'murphy': _murphy_style,
    'native': _native_style,
    'paraiso-dark': _paraiso_dark_style,
    'paraiso-light': _paraiso_light_style,
    'pastie': _pastie_style,
    'perldoc': _perldoc_style,
    'rrt': _rrt_style,
    'tango': _tango_style,
    'trac': _trac_style,
    'vim': _vim_style,
    'vs': _vs_style,
    'xcode': _xcode_style,
    }, globals(), 'ANSI_STYLES')

del (_algol_style, _algol_nu_style, _autumn_style, _borland_style, _bw_style,
     _colorful_style, _default_style, _emacs_style, _friendly_style,
     _fruity_style, _igor_style, _lovelace_style, _manni_style,
     _monokai_style, _murphy_style, _native_style, _paraiso_dark_style,
     _paraiso_light_style, _pastie_style, _perldoc_style,  _rrt_style,
     _tango_style, _trac_style, _vim_style, _vs_style, _xcode_style)


#
# Dynamically generated styles
#
def make_ansi_style(pallette):
    """Makes an ANSI color style from a color pallette"""
    style = {'NO_COLOR': '0'}
    for name, t in BASE_XONSH_COLORS.items():
        closest = find_closest_color(t, pallette)
        if len(closest) == 3:
            closest = ''.join([a*2 for a in closest])
        short = rgb2short(closest)[0]
        style[name] = '38;5;' + short
        style['BOLD_'+name] = '1;38;5;' + short
        style['UNDERLINE_'+name] = '4;38;5;' + short
        style['BOLD_UNDERLINE_'+name] = '1;4;38;5;' + short
        style['BACKGROUND_'+name] = '48;5;' + short
    return style


def ansi_style_by_name(name):
    """Gets or makes an ANSI color style by name. If the styles does not
    exist, it will look for a style using the pygments name.
    """
    if name in ANSI_STYLES:
        return ANSI_STYLES[name]
    elif not HAS_PYGMENTS:
        raise KeyError('could not find style {0!r}'.format(name))
    from pygments.styles import get_style_by_name
    pstyle = get_style_by_name(name)
    pallette = make_pallete(pstyle.styles.values())
    astyle = make_ansi_style(pallette)
    ANSI_STYLES[name] = astyle
    return astyle
