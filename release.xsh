#!/usr/bin/env xonsh
"""Release helper script for xonsh."""
import os
import re
import sys
import socket
from getpass import getuser, getpass
from argparse import ArgumentParser, Action

try:
  import github3
except ImportError:
  github3 = None

# Configuration!
PROJECT = 'xonsh'
PROJECT_URL = 'http://xon.sh'

# further possible customizations
USER = getuser()
ORG = PROJECT
BRANCH = 'master'
UPSTREAM_ORG = PROJECT
UPSTREAM_REPO = PROJECT
FEEDSTOCK_REPO = PROJECT + '-feedstock'
WILL_DO = {
  'do_version_bump': True,
  'do_git': True,
  'do_pip': True,
  'do_conda': True,
  'do_docs': True,
}
# Allow alternative SHA patterns for feedstock, uncomment the one you need
# Option 0
TAR_SHA_RE = '\s+sha256:.*'
TAR_SHA_SUBS = '  sha256: {0}'
# Option 1
#TAR_SHA_RE = '{% set sha256 = ".*" %}'
#TAR_SHA_SUBS = '{{% set sha256 = "{0}" %}}'
def ver_news(ver):
    news = ('.. current developments\n\n'
             'v{0}\n'
             '====================\n\n')
    news = news.format(ver)
    news += merge_news()
    return news
VERSION_UPDATE_PATTERNS = [
    (r'__version__\s*=.*', (lambda ver: "__version__ = '{0}'".format(ver)),
        [PROJECT, '__init__.py']),
    (r'version:\s*', (lambda ver: 'version: {0}.{{build}}'.format(ver)),
        ['.appveyor.yml']),
    ('.. current developments', ver_news, ['CHANGELOG.rst']),
]


#
# Implementation below!
#

def replace_in_file(pattern, new, fname):
    """Replaces a given pattern in a file"""
    with open(fname, 'r') as f:
        raw = f.read()
    lines = raw.splitlines()
    ptn = re.compile(pattern)
    for i, line in enumerate(lines):
        if ptn.match(line):
            lines[i] = new
    upd = '\n'.join(lines) + '\n'
    with open(fname, 'w') as f:
        f.write(upd)


if os.path.isdir('news'):
    NEWS = [os.path.join('news', f) for f in os.listdir('news')
            if f != 'TEMPLATE.rst']
else:
    NEWS = []
NEWS_CATEGORIES = ['Added', 'Changed', 'Deprecated', 'Removed', 'Fixed',
                   'Security']
NEWS_RE = re.compile('\*\*({0}):\*\*'.format('|'.join(NEWS_CATEGORIES)),
                     flags=re.DOTALL)

def merge_news():
    """Reads news files and merges them."""
    cats = {c: '' for c in NEWS_CATEGORIES}
    for news in NEWS:
        with open(news) as f:
            raw = f.read()
        raw = raw.strip()
        parts = NEWS_RE.split(raw)
        while len(parts) > 0 and parts[0] not in NEWS_CATEGORIES:
            parts = parts[1:]
        for key, val in zip(parts[::2], parts[1::2]):
            val = val.strip()
            if val == 'None':
                continue
            cats[key] += val + '\n'
    for news in NEWS:
        os.remove(news)
    s = ''
    for c in NEWS_CATEGORIES:
        val = cats[c]
        if len(val) == 0:
            continue
        s += '**' + c + ':**\n\n' + val + '\n\n'
    return s

def version_update(ver):
    """Updates version strings in relevant files."""
    for p, n, f in VERSION_UPDATE_PATTERNS:
        if callable(n):
            n = n(ver)
        replace_in_file(p, n, os.path.join(*f))


def just_do_git(ns):
    """Commits and updates tags. Creates github release and adds merged news as
    release notes"""
    git status
    git commit -am @("version bump to " + ns.ver)
    git push @(ns.upstream) @(ns.branch)
    git tag @(ns.ver)
    git push --tags @(ns.upstream)
    if github3 is not None:
        do_github_release(ns.ver, ns.ghuser, 'xonsh', 'xonsh')



def pipify():
    """Make and upload pip package."""
    ./setup.py sdist upload


def shatar(org, repo, target):
    """Returns the SHA-256 sum of the {ver}.tar.gz archive from github."""
    oldpwd = $PWD
    cd /tmp
    url = "https://github.com/{0}/{1}/archive/{2}.tar.gz"
    url = url.format(org, repo, target)
    curl -L -O @(url)
    sha, _ = $(sha256sum @('{}.tar.gz'.format(target))).split()
    cd @(oldpwd)
    return sha


def feedstock_repos(ghuser):
    """Returns the origin and upstream repo URLs for the feedstock."""
    origin = 'git@github.com:{ghuser}/{feedstock}.git'
    origin = origin.format(ghuser=ghuser, feedstock=FEEDSTOCK_REPO)
    upstream = 'git@github.com:conda-forge/{feedstock}.git'
    upstream = upstream.format(feedstock=FEEDSTOCK_REPO)
    return origin, upstream


