import Browser

import Html exposing (..)
import Html.Events exposing (onClick)
import Http
import String
import Json.Decode
import Json.Decode as Decode
import Json.Encode as Encode
import Bootstrap.Tab as Tab
import Bootstrap.CDN as CDN
import Bootstrap.Grid as Grid
import Bootstrap.Button as Button
import Bootstrap.ListGroup as ListGroup
import XonshData

-- example with animation, you can drop the subscription part when not using animations
type alias Model =
    { tabState : Tab.State
    , promptValue : String
    --, response : Maybe PostResponse
    , error : Maybe Http.Error
    }

init : ( Model, Cmd Msg )
init =
    ( { tabState = Tab.initialState
      , promptValue = "$"
      --, response = Nothing
      , error = Nothing
      }
    , Cmd.none )

type Msg
    = TabMsg Tab.State
    | PromptSelect String
    | SaveClicked
    | Response (Result Http.Error ())

update : Msg -> Model -> ( Model, Cmd Msg )
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
        SaveClicked ->
        --    ( { model | error = Nothing, response = Nothing }
            ( { model | error = Nothing}
            , saveSettings model
            )
        Response (Ok response) ->
            --( { model | error = Nothing, response = Just response }, Cmd.none )
            ( { model | error = Nothing }, Cmd.none )
        Response (Err error) ->
            --( { model | error = Just error, response = Nothing }, Cmd.none )
            ( { model | error = Just error }, Cmd.none )

encodeModel : Model -> Encode.Value
encodeModel model =
    Encode.object
    [ ("prompt", Encode.string model.promptValue)
    ]

saveSettings : Model -> Cmd Msg
saveSettings model =
  Http.post
    { url = "/save"
    , body = Http.stringBody "application/json" (Encode.encode 0 (encodeModel model))
    , expect = Http.expectWhatever Response
    }

promptButton : String -> (ListGroup.CustomItem Msg)
promptButton value =
    ListGroup.button
        [ ListGroup.attrs [ onClick (PromptSelect value) ]
        , ListGroup.info
        ]
        [ text ("Prompt: " ++ value) ]

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
                    , p [] []
                    , ListGroup.custom (List.map promptButton XonshData.prompts)
                    , p [] []
                    , Button.button [ Button.info
                                    , Button.attrs [ onClick SaveClicked ]
                                    ] [ text "Save" ]
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
