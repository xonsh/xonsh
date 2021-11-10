from xonsh.tools import ON_WINDOWS as _ON_WINDOWS
import xonsh.session as xsh


def _ret_code_color():
    if xsh.XSH.history.rtns:
        color = "blue" if xsh.XSH.history.rtns[-1] == 0 else "red"
    else:
        color = "blue"
    if _ON_WINDOWS:
        if color == "blue":
            return "{BOLD_INTENSE_CYAN}"
        elif color == "red":
            return "{BOLD_INTENSE_RED}"
    else:
        if color == "blue":
            return "{BOLD_BLUE}"
        elif color == "red":
            return "{BOLD_RED}"


def _ret_code():
    if xsh.XSH.history.rtns:
        return_code = xsh.XSH.history.rtns[-1]
        if return_code != 0:
            return "[{}]".format(return_code)
    return None


def _update():

    env = xsh.XSH.env

    env["PROMPT"] = env["PROMPT"].replace(
        "{prompt_end}{RESET}", "{ret_code_color}{ret_code}{prompt_end}{RESET}"
    )

    flds = env["PROMPT_FIELDS"]
    flds["ret_code_color"] = _ret_code_color
    flds["ret_code"] = _ret_code


# xontrib loads updates context
_update()
