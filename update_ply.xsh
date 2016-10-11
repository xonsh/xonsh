#!/usr/bin/env xonsh

# update the ply repo bundled with xonsh
git subtree pull --prefix xonsh/ply https://github.com/dabeaz/ply.git master --squash
