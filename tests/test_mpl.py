import pytest

# make sure to skip these tests entirely if numpy/matplotlib are not present
np = pytest.importorskip("numpy")
matplotlib = pytest.importorskip("matplotlib")
plt = pytest.importorskip("matplotlib.pyplot")

from xontrib import mplhooks

skip_if_mpl2 = pytest.mark.skipif(
    matplotlib.__version__.startswith("2"), reason="Bug in matplotlib v2"
)

# some default settings that are temporarily changed by mpl
FONT_SIZE = 22
FACE_COLOR = (0.0, 1.0, 0.0, 1.0)
DPI = 80


def create_figure():
    """Simply create a figure with the default settings"""
    f, ax = plt.subplots()
    ax.plot(np.arange(20), np.arange(20))
    # set the figure parameters such that mpl will require changes
    f.set_facecolor(FACE_COLOR)
    f.dpi = DPI
    matplotlib.rcParams.update({"font.size": FONT_SIZE})
    return f


@skip_if_mpl2
def test_mpl_preserve_font_size():
    """Make sure that matplotlib preserves font size settings"""
    f = create_figure()
    width, height = f.canvas.get_width_height()
    print(width, height)
    s = mplhooks.figure_to_tight_array(f, 0.5 * width, 0.5 * height, True)
    exp = FONT_SIZE
    obs = matplotlib.rcParams["font.size"]
    plt.close(f)
    assert exp == obs


@skip_if_mpl2
def test_mpl_preserve_face_color():
    """Make sure that the figure preserves face color settings"""
    f = create_figure()
    width, height = f.canvas.get_width_height()
    s = mplhooks.figure_to_tight_array(f, 0.5 * width, 0.5 * height, True)
    exp = FACE_COLOR
    obs = f.get_facecolor()
    plt.close(f)
    assert exp == obs


@skip_if_mpl2
def test_mpl_preserve_width():
    """Make sure that the figure preserves width settings"""
    f = create_figure()
    width, height = f.canvas.get_width_height()
    s = mplhooks.figure_to_tight_array(f, 0.5 * width, 0.5 * height, True)
    exp = width
    newwidth, newheight = f.canvas.get_width_height()
    obs = newwidth
    plt.close(f)
    assert exp == obs


@skip_if_mpl2
def test_mpl_preserve_height():
    """Make sure that the figure preserves height settings"""
    f = create_figure()
    width, height = f.canvas.get_width_height()
    s = mplhooks.figure_to_tight_array(f, 0.5 * width, 0.5 * height, True)
    exp = height
    newwidth, newheight = f.canvas.get_width_height()
    obs = newheight
    plt.close(f)
    assert exp == obs


def test_mpl_preserve_dpi():
    """Make sure that the figure preserves height settings"""
    f = create_figure()
    width, height = f.canvas.get_width_height()
    s = mplhooks.figure_to_tight_array(f, 0.5 * width, 0.5 * height, False)
    exp = DPI
    obs = f.dpi
    plt.close(f)
    assert exp == obs


@skip_if_mpl2
def test_mpl_preserve_image_tight():
    """Make sure that the figure preserves height settings"""
    f = create_figure()
    exp = mplhooks.figure_to_rgb_array(f)
    width, height = f.canvas.get_width_height()
    s = mplhooks.figure_to_tight_array(f, 0.5 * width, 0.5 * height, True)
    obs = mplhooks.figure_to_rgb_array(f)
    plt.close(f)
    assert np.all(exp == obs)


def test_mpl_preserve_standard():
    """Make sure that the figure preserves height settings"""
    f = create_figure()
    exp = mplhooks.figure_to_rgb_array(f)
    width, height = f.canvas.get_width_height()
    s = mplhooks.figure_to_tight_array(f, 0.5 * width, 0.5 * height, False)
    obs = mplhooks.figure_to_rgb_array(f)
    plt.close(f)
    assert np.all(exp == obs)
