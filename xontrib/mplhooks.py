"""Matplotlib hooks, for what its worth."""
import shutil

import numpy as np
import matplotlib
import matplotlib.pyplot as plt

from xonsh.tools import print_color, ON_WINDOWS

def figure_to_rgb_array(fig, width, height):
    """Converts figure to a numpy array of rgb values

    Forked from http://www.icare.univ-lille1.fr/wiki/index.php/How_to_convert_a_matplotlib_figure_to_a_numpy_array_or_a_PIL_image
    """
    w, h = fig.canvas.get_width_height()
    dpi = fig.get_dpi()
    fig.set_size_inches(width/dpi, height/dpi, forward=True)
    width, height = fig.canvas.get_width_height()
    ax = fig.gca()
    ax.set_xticklabels([])
    ax.set_yticklabels([])
    fig.set_tight_layout(True)
    fig.set_frameon(False)
    fig.set_facecolor('w')
    font_size = matplotlib.rcParams['font.size']
    matplotlib.rcParams.update({'font.size': 1})

    # Draw the renderer and get the RGB buffer from the figure
    fig.canvas.draw()
    buf = np.fromstring(fig.canvas.tostring_rgb(), dtype=np.uint8)
    buf.shape = (height, width, 3)

    # clean up and return
    matplotlib.rcParams.update({'font.size': font_size})
    return buf


def buf_to_color_str(buf):
    """Converts an RGB array to a xonsh color string."""
    space = ' '
    pix = '{{bg#{0:02x}{1:02x}{2:02x}}} '
    pixels = []
    for h in range(buf.shape[0]):
        last = None
        for w in range(buf.shape[1]):
            rgb = buf[h,w]
            if last is not None and (last == rgb).all():
                pixels.append(space)
            else:
                pixels.append(pix.format(*rgb))
            last = rgb
        pixels.append('{NO_COLOR}\n')
    pixels[-1] = pixels[-1].rstrip()
    return ''.join(pixels)


def show():
    fig = plt.gcf()
    w, h = shutil.get_terminal_size()
    if ON_WINDOWS:
        w -= 1  # @melund reports that win terminals are too thin
    h -= 1  # leave space for next prompt
    buf = figure_to_rgb_array(fig, w, h)
    s = buf_to_color_str(buf)
    print_color(s)
