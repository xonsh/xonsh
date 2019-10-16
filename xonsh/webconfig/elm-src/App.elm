module Main exposing (main)

import Html exposing (..)
import Bootstrap.Tab as Tab
import Bootstrap.CDN as CDN
import Bootstrap.Grid as Grid

-- example with animation, you can drop the subscription part when not using animations
type alias Model =
    { tabState : Tab.State }

init : ( Model, Cmd Msg )
init =
    ( { tabState = Tab.initialState }, Cmd.none )

type Msg
    = TabMsg Tab.State

update : Msg -> Model -> ( Model, Cmd msg )
update msg model =
    case msg of
        TabMsg state ->
            ( { model | tabState = state }
            , Cmd.none
            )

view : Model -> Html msg
view model =
    Tab.config TabMsg
        --|> Tab.withAnimation
        -- remember to wire up subscriptions when using this option
        |> Tab.right
        |> Tab.items
            [ Tab.item
                { id = "tabItem1"
                , link = Tab.link [] [ text "Tab 1" ]
                , pane = Tab.pane [] [ text "Tab 1 Content" ]
                }
            , Tab.item
                { id = "tabItem2"
                , link = Tab.link [] [ text "Tab 2" ]
                , pane = Tab.pane [] [ text "Tab 2 Content" ]
                }
            ]
        |> Tab.view model.tabState

--main =
--    Grid.container []
--        [ CDN.stylesheet -- creates an inline style node with the Bootstrap CSS
--       , view
        --Grid.row []
        --    [ Grid.col []
        --       [ text "Some content for my view here..."]
        --    , Grid.col [] [view tabState]
        --    ]
--        ]

main = view