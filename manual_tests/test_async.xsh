import time
$ENABLE_ASYNC_PROMPT = True

def _in_future():
    time.sleep(5)
    return "{GREEN} awake "
$PROMPT_FIELDS['in_future'] = _in_future
$PROMPT = '{user}@{hostname}:{cwd} {localtime} {in_future}> '