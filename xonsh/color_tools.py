"""Tools for color handling in xonsh.

This includes Convert values between RGB hex codes and xterm-256
color codes. Parts of this file were originally forked from Micah Elliott
http://MicahElliott.com Copyright (C) 2011 Micah Elliott. All rights reserved.
WTFPL http://sam.zoy.org/wtfpl/
"""
import re
import math

from xonsh.lazyasd import lazyobject, LazyObject


RE_BACKGROUND = LazyObject(lambda: re.compile('(BG#|BGHEX|BACKGROUND)'),
                           globals(), 'RE_BACKGROUND')


@lazyobject
def BASE_XONSH_COLORS():
    return {
        'BLACK': (0, 0, 0),
        'RED': (170, 0, 0),
        'GREEN': (0, 170, 0),
        'YELLOW': (170, 85, 0),
        'BLUE': (0, 0, 170),
        'PURPLE': (170, 0, 170),
        'CYAN': (0, 170, 170),
        'WHITE': (170, 170, 170),
        'INTENSE_BLACK': (85, 85, 85),
        'INTENSE_RED': (255, 85, 85),
        'INTENSE_GREEN': (85, 255, 85),
        'INTENSE_YELLOW': (255, 255, 85),
        'INTENSE_BLUE': (85, 85, 255),
        'INTENSE_PURPLE': (255, 85, 255),
        'INTENSE_CYAN': (85, 255, 255),
        'INTENSE_WHITE': (255, 255, 255),
    }


