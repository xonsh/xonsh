from xonsh.built_ins import XSH

env = XSH.env
# adjust some paths
env["PATH"].append("/home/snail/sandbox/bin")
env["LD_LIBRARY_PATH"] = ["/home/snail/.local/lib", "/home/snail/miniconda3/lib"]

# alias to quit AwesomeWM from the terminal
@XSH.aliases.register("qa")
def _quit_awesome(args, stdin=None):
    print("awesome python code")

# setting aliases as list are faster since they don't involve parser.
XSH.aliases["gc"] = ["git", "commit"]

# some customization options, see https://xon.sh/envvars.html for details
env["MULTILINE_PROMPT"] = "`·.,¸,.·*¯`·.,¸,.·*¯"
env["XONSH_SHOW_TRACEBACK"] = True
env["XONSH_STORE_STDOUT"] = True
env["XONSH_HISTORY_MATCH_ANYWHERE"] = True
env["COMPLETIONS_CONFIRM"] = True
env["XONSH_AUTOPAIR"] = True
