from xonsh.tools import ON_WINDOWS as _ON_WINDOWS


def _ret_code_color():
    try:
	color_bg = $PROMPT_RET_CODE_BACKGROUND
    except:
	color_bg = False

    if color_bg:
	prefix = 'BACKGROUND'
    else:
	prefix = 'BOLD'

    if __xonsh__.history.rtns:
        color = 'blue' if __xonsh__.history.rtns[-1] == 0 else 'red'
    else:
        color = 'blue'

    if _ON_WINDOWS:
        if color == 'blue':
            return '{%s_INTENSE_CYAN}' % prefix
        elif color == 'red':
            return '{%s_INTENSE_RED}' % prefix
    else:
        if color == 'blue':
            return '{%s_BLUE}' % prefix
        elif color == 'red':
            return '{%s_RED}' % prefix


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
