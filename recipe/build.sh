#!/bin/bash
$PYTHON setup.py install --conda

cp ${RECIPE_DIR}/xonsh_shortcut.json ${PREFIX}/Menu/xonsh_shortcut.json
cp ${RECIPE_DIR}/xonsh.ico ${PREFIX}/Menu/xonsh.ico