@lazyobject
def CLUT():
    """color look-up table"""
    return [
        #    8-bit, RGB hex
        # Primary 3-bit (8 colors). Unique representation!
        ('00', '000000'),
        ('01', '800000'),
        ('02', '008000'),
        ('03', '808000'),
        ('04', '000080'),
        ('05', '800080'),
        ('06', '008080'),
        ('07', 'c0c0c0'),
        # Equivalent "bright" versions of original 8 colors.
        ('08', '808080'),
        ('09', 'ff0000'),
        ('10', '00ff00'),
        ('11', 'ffff00'),
        ('12', '0000ff'),
        ('13', 'ff00ff'),
        ('14', '00ffff'),
        ('15', 'ffffff'),
        # Strictly ascending.
        ('16', '000000'),
        ('17', '00005f'),
        ('18', '000087'),
        ('19', '0000af'),
        ('20', '0000d7'),
        ('21', '0000ff'),
        ('22', '005f00'),
        ('23', '005f5f'),
        ('24', '005f87'),
        ('25', '005faf'),
        ('26', '005fd7'),
        ('27', '005fff'),
        ('28', '008700'),
        ('29', '00875f'),
        ('30', '008787'),
        ('31', '0087af'),
        ('32', '0087d7'),
        ('33', '0087ff'),
        ('34', '00af00'),
        ('35', '00af5f'),
        ('36', '00af87'),
        ('37', '00afaf'),
        ('38', '00afd7'),
        ('39', '00afff'),
        ('40', '00d700'),
        ('41', '00d75f'),
        ('42', '00d787'),
        ('43', '00d7af'),
        ('44', '00d7d7'),
        ('45', '00d7ff'),
        ('46', '00ff00'),
        ('47', '00ff5f'),
        ('48', '00ff87'),
        ('49', '00ffaf'),
        ('50', '00ffd7'),
        ('51', '00ffff'),
        ('52', '5f0000'),
        ('53', '5f005f'),
        ('54', '5f0087'),
        ('55', '5f00af'),
        ('56', '5f00d7'),
        ('57', '5f00ff'),
        ('58', '5f5f00'),
        ('59', '5f5f5f'),
        ('60', '5f5f87'),
        ('61', '5f5faf'),
        ('62', '5f5fd7'),
        ('63', '5f5fff'),
        ('64', '5f8700'),
        ('65', '5f875f'),
        ('66', '5f8787'),
        ('67', '5f87af'),
        ('68', '5f87d7'),
        ('69', '5f87ff'),
        ('70', '5faf00'),
        ('71', '5faf5f'),
        ('72', '5faf87'),
        ('73', '5fafaf'),
        ('74', '5fafd7'),
        ('75', '5fafff'),
        ('76', '5fd700'),
        ('77', '5fd75f'),
        ('78', '5fd787'),
        ('79', '5fd7af'),
        ('80', '5fd7d7'),
        ('81', '5fd7ff'),
        ('82', '5fff00'),
        ('83', '5fff5f'),
        ('84', '5fff87'),
        ('85', '5fffaf'),
        ('86', '5fffd7'),
        ('87', '5fffff'),
        ('88', '870000'),
        ('89', '87005f'),
        ('90', '870087'),
        ('91', '8700af'),
        ('92', '8700d7'),
        ('93', '8700ff'),
        ('94', '875f00'),
        ('95', '875f5f'),
        ('96', '875f87'),
        ('97', '875faf'),
        ('98', '875fd7'),
        ('99', '875fff'),
        ('100', '878700'),
        ('101', '87875f'),
        ('102', '878787'),
        ('103', '8787af'),
        ('104', '8787d7'),
        ('105', '8787ff'),
        ('106', '87af00'),
        ('107', '87af5f'),
        ('108', '87af87'),
        ('109', '87afaf'),
        ('110', '87afd7'),
        ('111', '87afff'),
        ('112', '87d700'),
        ('113', '87d75f'),
        ('114', '87d787'),
        ('115', '87d7af'),
        ('116', '87d7d7'),
        ('117', '87d7ff'),
        ('118', '87ff00'),
        ('119', '87ff5f'),
        ('120', '87ff87'),
        ('121', '87ffaf'),
        ('122', '87ffd7'),
        ('123', '87ffff'),
        ('124', 'af0000'),
        ('125', 'af005f'),
        ('126', 'af0087'),
        ('127', 'af00af'),
        ('128', 'af00d7'),
        ('129', 'af00ff'),
        ('130', 'af5f00'),
        ('131', 'af5f5f'),
        ('132', 'af5f87'),
        ('133', 'af5faf'),
        ('134', 'af5fd7'),
        ('135', 'af5fff'),
        ('136', 'af8700'),
        ('137', 'af875f'),
        ('138', 'af8787'),
        ('139', 'af87af'),
        ('140', 'af87d7'),
        ('141', 'af87ff'),
        ('142', 'afaf00'),
        ('143', 'afaf5f'),
        ('144', 'afaf87'),
        ('145', 'afafaf'),
        ('146', 'afafd7'),
        ('147', 'afafff'),
        ('148', 'afd700'),
        ('149', 'afd75f'),
        ('150', 'afd787'),
        ('151', 'afd7af'),
        ('152', 'afd7d7'),
        ('153', 'afd7ff'),
        ('154', 'afff00'),
        ('155', 'afff5f'),
        ('156', 'afff87'),
        ('157', 'afffaf'),
        ('158', 'afffd7'),
        ('159', 'afffff'),
        ('160', 'd70000'),
        ('161', 'd7005f'),
        ('162', 'd70087'),
        ('163', 'd700af'),
        ('164', 'd700d7'),
        ('165', 'd700ff'),
        ('166', 'd75f00'),
        ('167', 'd75f5f'),
        ('168', 'd75f87'),
        ('169', 'd75faf'),
        ('170', 'd75fd7'),
        ('171', 'd75fff'),
        ('172', 'd78700'),
        ('173', 'd7875f'),
        ('174', 'd78787'),
        ('175', 'd787af'),
        ('176', 'd787d7'),
        ('177', 'd787ff'),
        ('178', 'd7af00'),
        ('179', 'd7af5f'),
        ('180', 'd7af87'),
        ('181', 'd7afaf'),
        ('182', 'd7afd7'),
        ('183', 'd7afff'),
        ('184', 'd7d700'),
        ('185', 'd7d75f'),
        ('186', 'd7d787'),
        ('187', 'd7d7af'),
        ('188', 'd7d7d7'),
        ('189', 'd7d7ff'),
        ('190', 'd7ff00'),
        ('191', 'd7ff5f'),
        ('192', 'd7ff87'),
        ('193', 'd7ffaf'),
        ('194', 'd7ffd7'),
        ('195', 'd7ffff'),
        ('196', 'ff0000'),
        ('197', 'ff005f'),
        ('198', 'ff0087'),
        ('199', 'ff00af'),
        ('200', 'ff00d7'),
        ('201', 'ff00ff'),
        ('202', 'ff5f00'),
        ('203', 'ff5f5f'),
        ('204', 'ff5f87'),
        ('205', 'ff5faf'),
        ('206', 'ff5fd7'),
        ('207', 'ff5fff'),
        ('208', 'ff8700'),
        ('209', 'ff875f'),
        ('210', 'ff8787'),
        ('211', 'ff87af'),
        ('212', 'ff87d7'),
        ('213', 'ff87ff'),
        ('214', 'ffaf00'),
        ('215', 'ffaf5f'),
        ('216', 'ffaf87'),
        ('217', 'ffafaf'),
        ('218', 'ffafd7'),
        ('219', 'ffafff'),
        ('220', 'ffd700'),
        ('221', 'ffd75f'),
        ('222', 'ffd787'),
        ('223', 'ffd7af'),
        ('224', 'ffd7d7'),
        ('225', 'ffd7ff'),
        ('226', 'ffff00'),
        ('227', 'ffff5f'),
        ('228', 'ffff87'),
        ('229', 'ffffaf'),
        ('230', 'ffffd7'),
        ('231', 'ffffff'),
        # Gray-scale range.
        ('232', '080808'),
        ('233', '121212'),
        ('234', '1c1c1c'),
        ('235', '262626'),
        ('236', '303030'),
        ('237', '3a3a3a'),
        ('238', '444444'),
        ('239', '4e4e4e'),
        ('240', '585858'),
        ('241', '626262'),
        ('242', '6c6c6c'),
        ('243', '767676'),
        ('244', '808080'),
        ('245', '8a8a8a'),
        ('246', '949494'),
        ('247', '9e9e9e'),
        ('248', 'a8a8a8'),
        ('249', 'b2b2b2'),
        ('250', 'bcbcbc'),
        ('251', 'c6c6c6'),
        ('252', 'd0d0d0'),
        ('253', 'dadada'),
        ('254', 'e4e4e4'),
        ('255', 'eeeeee'),
        ]


