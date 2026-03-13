# PR: Fix #6141 - Underline matching substring in completion menu

## Summary
This PR implements visual indication for completion matches that occur in the middle of completion text (not at the start). When a user types a prefix that matches a substring within a completion option, the matching portion is now underlined in the completion menu.

## Problem
Issue #6141: When typing a prefix like "book", completions like "ebook" and "notebook" are shown, but there's no visual indication of *where* in the completion text the match occurs. This can be confusing for users, especially with fuzzy or substring matching.

## Solution
Modified `xonsh/shells/ptk_shell/completer.py` to:
1. Added `_create_styled_display()` function that analyzes where the prefix matches in each completion
2. When the match occurs in the middle (position > 0), the function returns a `FormattedText` object with the matching substring styled with `underline`
3. When the match is at the start (position == 0) or there's no match, returns plain text (no styling)
4. Integrated this function into the `get_completions()` method for both `RichCompletion` and plain string completions

## Example
When user types `book`:
- `ebook` → displayed as `e`<u>`book`</u> (underline on "book")
- `bookkeeper` → displayed as `bookkeeper` (no underline, match at start)
- `notebook` → displayed as `note`<u>`book`</u> (underline on "book")

## Changes
- **xonsh/shells/ptk_shell/completer.py**:
  - Added import for `FormattedText` from `prompt_toolkit.formatted_text`
  - Added `_create_styled_display()` helper function
  - Modified `get_completions()` to use styled display for completions

- **tests/shell/test_ptk_completer.py**:
  - Added `test_completion_underline_match_in_middle()` test case

## Testing
All existing tests pass:
```bash
pytest tests/shell/test_ptk_completer.py -v
# 28 passed in 0.23s
```

New test specifically validates:
- Matches in the middle are underlined
- Matches at the start have no underline
- Matches at the end are underlined correctly

## Compatibility
- Requires `prompt_toolkit >= 3.0.29` (already a dependency)
- No breaking changes - purely visual enhancement
- Backward compatible: completions without matches display normally

## Future Enhancements
This implementation lays the groundwork for more advanced completion styling, such as:
- Fuzzy match highlighting (multiple non-contiguous segments)
- Color-coded match types
- Bold styling for exact prefix matches
