from xonsh.tools import ON_WINDOWS as _ON_WINDOWS
from xonsh.tools import is_string, ensure_string
from xonsh.environ import Ensurer


${...}.set_ensurer("XONTRIB_PROMPT_RET_CODE_COLOR_ZERO",
    Ensurer(is_string, ensure_string, ensure_string))

${...}.set_ensurer("XONTRIB_PROMPT_RET_CODE_COLOR_NONZERO",
    Ensurer(is_string, ensure_string, ensure_string))


if _ON_WINDOWS:
    $XONTRIB_PROMPT_RET_CODE_COLOR_ZERO = ${...}.get(
            "XONTRIB_PROMPT_RET_CODE_COLOR_ZERO",
            '{BOLD_INTENSE_CYAN}')
    $XONTRIB_PROMPT_RET_CODE_COLOR_NONZERO = ${...}.get(
            "XONTRIB_PROMPT_RET_CODE_COLOR_NONZERO",
            '{BOLD_INTENSE_RED}')


def _ret_code_color():
    if __xonsh__.history.rtns:
        ret_code = True if __xonsh__.history.rtns[-1] == 0 else False
    else:
        ret_code = True

    if ret_code:
	return ${...}.get("XONTRIB_PROMPT_RET_CODE_COLOR_ZERO",
		'{BOLD_BLUE}')
    else:
	return ${...}.get("XONTRIB_PROMPT_RET_CODE_COLOR_NONZERO",
		'{BOLD_RED}')


def _ret_code():
    if __xonsh__.history.rtns:
        return_code = __xonsh__.history.rtns[-1]
        if return_code != 0:
            return '[{}]'.format(return_code)
    return None


$PROMPT = $PROMPT.replace('{prompt_end}{NO_COLOR}',
        '{ret_code_color}{ret_code}{prompt_end}{NO_COLOR}')


$PROMPT_FIELDS['ret_code_color'] = _ret_code_color
$PROMPT_FIELDS['ret_code'] = _ret_code
