# -*- coding: utf-8 -*-
"""Informative git status prompt formatter"""

import os
import builtins
import subprocess

import xonsh.lazyasd as xl


def _check_output(*args, **kwargs):
    kwargs.update(dict(env=builtins.__xonsh_env__.detype(),
                       stderr=subprocess.DEVNULL,
                       timeout=builtins.__xonsh_env__['VC_BRANCH_TIMEOUT'],
                       universal_newlines=True
                       ))
    return subprocess.check_output(*args, **kwargs)


@xl.lazyobject
def _DEFS():
    DEFS = {
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
    return DEFS


def _get_def(key):
    return builtins.__xonsh_env__.get('XONSH_GITSTATUS_' + key) or _DEFS[key]


def _get_tag_or_hash():
    tag = _check_output(['git', 'describe', '--exact-match']).strip()
    if tag:
        return tag
    hash_ = _check_output(['git', 'rev-parse', '--short', 'HEAD']).strip()
    return _get_def('HASH') + hash_


def _get_stash(gitdir):
    try:
        with open(os.path.join(gitdir, 'logs/refs/stash')) as f:
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


def gitstatus():
    """Return (branch name, number of ahead commit, number of behind commit,
               untracked number, changed number, conflicts number,
               staged number, stashed number, operation)"""
    status = _check_output(['git', 'status', '--porcelain', '--branch'])
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

    gitdir = _check_output(['git', 'rev-parse', '--git-dir']).strip()
    stashed = _get_stash(gitdir)
    operations = _gitoperation(gitdir)

    return (branch, num_ahead, num_behind,
            untracked, changed, conflicts, staged, stashed,
            operations)


def gitstatus_prompt():
    """Return str `BRANCH|OPERATOR|numbers`"""
    try:
        (branch, num_ahead, num_behind,
         untracked, changed, conflicts, staged, stashed,
         operations) = gitstatus()
    except subprocess.SubprocessError:
        return ''

    ret = _get_def('BRANCH') + branch
    if num_ahead > 0:
        ret += _get_def('AHEAD') + str(num_ahead)
    if num_behind > 0:
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

    return ret
