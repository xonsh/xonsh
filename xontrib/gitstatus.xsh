'''informative git status for prompt'''

import re
import os
import builtins
import functools
import subprocess

__all__ = []

_env = builtins.__xonsh_env__

check_output = functools.partial(subprocess.check_output,
                                 env=_env.detype(),
                                 stderr=subprocess.DEVNULL,
                                 timeout=_env['VC_BRANCH_TIMEOUT'],
                                 universal_newlines=True)

_DEFS = {
    'HASH': ':',
    'BRANCH': '{CYAN}',
    'OPERATION': '{CYAN}',
    'STAGED': '{RED}●',
    'CONFLICTS': '{RED}×',
    'CHANGED': '{BLUE}+',
    'UNTRACKED': '…',
    'STASHED': '⚑',
    'CLEAN': '{BOLD_GREEN}✓',
    'AHEAD': '↑·',
    'BEHIND': '↓·',
}

_get_def = lambda key: _env.get('XONSH_GITSTATUS_' + key) \
                       or _DEFS[key]

def _get_tag_or_hash():
    tag = check_output(['git', 'describe', '--exact-match']).strip()
    if tag:
        return tag
    hash_ = check_output(['git', 'rev-parse', '--short', 'HEAD']).strip()
    return _get_def('HASH') + hash_

def _get_stash(gitdir):
    try:
        with open(os.path.join(gitdir, '/logs/refs/stash')) as f:
            return sum(1 for _ in f)
    except IOError:
        return 0

def _gitoperation(gitdir):
    files = (
             ('rebase-merge', 'REBASE'),
             ('rebase-apply', 'AM/REBASE'),
             ('MERGE_HEAD', 'MERGING'),
             ('CHERRY_PICK_HEAD', 'CHERRY-PICKING'),
             ('REVERT_HEAD', 'REVERTING'),
             ('BISECT_LOG', 'BISECTING'),
             )
    return [f[1] for f in files
            if os.path.exists(os.path.join(gitdir, f[0]))]


def _gitstatus():
    status = check_output(['git', 'status', '--porcelain', '--branch'])
    branch = ''
    num_ahead, num_behind = 0, 0
    untracked, changed, conflicts, staged = 0, 0, 0, 0
    for line in status.splitlines():
        if line.startswith('##'):
            line = line[2:].strip()
            if 'Initial commit on' in line:
                branch = line.split()[-1]
            elif 'no branch' in line:
                branch = _get_tag_or_hash()
            elif '...' not in line:
                branch = line
            else:
                branch, rest = line.split('...')
                if ' ' in rest:
                    divergence = rest.split(' ', 1)[-1]
                    divergence = divergence.strip('[]')
                    for div in divergence.split(', '):
                        if 'ahead' in div:
                            num_ahead = int(div[len('ahead '):].strip())
                        elif 'behind' in div:
                            num_behind = int(div[len('behind '):].strip())
        elif line.startswith('??'):
            untracked += 1
        else:
            if len(line) > 1 and line[1] == 'M':
                changed += 1

            if len(line) > 0 and line[0] == 'U':
                conflicts += 1
            elif len(line) > 0 and line[0] != ' ':
                staged += 1

    gitdir = check_output(['git', 'rev-parse', '--git-dir']).strip()
    stashed = _get_stash(gitdir)
    operations = _gitoperation(gitdir)

    return (branch, num_ahead, num_behind,
            untracked, changed, conflicts, staged, stashed,
            operations)


def _gitstatus_prompt():
    try:
        (branch, num_ahead, num_behind,
         untracked, changed, conflicts, staged, stashed,
         operations) = _gitstatus()
    except subprocess.SubprocessError:
        return ''

    ret = '[' + _get_def('BRANCH') + branch
    if num_ahead + num_behind > 0:
        ret += _get_def('AHEAD') + str(num_ahead)
        ret += _get_def('BEHIND') + str(num_behind)
    if operations:
        ret += _get_def('OPERATION') + '|' + '|'.join(operations)
    ret += '|'
    if staged > 0:
        ret += _get_def('STAGED') + str(staged) + '{NO_COLOR}'
    if conflicts > 0:
        ret += _get_def('CONFLICTS') + str(conflicts) + '{NO_COLOR}'
    if changed > 0:
        ret += _get_def('CHANGED') + str(changed) + '{NO_COLOR}'
    if untracked > 0:
        ret += _get_def('UNTRACKED') + str(untracked) + '{NO_COLOR}'
    if stashed > 0:
        ret += _get_def('STASHED') + str(stashed) + '{NO_COLOR}'
    if staged + conflicts + changed + untracked + stashed == 0:
        ret += _get_def('CLEAN') + '{NO_COLOR}'
    ret += ']'

    return ret


$FORMATTER_DICT['gitstatus'] = _gitstatus_prompt

