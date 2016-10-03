from xontrib import mplhooks
import numpy as np
import matplotlib
import matplotlib.pyplot as plt


# some default settings that are temporarily changed by mpl
FONT_SIZE    = 22
FACE_COLOR   = (0.0, 1.0, 0.0, 1.0)
TIGHT_LAYOUT = False


def create_figure():
    """Simply create a figure with the default settings"""
    f, ax = plt.subplots()
    ax.plot(np.arange(20), np.arange(20))
    # set the figure parameters such that mpl will require changes
    f.set_tight_layout(TIGHT_LAYOUT)
    f.set_facecolor(FACE_COLOR)
    matplotlib.rcParams.update({'font.size': FONT_SIZE})
    return f


def test_mpl_preserve_font_size():
    """Make sure that matplotlib preserves font size settings"""
    f = create_figure()
    width, height = f.canvas.get_width_height()
    s = mplhooks.figure_to_rgb_array(f, 0.5*width, 0.5*height)
    exp = FONT_SIZE
    obs = matplotlib.rcParams['font.size']
    plt.close(f)
    assert exp == obs


def test_mpl_preserve_tight_layout():
    """Make sure that the figure preserves tight layout settings"""
    f = create_figure()
    width, height = f.canvas.get_width_height()
    s = mplhooks.figure_to_rgb_array(f, 0.5*width, 0.5*height)
    exp = TIGHT_LAYOUT
    obs = f.get_tight_layout()
    plt.close(f)
    assert exp == obs


def test_mpl_preserve_face_color():
    """Make sure that the figure preserves face color settings"""
    f = create_figure()
    width, height = f.canvas.get_width_height()
    s = mplhooks.figure_to_rgb_array(f, 0.5*width, 0.5*height)
    exp = FACE_COLOR
    obs = f.get_facecolor()
    plt.close(f)
    assert exp == obs


def test_mpl_preserve_width():
    """Make sure that the figure preserves width settings"""
    f = create_figure()
    width, height = f.canvas.get_width_height()
    s = mplhooks.figure_to_rgb_array(f, 0.5*width, 0.5*height)
    exp = width
    newwidth, newheight = f.canvas.get_width_height()
    obs = newwidth
    plt.close(f)
    assert exp == obs


def test_mpl_preserve_height():
    """Make sure that the figure preserves height settings"""
    f = create_figure()
    width, height = f.canvas.get_width_height()
    s = mplhooks.figure_to_rgb_array(f, 0.5*width, 0.5*height)
    exp = height
    newwidth, newheight = f.canvas.get_width_height()
    obs = newheight
    plt.close(f)
    assert exp == obs
