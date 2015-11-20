#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys
from xonsh.tools import TERM_COLORS, print_color

if __name__ == "__main__":
    colors = ["BLACK", "RED", "GREEN", "YELLOW", "BLUE", "PURPLE", "CYAN",
              "WHITE"]
    bgrounds = [None, "BACKGROUND", "BACKGROUND_INTENSE"]
    styles = [None, "UNDERLINE", "BOLD", "BOLD_INTENSE"]

    try:
        color_of_interest = sys.argv[1].upper()
    except IndexError:
        color_of_interest = None
    try:
        text = sys.argv[2]
    except IndexError:
        text = "Hello World!"

    all_tags = set()
    output = ""
    for c in colors:
        for st in styles:
            fg_tag = ("{%(st)s_%(c)s}" if st else "{%(c)s}") % locals()

            for bg in bgrounds:
                for bgc in colors:
                    bg_tag = "{%(bg)s_%(bgc)s}" % locals() if bg else ""

                    tag = "%(fg_tag)s%(bg_tag)s" % locals()
                    if (tag not in all_tags) and (not color_of_interest or
                                                  color_of_interest in tag):
                        all_tags.add(tag)
                        desc = tag.replace("}{", "+")\
                                     .replace("{", "")\
                                     .replace("}", "")
                        output += "%(tag)s%(text)s{NO_COLOR}\t\t%(desc)s\n"\
                                  % locals()

            output += '\n'
        output += '\n'

    print_color(output.format(**TERM_COLORS))
