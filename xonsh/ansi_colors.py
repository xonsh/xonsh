"""Tools for helping with ANSI color codes."""
import re
import string
import warnings

from xonsh.lazyasd import LazyObject, LazyDict


RE_BACKGROUND = LazyObject(lambda: re.compile('(bg|bg#|bghex|background)'),
                           globals(), 'RE_BACKGROUND')


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
        msg = 'Could not find color style {0!r}, using default.'.format(style)
        warnings.warn(msg, RuntimeWarning)
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


RGB_256 = LazyObject(lambda: {
    '000000': '16',
    '00005f': '17',
    '000080': '04',
    '000087': '18',
    '0000af': '19',
    '0000d7': '20',
    '0000ff': '21',
    '005f00': '22',
    '005f5f': '23',
    '005f87': '24',
    '005faf': '25',
    '005fd7': '26',
    '005fff': '27',
    '008000': '02',
    '008080': '06',
    '008700': '28',
    '00875f': '29',
    '008787': '30',
    '0087af': '31',
    '0087d7': '32',
    '0087ff': '33',
    '00af00': '34',
    '00af5f': '35',
    '00af87': '36',
    '00afaf': '37',
    '00afd7': '38',
    '00afff': '39',
    '00d700': '40',
    '00d75f': '41',
    '00d787': '42',
    '00d7af': '43',
    '00d7d7': '44',
    '00d7ff': '45',
    '00ff00': '46',
    '00ff5f': '47',
    '00ff87': '48',
    '00ffaf': '49',
    '00ffd7': '50',
    '00ffff': '51',
    '080808': '232',
    '121212': '233',
    '1c1c1c': '234',
    '262626': '235',
    '303030': '236',
    '3a3a3a': '237',
    '444444': '238',
    '4e4e4e': '239',
    '585858': '240',
    '5f0000': '52',
    '5f005f': '53',
    '5f0087': '54',
    '5f00af': '55',
    '5f00d7': '56',
    '5f00ff': '57',
    '5f5f00': '58',
    '5f5f5f': '59',
    '5f5f87': '60',
    '5f5faf': '61',
    '5f5fd7': '62',
    '5f5fff': '63',
    '5f8700': '64',
    '5f875f': '65',
    '5f8787': '66',
    '5f87af': '67',
    '5f87d7': '68',
    '5f87ff': '69',
    '5faf00': '70',
    '5faf5f': '71',
    '5faf87': '72',
    '5fafaf': '73',
    '5fafd7': '74',
    '5fafff': '75',
    '5fd700': '76',
    '5fd75f': '77',
    '5fd787': '78',
    '5fd7af': '79',
    '5fd7d7': '80',
    '5fd7ff': '81',
    '5fff00': '82',
    '5fff5f': '83',
    '5fff87': '84',
    '5fffaf': '85',
    '5fffd7': '86',
    '5fffff': '87',
    '626262': '241',
    '6c6c6c': '242',
    '767676': '243',
    '800000': '01',
    '800080': '05',
    '808000': '03',
    '808080': '244',
    '870000': '88',
    '87005f': '89',
    '870087': '90',
    '8700af': '91',
    '8700d7': '92',
    '8700ff': '93',
    '875f00': '94',
    '875f5f': '95',
    '875f87': '96',
    '875faf': '97',
    '875fd7': '98',
    '875fff': '99',
    '878700': '100',
    '87875f': '101',
    '878787': '102',
    '8787af': '103',
    '8787d7': '104',
    '8787ff': '105',
    '87af00': '106',
    '87af5f': '107',
    '87af87': '108',
    '87afaf': '109',
    '87afd7': '110',
    '87afff': '111',
    '87d700': '112',
    '87d75f': '113',
    '87d787': '114',
    '87d7af': '115',
    '87d7d7': '116',
    '87d7ff': '117',
    '87ff00': '118',
    '87ff5f': '119',
    '87ff87': '120',
    '87ffaf': '121',
    '87ffd7': '122',
    '87ffff': '123',
    '8a8a8a': '245',
    '949494': '246',
    '9e9e9e': '247',
    'a8a8a8': '248',
    'af0000': '124',
    'af005f': '125',
    'af0087': '126',
    'af00af': '127',
    'af00d7': '128',
    'af00ff': '129',
    'af5f00': '130',
    'af5f5f': '131',
    'af5f87': '132',
    'af5faf': '133',
    'af5fd7': '134',
    'af5fff': '135',
    'af8700': '136',
    'af875f': '137',
    'af8787': '138',
    'af87af': '139',
    'af87d7': '140',
    'af87ff': '141',
    'afaf00': '142',
    'afaf5f': '143',
    'afaf87': '144',
    'afafaf': '145',
    'afafd7': '146',
    'afafff': '147',
    'afd700': '148',
    'afd75f': '149',
    'afd787': '150',
    'afd7af': '151',
    'afd7d7': '152',
    'afd7ff': '153',
    'afff00': '154',
    'afff5f': '155',
    'afff87': '156',
    'afffaf': '157',
    'afffd7': '158',
    'afffff': '159',
    'b2b2b2': '249',
    'bcbcbc': '250',
    'c0c0c0': '07',
    'c6c6c6': '251',
    'd0d0d0': '252',
    'd70000': '160',
    'd7005f': '161',
    'd70087': '162',
    'd700af': '163',
    'd700d7': '164',
    'd700ff': '165',
    'd75f00': '166',
    'd75f5f': '167',
    'd75f87': '168',
    'd75faf': '169',
    'd75fd7': '170',
    'd75fff': '171',
    'd78700': '172',
    'd7875f': '173',
    'd78787': '174',
    'd787af': '175',
    'd787d7': '176',
    'd787ff': '177',
    'd7af00': '178',
    'd7af5f': '179',
    'd7af87': '180',
    'd7afaf': '181',
    'd7afd7': '182',
    'd7afff': '183',
    'd7d700': '184',
    'd7d75f': '185',
    'd7d787': '186',
    'd7d7af': '187',
    'd7d7d7': '188',
    'd7d7ff': '189',
    'd7ff00': '190',
    'd7ff5f': '191',
    'd7ff87': '192',
    'd7ffaf': '193',
    'd7ffd7': '194',
    'd7ffff': '195',
    'dadada': '253',
    'e4e4e4': '254',
    'eeeeee': '255',
    'ff0000': '196',
    'ff005f': '197',
    'ff0087': '198',
    'ff00af': '199',
    'ff00d7': '200',
    'ff00ff': '201',
    'ff5f00': '202',
    'ff5f5f': '203',
    'ff5f87': '204',
    'ff5faf': '205',
    'ff5fd7': '206',
    'ff5fff': '207',
    'ff8700': '208',
    'ff875f': '209',
    'ff8787': '210',
    'ff87af': '211',
    'ff87d7': '212',
    'ff87ff': '213',
    'ffaf00': '214',
    'ffaf5f': '215',
    'ffaf87': '216',
    'ffafaf': '217',
    'ffafd7': '218',
    'ffafff': '219',
    'ffd700': '220',
    'ffd75f': '221',
    'ffd787': '222',
    'ffd7af': '223',
    'ffd7d7': '224',
    'ffd7ff': '225',
    'ffff00': '226',
    'ffff5f': '227',
    'ffff87': '228',
    'ffffaf': '229',
    'ffffd7': '230',
    'ffffff': '231',
    }, globals(), 'RGB_256')

