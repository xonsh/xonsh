import time
$ENABLE_ASYNC_PROMPT = True

def red_green(delay):
    start = time.time()
    time.sleep(delay)
    end = time.time()
    return f"{{GREEN}} done in {(end-start):.2F}"

# $PROMPT_FIELDS.update({...}) didn't work?
$PROMPT_FIELDS['d5_sec'] = (lambda: red_green(5))
$PROMPT_FIELDS['d10_sec'] = (lambda: red_green(10))
$PROMPT_FIELDS['d1_sec'] = (lambda:red_green(1))

$PROMPT_FIELDS['in_future'] = _in_future
$PROMPT = 'xx {user}@{hostname}:{cwd} {d5sec}> '
$RIGHT_PROMPT = '< {RED} {d1_sec}'
$BOTTOM_TOOLBAR = 'normal stuff {RED} {d1_sec}  {NO_COLOR}   {RED} {d5_sec} {NO_COLOR}  {RED} {d10_sec} {NO_COLOR}'