def _str2hex(hexstr):
    return int(hexstr, 16)


def _strip_hash(rgb):
    # Strip leading `#` if exists.
    if rgb.startswith('#'):
        rgb = rgb.lstrip('#')
    return rgb


@lazyobject
def SHORT_TO_RGB():
    return dict(CLUT)


@lazyobject
def RGB_TO_SHORT():
    return {v: k for k, v in SHORT_TO_RGB.items()}


def short2rgb(short):
    return SHORT_TO_RGB[short]


def rgb_to_256(rgb):
    """Find the closest ANSI 256 approximation to the given RGB value.

        >>> rgb2short('123456')
        ('23', '005f5f')
        >>> rgb2short('ffffff')
        ('231', 'ffffff')
        >>> rgb2short('0DADD6') # vimeo logo
        ('38', '00afd7')

    Parameters
    ----------
    rgb : Hex code representing an RGB value, eg, 'abcdef'

    Returns
    -------
    String between 0 and 255, compatible with xterm.
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
    equiv = RGB_TO_SHORT[res]
    return equiv, res

rgb2short = rgb_to_256


@lazyobject
def RE_RGB3():
    return re.compile(r'(.)(.)(.)')


@lazyobject
def RE_RGB6():
    return re.compile(r'(..)(..)(..)')


def rgb_to_ints(rgb):
    if len(rgb) == 6:
        return tuple([int(h, 16) for h in RE_RGB6.split(rgb)[1:4]])
    else:
        return tuple([int(h*2, 16) for h in RE_RGB3.split(rgb)[1:4]])


def color_dist(x, y):
    return math.sqrt((x[0]-y[0])**2 + (x[1]-y[1])**2 + (x[2]-y[2])**2)


def find_closest_color(x, pallette):
    return min(sorted(pallette.keys())[::-1],
               key=lambda k: color_dist(x, pallette[k]))


def make_pallete(strings):
    """Makes a color pallete from a colection of strings."""
    pallette = {}
    for s in strings:
        while '#' in s:
            _, t = s.split('#', 1)
            t, _, s = t.partition(' ')
            pallette[t] = rgb_to_ints(t)
    return pallette
