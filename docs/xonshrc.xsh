# adjust some paths
$PATH.append('/home/snail/sandbox/bin')
$LD_LIBRARY_PATH = ['/home/snail/.local/lib', '/home/snail/miniconda3/lib', '']

# alias to quit AwesomeWM from the terminal
@aliases.register('qa')
def _quit_awesome(args, stdin=None):
    lines = $(ps ux | grep "gnome-session --session=awesome").splitlines()
    pids = [l.split()[1] for l in lines]
    for pid in pids:
        kill @(pid)

# some customization options, see https://xon.sh/envvars.html for details
$MULTILINE_PROMPT = '`·.,¸,.·*¯`·.,¸,.·*¯'
$XONSH_SHOW_TRACEBACK = True
$XONSH_STORE_STDOUT = True
$XONSH_HISTORY_MATCH_ANYWHERE = True
$COMPLETIONS_CONFIRM = True
$XONSH_AUTOPAIR = True