def condaify(ver, ghuser):
    """Make and upload conda packages."""
    origin, upstream = feedstock_repos(ghuser)
    if not os.path.isdir('feedstock'):
        git clone @(origin) feedstock
    # make sure master feedstock is up to date
    cd feedstock
    git checkout master
    git pull @(upstream) master
    # make and modify version branch
    with ${...}.swap(RAISE_SUBPROC_ERROR=False):
        git checkout -b @(ver) master or git checkout @(ver)
    cd recipe
    set_ver = '{% set version = "' + ver + '" %}'
    set_sha = TAR_SHA_SUBS.format(shatar(UPSTREAM_ORG, UPSTREAM_REPO, ver))
    replace_in_file('{% set version = ".*" %}', set_ver, 'meta.yaml')
    replace_in_file(TAR_SHA_RE, set_sha, 'meta.yaml')
    cd ..
    with ${...}.swap(RAISE_SUBPROC_ERROR=False):
        git commit -am @("updated v" + ver)
    git push --set-upstream @(origin) @(ver)
    cd ..
    if github3 is not None:
        open_feedstock_pr(ver, ghuser)


def create_ghuser_token(ghuser, credfile):
    """Acquires a github token, writes a credentials file, and returns
    the token.
    """
    password = ''
    while not password:
        password = getpass('GitHub Password for {0}: '.format(ghuser))
    note = 'github3.py release.xsh ' + PROJECT + ' ' + socket.gethostname()
    note_url = PROJECT_URL
    scopes = ['user', 'repo']
    try:
        auth = github3.authorize(ghuser, password, scopes, note, note_url,
                                 two_factor_callback=two_factor)
    except github3.exceptions.UnprocessableEntity:
        msg = ('Could not create GitHub authentication token, probably because'
               'it already exists. Try deleting the token titled:\n\n    ')
        msg += note
        msg += ('\n\nfrom https://github.com/settings/tokens')
        raise RuntimeError(msg)
    with open(credfile, 'w') as f:
        f.write(str(auth.token) + '\n')
        f.write(str(auth.id))
    return auth.token


def two_factor():
    """2 Factor Authentication callback function, called by `github3.authorize`
    as needed.
    """
    code = ''
    while not code:
        code = input('Enter 2FA code: ')
    return code


def read_ghuser_token(credfile):
    """Reads in a github user token from the credentials file."""
    with open(credfile, 'r') as f:
        token = f.readline().strip()
        ghid = f.readline().strip()
    return token


def ghlogin(ghuser):
    """Returns a github object that is logged in."""
    credfile = ghuser + '.cred'
    if os.path.exists(credfile):
        token = read_ghuser_token(credfile)
    else:
        token = create_ghuser_token(ghuser, credfile)
    gh = github3.login(ghuser, token=token)
    return gh

def do_github_release(ver, ghuser, org, repo):
    """Performs a github release"""
    login = ghlogin(ghuser)
    repo = login.repository(org, repo)
    news = read_changelog_recent()
    repo.create_release(ver, target_commitish='master', name=ver, body=news,
                        draft=False, prerelease=False)

def read_changelog_recent():
    with open('CHANGELOG.rst', 'r') as f:
        line = ''
        while not line.startswith('v'):
            line = f.readline()
        news = ''
        while True:
            line = f.readline()
            if line.startswith('v'):
                break
            news += line

    return news

def open_feedstock_pr(ver, ghuser):
    """Opens a feedstock PR."""
    origin, upstream = feedstock_repos(ghuser)
    gh = ghlogin(ghuser)
    repo = gh.repository('conda-forge', FEEDSTOCK_REPO)
    print('Creating conda-forge feedstock pull request...')
    title = PROJECT + ' v' + ver
    head = ghuser + ':' + ver
    body = 'Merge only after success.'
    pr = repo.create_pull(title, 'master', head, body=body)
    if pr is None:
        print('!!!Failed to create pull request!!!')
    else:
        print('Pull request created at ' + pr.html_url)


def docser():
    """Create docs"""
    # FIXME this should be made more general
    ./setup.py install --user
    cd docs
    make clean html push-root
    cd ..


DOERS = ('do_version_bump', 'do_git', 'do_pip', 'do_conda', 'do_docs')

class OnlyAction(Action):
    def __init__(self, option_strings, dest, **kwargs):
        super().__init__(option_strings, dest, **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        for doer in DOERS:
            if doer == self.dest:
                setattr(namespace, doer, True)
            else:
                setattr(namespace, doer, False)


def main(args=None):
    default_upstream = 'git@github.com:{org}/{repo}.git'
    default_upstream = default_upstream.format(org=UPSTREAM_ORG,
                                               repo=UPSTREAM_REPO)
    # make parser
    parser = ArgumentParser('release')
    parser.add_argument('--upstream', default=default_upstream,
                        help='upstream repo')
    parser.add_argument('-b', '--branch', default=BRANCH,
                        help='branch to commit / push to.')
    parser.add_argument('--github-user', default=USER, dest='ghuser',
                        help='GitHub username.')
    for doer in DOERS:
        base = doer[3:].replace('_', '-')
        wd = WILL_DO.get(doer, True)
        parser.add_argument('--do-' + base, dest=doer, default=wd,
                            action='store_true',
                            help='runs {}, default: {}'.format(base, wd))
        parser.add_argument('--no-' + base, dest=doer, action='store_false',
                            help='does not run ' + base)
        parser.add_argument('--only-' + base, dest=doer, action=OnlyAction,
                            help='only runs ' + base, nargs=0)
    parser.add_argument('ver', help='target version string')
    ns = parser.parse_args(args or $ARGS[1:])
    # enable debugging
    $RAISE_SUBPROC_ERROR = True
    #trace on
    # run commands
    if ns.do_version_bump:
        version_update(ns.ver)
    if ns.do_git:
        just_do_git(ns)
    if ns.do_pip:
        pipify()
    if ns.do_conda:
        condaify(ns.ver, ns.ghuser)
    if ns.do_docs:
        docser()
    # disable debugging
    #trace off


if __name__ == '__main__':
    main()
