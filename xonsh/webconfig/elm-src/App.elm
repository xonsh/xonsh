import Browser

import Html exposing (..)
import Html.Events exposing (onClick)
import String
import Json.Decode
import Json.Decode as Decode
import Json.Encode as Encode
import Bootstrap.Tab as Tab
import Bootstrap.CDN as CDN
import Bootstrap.Grid as Grid
import Bootstrap.ListGroup as ListGroup

-- example with animation, you can drop the subscription part when not using animations
type alias Model =
    { tabState : Tab.State
    , promptValue : String
    }

init : ( Model, Cmd Msg )
init =
    ( { tabState = Tab.initialState
      , promptValue = "$"
      }
    , Cmd.none )

type Msg
    = TabMsg Tab.State
    | PromptSelect String

update : Msg -> Model -> ( Model, Cmd msg )
update msg model =
    case msg of
        TabMsg state ->
            ( { model | tabState = state }
            , Cmd.none
            )
        PromptSelect value ->
            ( { model | promptValue = value }
            , Cmd.none
            )

view : Model -> Html Msg
view model =
    Tab.config TabMsg
        --|> Tab.withAnimation
        -- remember to wire up subscriptions when using this option
        |> Tab.center
        |> Tab.items
            [ Tab.item
                { id = "tabItemPrompt"
                , link = Tab.link [] [ text "Prompt" ]
                , pane = Tab.pane [] [
                    text ("Current Prompt: " ++ model.promptValue)
                    , ListGroup.custom [
                        ListGroup.button
                            [ ListGroup.attrs [ onClick (PromptSelect "$") ]
                            , ListGroup.info
                            ]
                            [ text "List item 1" ]
                        , ListGroup.button
                            [ ListGroup.attrs [ onClick (PromptSelect "#") ]
                            , ListGroup.warning
                            ]
                            [ text "List item 2" ]
                    ]
                ]
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
