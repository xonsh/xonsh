import os
import re
import pickle
import subprocess

from xonsh.completers.tools import get_filter_function

OPTIONS_PATH = os.path.join(os.path.expanduser('~'), ".xonsh_man_completions")
try:
    with open(OPTIONS_PATH, 'rb') as f:
        OPTIONS = pickle.load(f)
except:
    OPTIONS = {}


def save_cached_options():
    with open(OPTIONS_PATH, 'wb') as f:
        pickle.dump(OPTIONS, f)

SCRAPE_RE = re.compile(r'^(?:\s*(?:-\w|--[a-z0-9-]+)[\s,])+', re.M)
INNER_OPTIONS_RE = re.compile(r'-\w|--[a-z0-9-]+')


def complete_from_man(prefix, line, start, end, ctx):
    """Completes an option name, based on the contents of the associated man
    page."""
    global OPTIONS
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
            save_cached_options()
        except:
            return set()
    return {s for s in OPTIONS[cmd]
            if get_filter_function()(s, prefix)}
