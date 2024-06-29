"""PTK specific PromptFormatter class."""

import functools
import typing as tp

from xonsh.prompt.base import DEFAULT_PROMPT, PromptFormatter
from xonsh.shells.ptk_shell.updator import AsyncPrompt, PromptUpdator


class PTKPromptFormatter(PromptFormatter):
    """A subclass of PromptFormatter to support rendering prompt sections with/without threads."""

    def __init__(self, shell):
        super().__init__()
        self.shell = shell

    def __call__(
        self,
        template=DEFAULT_PROMPT,
        fields=None,
        threaded=False,
        prompt_name: str = None,
        **_,
    ) -> str:
        """Formats a xonsh prompt template string."""

        kwargs = {}
        if threaded:
            # init only for async prompts
            if not hasattr(self, "updator"):
                # updates an async prompt.
                self.updator = PromptUpdator(self.shell)

            # set these attributes per call. one can enable/disable async-prompt inside a session.
            kwargs["async_prompt"] = self.updator.add(prompt_name)

        # in case of failure it returns a fail-over template. otherwise it returns list of tokens
        return super().__call__(template, fields, **kwargs)

    def _format_prompt(
        self,
        template=DEFAULT_PROMPT,
        async_prompt: tp.Optional[AsyncPrompt] = None,
        **kwargs,
    ):
        toks = super()._format_prompt(
            template=template, async_prompt=async_prompt, **kwargs
        )
        if async_prompt is not None:
            # late binding of values
            async_prompt.tokens = toks
        return toks

    def _get_field_value(
        self, field, async_prompt=None, idx=None, spec=None, conv=None, **_
    ):
        func = functools.partial(super()._get_field_value, field)
        if async_prompt is not None and self.fields.needs_calling(field):
            # create a thread and return an intermediate result
            return async_prompt.submit_section(func, field, idx, spec, conv)
        return func()

    def start_update(self):
        """Start listening on the prompt section futures."""
        self.updator.start()
