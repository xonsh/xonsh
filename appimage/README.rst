This directory contains xonsh AppImage description.

The steps to build ``xonsh.AppImage`` for release:

1. We're using `rever <https://github.com/regro/rever>`_ to manage release.

2. The basic configuration for AppImage is in `xonsh/rever.xsh <https://github.com/xonsh/xonsh/blob/295e7f0582ff7399144939c4a56a85379417003d/rever.xsh#L49-L51>`_.

3. The actual code to build appimage is in `rever/activities/appimage.py <https://github.com/regro/rever/blob/master/rever/activities/appimage.xsh>`_.

See also: https://xon.sh/appimage.html
