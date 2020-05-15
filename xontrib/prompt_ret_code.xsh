from xonsh.tools import ON_WINDOWS as _ON_WINDOWS


def _ret_code_color():
    if __xonsh__.history.rtns:
        color = 'blue' if __xonsh__.history.rtns[-1] == 0 else 'red'
    else:
        color = 'blue'
    if _ON_WINDOWS:
        if color == 'blue':
            return '{BOLD_INTENSE_CYAN}'
        elif color == 'red':
            return '{BOLD_INTENSE_RED}'
    else:
        if color == 'blue':
            return '{BOLD_BLUE}'
        elif color == 'red':
            return '{BOLD_RED}'


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
