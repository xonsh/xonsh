"""Completer for unicode symbols and emoji.

Trigger prefixes are configurable via environment variables:

- ``$XONSH_EMOJI_TRIGGER`` (default ``"::"``) — colorful emoji (faces, animals, objects).
- ``$XONSH_EMOJI_SYMBOL_TRIGGER`` (default ``":::"``) — simple unicode symbols (arrows, math, dingbats).

Set to empty string to disable.
"""

import unicodedata

from xonsh.built_ins import XSH
from xonsh.completers.tools import RichCompletion, contextual_command_completer
from xonsh.parsers.completion_context import CommandContext

# Colorful emoji (width=2 only)
_COLOR_RANGES = [
    (0x1F300, 0x1F5FF),  # Misc symbols and pictographs
    (0x1F600, 0x1F64F),  # Emoticons
    (0x1F680, 0x1F6FF),  # Transport and map
    (0x1F900, 0x1F9FF),  # Supplemental symbols
    (0x1FA70, 0x1FAFF),  # Symbols extended-A
]

# Simple unicode symbols
_SIMPLE_RANGES = [
    (0x2190, 0x21FF),  # Arrows
    (0x2200, 0x22FF),  # Mathematical operators
    (0x2300, 0x23FF),  # Miscellaneous technical
    (0x25A0, 0x25FF),  # Geometric shapes
    (0x2600, 0x26FF),  # Miscellaneous symbols
    (0x2700, 0x27BF),  # Dingbats
    (0x2B00, 0x2BFF),  # Misc symbols and arrows
]

_COLOR_CACHE: list[tuple[str, str]] | None = None
_SIMPLE_CACHE: list[tuple[str, str]] | None = None


def _get_color_cache():
    global _COLOR_CACHE
    if _COLOR_CACHE is None:
        from wcwidth import wcwidth

        _COLOR_CACHE = []
        for start, end in _COLOR_RANGES:
            for cp in range(start, end + 1):
                ch = chr(cp)
                if wcwidth(ch) != 2:
                    continue
                try:
                    _COLOR_CACHE.append((ch, unicodedata.name(ch).lower()))
                except ValueError:
                    pass
    return _COLOR_CACHE


def _get_simple_cache():
    global _SIMPLE_CACHE
    if _SIMPLE_CACHE is None:
        from wcwidth import wcwidth

        _SIMPLE_CACHE = []
        for start, end in _SIMPLE_RANGES:
            for cp in range(start, end + 1):
                ch = chr(cp)
                if wcwidth(ch) != 1:
                    continue
                try:
                    _SIMPLE_CACHE.append((ch, unicodedata.name(ch).lower()))
                except ValueError:
                    pass
    return _SIMPLE_CACHE


def _search(cache, query, prefix_len):
    results = []
    seen = set()

    if not query:
        for ch, name in cache:
            if ch not in seen:
                seen.add(ch)
                results.append(
                    RichCompletion(
                        ch, display=ch, description=name, prefix_len=prefix_len
                    )
                )
                if len(results) >= 200:
                    break
    else:
        # Prefix matches first
        for ch, name in cache:
            if any(w.startswith(query) for w in name.split()) and ch not in seen:
                seen.add(ch)
                results.append(
                    RichCompletion(
                        ch, display=ch, description=name, prefix_len=prefix_len
                    )
                )
        # Substring matches
        if len(results) < 50:
            for ch, name in cache:
                if query in name and ch not in seen:
                    seen.add(ch)
                    results.append(
                        RichCompletion(
                            ch, display=ch, description=name, prefix_len=prefix_len
                        )
                    )

    return set(results) if results else None


def _find_trigger(raw_prefix, trigger):
    """Find trigger in raw_prefix and return query after it, or None."""
    if not trigger:
        return None
    idx = raw_prefix.find(trigger)
    if idx == -1:
        return None
    return raw_prefix[idx + len(trigger) :].lower()


@contextual_command_completer
def complete_emoji(ctx: CommandContext):
    """Complete emoji and unicode symbols using configurable trigger prefixes."""
    prefix = ctx.prefix
    raw_prefix = ctx.opening_quote + prefix
    env = XSH.env or {}

    symbol_trigger = env.get("XONSH_COMPLETER_SYMBOLS_PREFIX", ":::")
    emoji_trigger = env.get("XONSH_COMPLETER_EMOJI_PREFIX", "::")

    # Check longer trigger first to avoid prefix conflict
    if len(symbol_trigger) >= len(emoji_trigger):
        triggers = [
            (symbol_trigger, _get_simple_cache),
            (emoji_trigger, _get_color_cache),
        ]
    else:
        triggers = [
            (emoji_trigger, _get_color_cache),
            (symbol_trigger, _get_simple_cache),
        ]

    for trigger, get_cache in triggers:
        query = _find_trigger(raw_prefix, trigger)
        if query is not None:
            return _search(get_cache(), query, len(prefix))

    return None
