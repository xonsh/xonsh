# AI Prompt I/O Log — claude

This directory tracks prompt inputs and model
outputs for AI-assisted development using
`claude` (Claude Code CLI).

## Policy

Prompt logging follows the
[NLNet generative AI policy][nlnet-ai].
All substantive AI contributions are logged
with:
- Model name and version
- Timestamps
- The prompts that produced the output
- Unedited model output (`.raw.md` files)

[nlnet-ai]: https://nlnet.nl/foundation/policies/generativeAI/

## Usage

Entries are created by the `/prompt-io` skill
or automatically via `/commit-msg` integration.

Human contributors remain accountable for all
code decisions. AI-generated content is never
presented as human-authored work.
