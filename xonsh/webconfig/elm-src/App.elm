import Browser

import Html exposing (..)
import Json.Decode
import Json.Decode as Decode
import Json.Encode as Encode
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

view : Model -> Html Msg
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


main : Program Decode.Value Model Msg
main =
  Browser.element
        { init = \_ -> init
        , view = view
        , update = update
        , subscriptions = \_ -> Sub.none
        }
