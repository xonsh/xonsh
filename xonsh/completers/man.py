import os
import re
import pickle
import builtins
import subprocess

import xonsh.lazyasd as xl

from xonsh.completers.tools import get_filter_function

OPTIONS = None
OPTIONS_PATH = None


@xl.lazyobject
def SCRAPE_RE():
    return re.compile(r'^(?:\s*(?:-\w|--[a-z0-9-]+)[\s,])+', re.M)


@xl.lazyobject
def INNER_OPTIONS_RE():
    return re.compile(r'-\w|--[a-z0-9-]+')


def complete_from_man(prefix, line, start, end, ctx):
    """
    Completes an option name, based on the contents of the associated man
    page.
    """
    global OPTIONS, OPTIONS_PATH
    if OPTIONS is None:
        datadir = builtins.__xonsh_env__['XONSH_DATA_DIR']
        OPTIONS_PATH = os.path.join(datadir, 'man_completions_cache')
        try:
            with open(OPTIONS_PATH, 'rb') as f:
                OPTIONS = pickle.load(f)
        except Exception:
            OPTIONS = {}
    if not prefix.startswith('-'):
        return set()
    cmd = line.split()[0]
    if cmd not in OPTIONS:
        try:
            manpage = subprocess.Popen(
                ["man", cmd], stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL)
            # This is a trick to get rid of reverse line feeds
            text = subprocess.check_output(
                ["col", "-b"], stdin=manpage.stdout)
            text = text.decode('utf-8')
            scraped_text = ' '.join(SCRAPE_RE.findall(text))
            matches = INNER_OPTIONS_RE.findall(scraped_text)
            OPTIONS[cmd] = matches
            with open(OPTIONS_PATH, 'wb') as f:
                pickle.dump(OPTIONS, f)
        except Exception:
            return set()
    return {s for s in OPTIONS[cmd]
            if get_filter_function()(s, prefix)}
