# must come before ptk / pygments imports
from xonsh.lazyasd import load_module_in_background

load_module_in_background('pkg_resources', debug='XONSH_DEBUG',
                          replacements={'pygments.plugin': 'pkg_resources'})
