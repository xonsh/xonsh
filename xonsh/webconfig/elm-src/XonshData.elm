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
    [ {name = "Just a Dollar", value = "$ ", display = "<div class=\"highlight\" style=\"background: #272822\"><pre style=\"line-height: 125%\"><span></span><span style=\"color: #f8f8f2\">print(</span><span style=\"color: #e6db74\">&quot;Hello World&quot;</span><span style=\"color: #f8f8f2\">)</span></pre></div>"}
    , {name = "Just a Hash", value = "# ", display = "<div></div>"}
    ]
