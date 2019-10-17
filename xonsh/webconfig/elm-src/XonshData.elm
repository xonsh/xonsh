-- A collection of xonsh values for the web-ui
module XonshData exposing (..)

import List
import String

type alias PromptData =
    { name : String
    , value : String
    }

prompts : List PromptData
prompts =
    [ {name = "Just a Dollar", value = "$ "}
    , {name = "Just a Hash", value = "# "}
    ]