RE_RGB3 = LazyObject(lambda: re.compile(r'(.)(.)(.)'), globals(), 'RE_RGB3')
RE_RGB6 = LazyObject(lambda: re.compile(r'(..)(..)(..)'), globals(), 'RE_RGB6')


def rgb_to_ints(rgb):
    """Converts an RGB string into a tuple of ints."""
    if len(rgb) == 6:
        return tuple([int(h, 16) for h in RE_RGB6.split(rgb)[1:4]])
    else:
        return tuple([int(h*2, 16) for h in RE_RGB3.split(rgb)[1:4]])


def rgb_to_256(rgb):
    """Find the closest ANSI 256 approximation to the given RGB value.
    Thanks to Micah Elliott (http://MicahElliott.com) for colortrans.py
    """
    rgb = rgb.lstrip('#')
    if len(rgb) == 0:
        return '0', '000000'
    incs = (0x00, 0x5f, 0x87, 0xaf, 0xd7, 0xff)
    # Break 6-char RGB code into 3 integer vals.
    parts = rgb_to_ints(rgb)
    res = []
    for part in parts:
        i = 0
        while i < len(incs)-1:
            s, b = incs[i], incs[i+1]  # smaller, bigger
            if s <= part <= b:
                s1 = abs(s - part)
                b1 = abs(b - part)
                if s1 < b1:
                    closest = s
                else:
                    closest = b
                res.append(closest)
                break
            i += 1
    res = ''.join([('%02.x' % i) for i in res])
    equiv = RGB_256[res]
    return equiv, res


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
