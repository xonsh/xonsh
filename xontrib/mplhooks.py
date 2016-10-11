"""Matplotlib hooks, for what its worth."""
from io import BytesIO
import shutil

import numpy as np
import matplotlib
import matplotlib.pyplot as plt

from xonsh.tools import print_color, ON_WINDOWS

try:
    # Use iterm2_tools as an indicator for the iterm2 terminal emulator
    from iterm2_tools.images import display_image_bytes
except ImportError:
    _use_iterm = False
else:
    _use_iterm = True

XONTRIB_MPL_MINIMAL_DEFAULT = True


def _get_buffer(fig, **kwargs):
    b = BytesIO()
    fig.savefig(b, **kwargs)
    b.seek(0)
    return b


def figure_to_rgb_array(fig, shape=None):
    """Converts figure to a numpy array

    Parameters
    ----------
    fig : matplotlib.figure.Figure
        the figure to be plotted
    shape : iterable
        with the shape of the output array. by default this attempts to use the
        pixel height and width of the figure


    Returns
    -------
    array : np.ndarray
        An RGBA array of the image represented by the figure.

    Note: the method will throw an exception if the given shape is wrong.
    """
    array = np.frombuffer(_get_buffer(fig, dpi=fig.dpi, format='raw').read(), dtype='uint8')
    if shape is None:
        w, h = fig.canvas.get_width_height()
        shape = (h, w, 4)
    return array.reshape(*shape)


def figure_to_tight_array(fig, width, height, minimal=True):
    """Converts figure to a numpy array of rgb values of tight value

    Parameters
    ----------
    fig : matplotlib.figure.Figure
        the figure to be plotted
    width : int
        pixel width of the final array
    height : int
        pixel height of the final array
    minimal : bool
        whether or not to reduce the output array to minimized margins/whitespace
        text is also eliminated

    Returns
    -------
    array : np.ndarray
        An RGBA array of the image represented by the figure.
    """
    # store the properties of the figure in order to restore it
    w, h = fig.canvas.get_width_height()
    dpi_fig = fig.dpi
    if minimal:
        # perform reversible operations to produce an optimally tight layout
        dpi = dpi_fig
        subplotpars = {
                k: getattr(fig.subplotpars, k)
                for k in ['wspace', 'hspace', 'bottom', 'top', 'left', 'right']
                }

        # set the figure dimensions to the terminal size
        fig.set_size_inches(width/dpi, height/dpi, forward=True)
        width, height = fig.canvas.get_width_height()

        # remove all space between subplots
        fig.subplots_adjust(wspace=0, hspace=0)
        # move all subplots to take the entirety of space in the figure
        # leave only one line for top and bottom
        fig.subplots_adjust(bottom=1/height, top=1-1/height, left=0, right=1)

        # redeuce font size in order to reduce text impact on the image
        font_size = matplotlib.rcParams['font.size']
        matplotlib.rcParams.update({'font.size': 0})
    else:
        dpi = min([width * fig.dpi // w, height * fig.dpi // h])
        fig.dpi = dpi
        width, height = fig.canvas.get_width_height()

    # Draw the renderer and get the RGB buffer from the figure
    array = figure_to_rgb_array(fig, shape=(height, width, 4))

    if minimal:
        # cleanup after tight layout
        # clean up rcParams
        matplotlib.rcParams.update({'font.size': font_size})

        # reset the axis positions and figure dimensions
        fig.set_size_inches(w/dpi, h/dpi, forward=True)
        fig.subplots_adjust(**subplotpars)
    else:
        fig.dpi = dpi_fig

    return array


def buf_to_color_str(buf):
    """Converts an RGB array to a xonsh color string."""
    space = ' '
    pix = '{{bg#{0:02x}{1:02x}{2:02x}}} '
    pixels = []
    for h in range(buf.shape[0]):
        last = None
        for w in range(buf.shape[1]):
            rgb = buf[h, w]
            if last is not None and (last == rgb).all():
                pixels.append(space)
            else:
                pixels.append(pix.format(*rgb))
            last = rgb
        pixels.append('{NO_COLOR}\n')
    pixels[-1] = pixels[-1].rstrip()
    return ''.join(pixels)


def display_figure_with_iterm2(fig):
    """Displays a matplotlib figure using iterm2 inline-image escape sequence.

    Parameters
    ----------
    fig : matplotlib.figure.Figure
        the figure to be plotted
    """
    print(display_image_bytes(_get_buffer(fig, format='png', dpi=fig.dpi).read()))


def show():
    '''Run the mpl display sequence by printing the most recent figure to console'''
    try:
        minimal = __xonsh_env__['XONTRIB_MPL_MINIMAL']
    except KeyError:
        minimal = XONTRIB_MPL_MINIMAL_DEFAULT
    fig = plt.gcf()
    if _use_iterm:
        display_figure_with_iterm2(fig)
    else:
        # Display the image using terminal characters to fit into the console
        w, h = shutil.get_terminal_size()
        if ON_WINDOWS:
            w -= 1  # @melund reports that win terminals are too thin
        h -= 1  # leave space for next prompt
        buf = figure_to_tight_array(fig, w, h, minimal)
        s = buf_to_color_str(buf)
        print_color(s)
