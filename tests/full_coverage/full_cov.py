import os
import re
import shutil
import subprocess as sp
from pprint import pprint


PATH = (
    os.path.join(os.path.abspath(os.path.dirname(__file__)), "bin")
    + os.pathsep
    + os.environ["PATH"]
)

def run_xonsh(
    cmd,
    stdin=sp.PIPE,
    stdin_cmd=None,
    stdout=sp.PIPE,
    stderr=sp.STDOUT,
    single_command=False,
    interactive=False,
    path=None,
    add_args: list = None,
    timeout=20,
):
    env = dict(os.environ)
    if path is None:
        env["PATH"] = PATH
    else:
        env["PATH"] = path
    env["XONSH_DEBUG"] = "0"  # was "1"
    env["XONSH_SHOW_TRACEBACK"] = "1"
    env["RAISE_SUBPROC_ERROR"] = "0"
    env["FOREIGN_ALIASES_SUPPRESS_SKIP_MESSAGE"] = "1"
    env["PROMPT"] = ""
    xonsh = shutil.which("xonsh", path=PATH)
    args = [xonsh, "--no-rc"]
    if interactive:
        args.append("-i")
    if single_command:
        args += ["-c", cmd]
        input = None
    else:
        input = cmd
    if add_args:
        args += add_args

    proc = sp.Popen(
        args,
        env=env,
        stdin=stdin,
        stdout=stdout,
        stderr=stderr,
        universal_newlines=True,
    )

    if stdin_cmd:
        proc.stdin.write(stdin_cmd)
        proc.stdin.flush()

    try:
        out, err = proc.communicate(input=input, timeout=timeout)
    except sp.TimeoutExpired:
        proc.kill()
        raise
    return out, err, proc.returncode



class CaseGen:
    snippets = {
        "sp_atom": {
            "capturable": "echo CCAAPP",
            # ls with colors
        },

        "sp_pipe": {
            "alone": "{body}",
            "tail": "echo 1PIPE1 | {body}",
            "middle": "echo 1PIPE1 | {body} | head",
        },

        "opers": {
            "stdout": "echo $({body})",
            "object": "echo @(!({body}).out)",
            "hiddenobject": "![{body}]",
            "uncaptured": "$[{body}]",
        },

        "aliases": {
            "inline": "aliases['a'] = '{body}'\n"
                      "a\n",
            "exec": "aliases['a'] = 'echo @($({body}))'\n"
                      "a\n"
            # exec alias
        },

        "calliases": {
            "default": "@aliases.register('a')\n"
                       "def _a():\n"
                       "    {body}\n"
                       "a\n",
            "unthreadable": "from xonsh.tools import unthreadable\n"
                            "@aliases.register('a')\n"
                            "def _a():\n"
                            "    {body}\n"
                            "a\n",
        }
    }

    executors = {
        "command": "",
        # "prompt": "",
        # "file": "",  #echo 'r = !(fzf)' > script.xsh
        # "stdin": "", #xonsh --no-rc script.xsh
    }

    def cases(self, atoms):
        atoms = atoms.split('.')
        cases = {atoms[0]+'='+atom: code for atom, code in self.snippets[atoms[0]].items()}
        for atom in atoms[1:]:
            new_case = {}
            for case_name, case_code in cases.items():
                for a, c in self.snippets[atom].items():
                    s = c.replace('{body}', case_code)
                    new_case[case_name+','+atom+'='+a] = s
            cases |= new_case
        return cases


if __name__ == '__main__':
    CG = CaseGen()

    cases = CG.cases("sp_atom.sp_pipe.opers.aliases")
    cases |= CG.cases("sp_atom.sp_pipe.opers.calliases")

    i = 0
    for case_spec, case_code in cases.items():
        print(f"{i:02}/{len(cases)}", case_spec)

        case_code = f"print('1CASE1')\n{case_code}\nprint('2CASE2')"
        out, err, rtn = run_xonsh(case_code)
        match = ".*1CASE1\nCCAAPP\n2CASE2\n.*"
        info = f"case_spec={case_spec!r}\ncase_code={case_code!r}\nexp={match!r}\nact={out!r}"
        assert re.match(
            match,
            out,
            re.MULTILINE | re.DOTALL,
        ), info
        i += 1
        # print(info)

    pprint('DONE')
