#!/usr/bin/env xonsh
"""A shameless copy of oh-my-zsh."""
from xontrib.abbrevs import abbrevs

from packaging import version as ver

# Git version checking
git_version = $(git version 2>/dev/null).split()[2]

#
# Functions
#

# Pretty log messages
def _git_log_prettily():
    if len($ARGS > 1):
        git log --pretty=$ARG1


# Warn if the current branch is a WIP
def work_in_progress():
    if $(git log -n 1 2>/dev/null | grep -q -c "\\-\\-wip\\-\\-"):
        echo "WIP!!"

# Check if main exists and use instead of master
def git_main_branch():
    if !(git rev-parse --git-dir &>/dev/null).returncode != 0:
        return
    for branch in ["master", "main", "trunk"]:
        if !(git show-ref -q --verify refs/heads/@(branch)).returncode == 0:
            return branch

#
# Aliases
# (sorted alphabetically)
#

my_aliases = {
    "ip": "ip -c",
    "g": "git",

    "ga": "git add",
    "gaa": "git add --all",
    "gapa": "git add --patch",
    "gau": "git add --update",
    "gav": "git add --verbose",
    "gap": "git apply",
    "gapt": "git apply --3way",

    "gb": "git branch",
    "gba": "git branch -a",
    "gbd": "git branch -d",
    "gbda": 'git branch --no-color --merged | grep -vE f"^(\\+|\\*|\\s*({git_main_branch()}|development|develop|devel|dev)\\s*$)" | xargs -n 1 git branch -d',
    "gbD": "git branch -D",
    "gbl": "git blame -b -w",
    "gbnm": "git branch --no-merged",
    "gbr": "git branch --remote",
    "gbs": "git bisect",
    "gbsb": "git bisect bad",
    "gbsg": "git bisect good",
    "gbsr": "git bisect reset",
    "gbss": "git bisect start",

    "gc": "git commit -v",
    "gc^": "git commit -v --amend",
    "gcn^": "git commit -v --no-edit --amend",
    "gca": "git commit -v -a",
    "gca^": "git commit -v -a --amend",
    "gcan^": "git commit -v -a --no-edit --amend",
    "gcans^": "git commit -v -a -s --no-edit --amend",
    "gcam": "git commit -a -m",
    "gcsm": "git commit -s -m",
    "gcb": "git checkout -b",
    "gcf": "git config --list",
    "gcl": "git clone --recurse-submodules",
    "gclean": "git clean -id",
    "gpristine": "git reset --hard && git clean -dffx",
    "gcm": "git checkout @(git_main_branch())",
    "gcd": "git checkout develop",
    "gcmsg": "git commit -m",
    "gco": "git checkout",
    "gcount": "git shortlog -sn",
    "gcp": "git cherry-pick",
    "gcpa": "git cherry-pick --abort",
    "gcpc": "git cherry-pick --continue",
    "gcs": "git commit -S",

    "gd": "git diff",
    "gdca": "git diff --cached",
    "gdcw": "git diff --cached --word-diff",
    "gdct": "git describe --tags $(git rev-list --tags --max-count=1)",
    "gds": "git diff --staged",
    "gdt": "git diff-tree --no-commit-id --name-only -r",
    "gdw": "git diff --word-diff",
}    


my_aliases.update( {
    "gdv": "git diff -w <edit> | view -",
    "gdnolock": 'git diff <edit> ":(exclude)package-lock.json" ":(exclude)*.lock"',
    "gf": "git fetch"
})

if ver.parse(git_version)>=ver.parse("2.8"):
    my_aliases["gfa"] = "git fetch --all --prune --jobs=10"
else:
    my_aliases["gfa"] = "git fetch --all --prune"

my_aliases.update( {
    "gfo": "git fetch origin",
    "gfg": "git ls-files | grep",
    "gg": "git gui citool",
    "gga": "git gui citool --amend",
})

"""
TODO:
function ggf() {
  [[ "$#" != 1 ]] && local b="$(git_current_branch)"
  git push --force origin "${b:=$1}"
}
compdef _git ggf=git-checkout
function ggfl() {
  [[ "$#" != 1 ]] && local b="$(git_current_branch)"
  git push --force-with-lease origin "${b:=$1}"
}
compdef _git ggfl=git-checkout

function ggl() {
  if [[ "$#" != 0 ]] && [[ "$#" != 1 ]]; then
    git pull origin "${*}"
  else
    [[ "$#" == 0 ]] && local b="$(git_current_branch)"
    git pull origin "${b:=$1}"
  fi
}
compdef _git ggl=git-checkout

function ggp() {
  if [[ "$#" != 0 ]] && [[ "$#" != 1 ]]; then
    git push origin "${*}"
  else
    [[ "$#" == 0 ]] && local b="$(git_current_branch)"
    git push origin "${b:=$1}"
  fi
}
compdef _git ggp=git-checkout

function ggpnp() {
  if [[ "$#" == 0 ]]; then
    ggl && ggp
  else
    ggl "${*}" && ggp "${*}"
  fi
}
compdef _git ggpnp=git-checkout

function ggu() {
  [[ "$#" != 1 ]] && local b="$(git_current_branch)"
  git pull --rebase origin "${b:=$1}"
}
compdef _git ggu=git-checkout
"""


