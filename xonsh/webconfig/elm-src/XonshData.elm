-- A collection of xonsh values for the web-ui
module XonshData exposing (..)

import List
import String

type alias PromptData =
    { name : String
    , value : String
    , display : String
    }

prompts : List PromptData
prompts =
    [ { name = "Default", value = "{env_name}{BOLD_GREEN}{user}@{hostname}{BOLD_BLUE} {cwd}{gitstatus: {}}{NO_COLOR} {BOLD_BLUE}{prompt_end}{NO_COLOR} ", display = "<div class=\"highlight\" style=\"background: #f8f8f8\"><pre style=\"line-height: 125%\"><span></span>{env_name}{user}@{hostname} {cwd}{gitstatus: {}} {prompt_end} </pre></div>" }
    , { name = "Just a Dollar", value = "$ ", display = "<div class=\"highlight\" style=\"background: #f8f8f8\"><pre style=\"line-height: 125%\"><span></span>$ </pre></div>" }
    ]
