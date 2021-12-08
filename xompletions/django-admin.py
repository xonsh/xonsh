"""Completers for pip."""

from xonsh.completers.tools import bash_complete_completer

from xonsh.parsers.completion_context import CommandContext


def xonsh_complete(ctx: CommandContext):
    """Completes python's package manager pip."""

    # todo: find a way to get description for the completions like here
    #   https://github.com/apie/fish-django-completions/blob/master/fish_django_completions.py

    # https://github.com/django/django/blob/main/extras/django_bash_completion
    return bash_complete_completer(ctx, DJANGO_AUTO_COMPLETE="1")


if __name__ == "__main__":
    # todo:
    #   1. add test script.
    #   2. add python completer and wrap this as `python manage.py`
    pass
