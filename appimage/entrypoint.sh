#! /bin/bash
exec {{ python-executable }} -u "${APPDIR}/opt/python{{ python-version }}/bin/xonsh" "$@"
