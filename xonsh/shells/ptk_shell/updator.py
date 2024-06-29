"""Has classes that help updating Prompt sections using Threads."""

import concurrent.futures
import threading
import typing as tp

from prompt_toolkit import PromptSession
from prompt_toolkit.formatted_text import PygmentsTokens

from xonsh.built_ins import XSH
from xonsh.prompt.base import ParsedTokens
from xonsh.style_tools import partial_color_tokenize, style_as_faded


class Executor:
    """Caches thread results across prompts."""

    def __init__(self):
        self.thread_pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=XSH.env["ASYNC_PROMPT_THREAD_WORKERS"]
        )

        # the attribute, .cache is cleared between calls.
        # This caches results from callback alone by field name.
        self.thread_results = {}

    def submit(self, func: tp.Callable, field: str):
        future = self.thread_pool.submit(self._run_func, func, field)
        place_holder = "{" + field + "}"

        return (
            future,
            (
                self.thread_results[field]
                if field in self.thread_results
                else place_holder
            ),
            place_holder,
        )

    def _run_func(self, func, field):
        """Run the callback and store the result."""
        result = func()
        self.thread_results[field] = (
            result if result is None else style_as_faded(result)
        )
        return result


class AsyncPrompt:
    """Represent an asynchronous prompt."""

    def __init__(self, name: str, session: PromptSession, executor: Executor):
        """

        Parameters
        ----------
        name: str
            what prompt to update. One of ['message', 'rprompt', 'bottom_toolbar']
        session: PromptSession
            current ptk session
        """

        self.name = name

        # list of tokens in that prompt. It could either be resolved or not resolved.
        self.tokens: tp.Optional[ParsedTokens] = None
        self.timer = None
        self.session = session
        self.executor = executor

        # (Key: the future object) that is created for the (value: index/field_name) in the tokens list
        self.futures: dict[
            concurrent.futures.Future,
            tuple[str, tp.Optional[int], tp.Optional[str], tp.Optional[str]],
        ] = {}

    def start_update(self, on_complete):
        """Listen on futures and update the prompt as each one completed.

        Timer is used to avoid clogging multiple calls at the same time.

        Parameters
        -----------
        on_complete:
            callback to notify after all the futures are completed
        """
        if not self.tokens:
            print(f"Warn: AsyncPrompt is created without tokens - {self.name}")
            return
        for fut in concurrent.futures.as_completed(self.futures):
            try:
                val = fut.result()
            except concurrent.futures.CancelledError:
                continue

            if fut not in self.futures:
                # rare case where the future is completed but the container is already cleared
                # because new prompt is called
                continue

            placeholder, idx, spec, conv = self.futures[fut]
            # example: placeholder="{field}", idx=10, spec="env: {}"

            if isinstance(idx, int):
                self.tokens.update(idx, val, spec, conv)
            else:  # when the function is called outside shell.
                for idx, ptok in enumerate(self.tokens.tokens):
                    if placeholder in ptok.value:
                        val = ptok.value.replace(placeholder, val)
                        self.tokens.update(idx, val, spec, conv)

            # calling invalidate in less period is inefficient
            self.invalidate()

        on_complete(self.name)

    def invalidate(self):
        """Create a timer to update the prompt. The timing can be configured through env variables.
        threading.Timer is used to stop calling invalidate frequently.
        """
        from xonsh.shells.ptk_shell import tokenize_ansi

        if self.timer:
            self.timer.cancel()

        def _invalidate():
            new_prompt = self.tokens.process()
            formatted_tokens = tokenize_ansi(
                PygmentsTokens(partial_color_tokenize(new_prompt))
            )
            setattr(self.session, self.name, formatted_tokens)
            self.session.app.invalidate()

        self.timer = threading.Timer(XSH.env["ASYNC_INVALIDATE_INTERVAL"], _invalidate)
        self.timer.start()

    def stop(self):
        """Stop any running threads"""
        for fut in self.futures:
            fut.cancel()
        self.futures.clear()

    def submit_section(
        self,
        func: tp.Callable,
        field: str,
        idx: tp.Optional[int] = None,
        spec: tp.Optional[str] = None,
        conv=None,
    ):
        future, intermediate_value, placeholder = self.executor.submit(func, field)
        self.futures[future] = (placeholder, idx, spec, conv)
        return intermediate_value


class PromptUpdator:
    """Handle updating multiple AsyncPrompt instances prompt/rprompt/bottom_toolbar"""

    def __init__(self, shell):
        from xonsh.shells.ptk_shell import PromptToolkitShell

        self.prompts: dict[str, AsyncPrompt] = {}
        self.shell: PromptToolkitShell = shell
        self.executor = Executor()
        self.futures = {}
        self.attrs_loaded = None

    def add(self, prompt_name: tp.Optional[str]) -> tp.Optional[AsyncPrompt]:
        # clear out old futures from the same prompt
        if prompt_name is None:
            return None

        self.stop(prompt_name)

        self.prompts[prompt_name] = AsyncPrompt(
            prompt_name, self.shell.prompter, self.executor
        )
        return self.prompts[prompt_name]

    def add_attrs(self):
        for attr, val in self.shell.get_lazy_ptk_kwargs():
            setattr(self.shell.prompter, attr, val)
        self.shell.prompter.app.invalidate()

    def start(self):
        """after ptk prompt is created, update it in background."""
        if not self.attrs_loaded:
            self.attrs_loaded = self.executor.thread_pool.submit(self.add_attrs)

        prompts = list(self.prompts)  # removal safe
        for pt_name in prompts:
            if pt_name not in self.prompts:
                continue
            prompt = self.prompts[pt_name]
            future = self.executor.thread_pool.submit(
                prompt.start_update, self.on_complete
            )
            self.futures[pt_name] = future

    def stop(self, prompt_name: str):
        if prompt_name in self.prompts:
            self.prompts[prompt_name].stop()
        if prompt_name in self.futures:
            self.futures[prompt_name].cancel()

    def on_complete(self, prompt_name):
        self.prompts.pop(prompt_name, None)
        self.futures.pop(prompt_name, None)
