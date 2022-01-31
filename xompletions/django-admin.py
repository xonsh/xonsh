"""Completers for pip."""

from xonsh.completers.tools import comp_based_completer
from xonsh.parsers.completion_context import CommandContext


def xonsh_complete(ctx: CommandContext):
    """Completes python's package manager pip."""
    # adapted from https://github.com/django/django/blob/main/extras/django_bash_completion

    # todo: find a way to get description for the completions like here
    #   1. https://github.com/apie/fish-django-completions/blob/master/fish_django_completions.py
    #   2. complete python manage.py invocations
    # https://github.com/django/django/blob/main/extras/django_bash_completion
    return comp_based_completer(ctx, DJANGO_AUTO_COMPLETE="1")
