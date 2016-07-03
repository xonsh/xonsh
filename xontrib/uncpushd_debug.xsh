xontrib uncpushd
import xontrib.uncpushd
aliases['xpushd'] = xontrib.uncpushd.unc_pushd
aliases['xpopd'] = xontrib.uncpushd.unc_popd

import os
os.getcwd()

net use z: /delete

net use

print('before push', $PWD)
xpushd \\jessie-pc\users\public
print('after push', $PWD)

dirs

print('listing directory')

ls -l

print('popping')
xpopd

print('after pop', $PWD)

