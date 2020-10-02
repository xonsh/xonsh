"""PTK specific PromptFormatter class."""

import functools

from prompt_toolkit import PromptSession
from xonsh.prompt.base import PromptFormatter, DEFAULT_PROMPT
from xonsh.ptk_shell.updator import PromptUpdator


class PTKPromptFormatter(PromptFormatter):
    """A subclass of PromptFormatter to support rendering prompt sections with/without threads."""

    def __init__(self, session: PromptSession):
        super().__init__()
        self.session = session

    def __call__(
        self,
        template=DEFAULT_PROMPT,
        fields=None,
        threaded=False,
        prompt_name: str = None,
        **_
    ) -> str:
        """Formats a xonsh prompt template string."""

        kwargs = {}
        if threaded:
            # init only for async prompts
            if not hasattr(self, "updator"):
                # updates an async prompt.
                self.updator = PromptUpdator(self.session)

            # set these attributes per call. one can enable/disable async-prompt inside a session.
            kwargs["async_prompt"] = self.updator.add(prompt_name)

        # in case of failure it returns a fail-over template. otherwise it returns list of tokens
        prompt_or_tokens = super().__call__(template, fields, **kwargs)

        if isinstance(prompt_or_tokens, list):
            if threaded:
                self.updator.set_tokens(prompt_name, prompt_or_tokens)
            return "".join(prompt_or_tokens)

        return prompt_or_tokens

    def _format_prompt(self, template=DEFAULT_PROMPT, **kwargs):
        return self._get_tokens(template, **kwargs)

    def _no_cache_field_value(
        self, field, field_value, idx=None, async_prompt=None, **_
    ):
        """This branch is created so that caching fields per prompt would still work."""
        func = functools.partial(super()._no_cache_field_value, field, field_value)

        if async_prompt is not None and callable(field_value):
            # create a thread and return an intermediate result
            return async_prompt.submit_section(func, field, idx)

        return func()

    def start_update(self):
        """Start listening on the prompt section futures."""
        self.updator.start()