my_aliases.update( {
    "ggpur": "ggu",
    "ggpull": 'git pull origin f"{git_current_branch()}"',
    "ggpush": 'git push origin f"{git_current_branch()}"',
    "ggsup": "git branch --set-upstream-to=origin/@(f'{git_current_branch()}')",
    "gpsup": "git push --set-upstream origin f'{git_current_branch()}'",
    "ghh": "git help",
    "gignore": "git update-index --assume-unchanged",
    "gignored": 'git ls-files -v | grep "^[[:lower:]]"',
    "git-svn-dcommit-push": "git svn dcommit && git push github @(f'{git_current_branch()}'):svntrunk",
    "gk": "\\gitk --all --branches",
    "gke": "\\gitk --all $(git log -g --pretty=%h)",
    "gl": "git pull",
    "glg": "git log --stat",
    "glgp": "git log --stat -p",
    "glgg": "git log --graph",
    "glgga": "git log --graph --decorate --all",
    "glgm": "git log --graph --max-count=10",
    "glo": "git log --oneline --decorate",
    "glol": "git log --graph --pretty='%Cred%h%Creset -%C(auto)%d%Creset %s %Cgreen(%cr) %C(bold blue)<%an>%Creset'",
    "glols": "git log --graph --pretty='%Cred%h%Creset -%C(auto)%d%Creset %s %Cgreen(%cr) %C(bold blue)<%an>%Creset' --stat",
    "glod": "git log --graph --pretty='%Cred%h%Creset -%C(auto)%d%Creset %s %Cgreen(%ad) %C(bold blue)<%an>%Creset'",
    "glods": "git log --graph --pretty='%Cred%h%Creset -%C(auto)%d%Creset %s %Cgreen(%ad) %C(bold blue)<%an>%Creset' --date=short",
    "glola": "git log --graph --pretty='%Cred%h%Creset -%C(auto)%d%Creset %s %Cgreen(%cr) %C(bold blue)<%an>%Creset' --all",
    "glog": "git log --oneline --decorate --graph",
    "gloga": "git log --oneline --decorate --graph --all",
    "glp": "_git_log_prettily",
    "gm": "git merge",
    "gmom": "git merge origin/$(git_main_branch)",
    "gmt": "git mergetool --no-prompt",
    "gmtvim": "git mergetool --no-prompt --tool=vimdiff",
    "gmum": "git merge upstream/$(git_main_branch)",
    "gma": "git merge --abort",
    "gp": "git push",
    "gpd": "git push --dry-run",
    "gpf": "git push --force-with-lease",
    "gpf^": "git push --force",
    "gpoat": "git push origin --all && git push origin --tags",
    "gpu": "git push upstream",
    "gpv": "git push -v",
    "gr": "git remote",
    "gra": "git remote add",
    "grb": "git rebase",
    "grba": "git rebase --abort",
    "grbc": "git rebase --continue",
    "grbd": "git rebase develop",
    "grbi": "git rebase -i",
    "grbm": "git rebase $(git_main_branch)",
    "grbs": "git rebase --skip",
    "grev": "git revert",
    "grh": "git reset",
    "grhh": "git reset --hard",
    "groh": "git reset origin/$(git_current_branch) --hard",
    "grm": "git rm",
    "grmc": "git rm --cached",
    "grmv": "git remote rename",
    "grrm": "git remote remove",
    "grs": "git restore",
    "grset": "git remote set-url",
    "grss": "git restore --source",
    "grst": "git restore --staged",
    "grt": 'cd "$(git rev-parse --show-toplevel || echo .)"',
    "gru": "git reset --",
    "grup": "git remote update",
    "grv": "git remote -v",
    "gsb": "git status -sb",
    "gsd": "git svn dcommit",
    "gsh": "git show",
    "gsi": "git submodule init",
    "gsps": "git show --pretty=short --show-signature",
    "gsr": "git svn rebase",
    "gss": "git status -s",
    "gst": "git status",
})




"""
============= DIRECTORIES ==============
"""

# Changing/making/removing directory

my_aliases.update( {
    "..": "cd ..",
    # '...' is taken by Ellipsis?? This is a bug in the lexer.
    "....": "cd ../../..",
    ".....": "cd ../../../..",
    "......": "cd ../../../../..",
    "md": "mkdir -p",
    "rd": "rmdir",
    "l": "ls -lah",
    "ll": "ls -lh",
    "la": "ls  -lAh",
})

abbrevs.update(my_aliases)