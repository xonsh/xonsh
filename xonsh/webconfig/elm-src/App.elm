import Browser

import Html exposing (..)
import Html.Events exposing (onClick)
import Html.Attributes exposing (class, style, href)
import Html.Parser
import Html.Parser.Util
import Http
import Maybe exposing (withDefault)
import Set
import Set exposing (Set)
import List
import String
import Json.Decode
import Json.Decode as Decode
import Json.Encode as Encode
import Bootstrap.Tab as Tab
import Bootstrap.CDN as CDN
import Bootstrap.Card as Card
import Bootstrap.Text as Text
import Bootstrap.Grid as Grid
import Bootstrap.Grid.Row as Row
import Bootstrap.Card.Block as Block
import Bootstrap.Button as Button
import Bootstrap.ListGroup as ListGroup
import XonshData
import XonshData exposing (PromptData, ColorData, XontribData)


-- example with animation, you can drop the subscription part when not using animations
type alias Model =
    { tabState : Tab.State
    , promptValue : PromptData
    , colorValue : ColorData
    , xontribs : (Set String)
    --, response : Maybe PostResponse
    , error : Maybe Http.Error
    }

init : ( Model, Cmd Msg )
init =
    ( { tabState = Tab.initialState
      , promptValue = withDefault {name = "unknown", value = "$ ", display = ""}
                                  (List.head XonshData.prompts)
      , colorValue = withDefault {name = "unknown", display = ""}
                                 (List.head XonshData.colors)
      , xontribs = Set.empty
      --, response = Nothing
      , error = Nothing
      }
    , Cmd.none )

type Msg
    = TabMsg Tab.State
    | PromptSelect PromptData
    | ColorSelect ColorData
    | XontribAdded XontribData
    | XontribRemoved XontribData
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
        ColorSelect value ->
            ( { model | colorValue = value }
            , Cmd.none
            )
        XontribAdded value ->
            ( { model | xontribs = Set.insert value.name model.xontribs }
            , Cmd.none
            )
        XontribRemoved value ->
            ( { model | xontribs = Set.remove value.name model.xontribs }
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
    [ ("prompt", Encode.string model.promptValue.value)
    , ("colors", Encode.string model.colorValue.name)
    , ("xontribs", Encode.set Encode.string model.xontribs)
    ]

saveSettings : Model -> Cmd Msg
saveSettings model =
  Http.post
    { url = "/save"
    , body = Http.stringBody "application/json" (Encode.encode 0 (encodeModel model))
    , expect = Http.expectWhatever Response
    }

-- VIEWS

textHtml : String -> List (Html.Html msg)
textHtml t =
    case Html.Parser.run t of
        Ok nodes ->
            Html.Parser.Util.toVirtualDom nodes

        Err _ ->
            []

promptButton : PromptData -> (ListGroup.CustomItem Msg)
promptButton pd =
    ListGroup.button
        [ ListGroup.attrs [ onClick (PromptSelect pd) ]
        , ListGroup.info
        ]
        [ text pd.name
        , p [] []
        , span [] (textHtml pd.display)
        ]

colorButton : ColorData -> (ListGroup.CustomItem Msg)
colorButton cd =
    ListGroup.button
        [ ListGroup.attrs [ onClick (ColorSelect cd) ]
        , ListGroup.info
        ]
        [ text cd.name
        , p [] []
        , span [] (textHtml cd.display)
        ]


centeredDeck : List (Card.Config msg) -> Html.Html msg
centeredDeck cards =
    Html.div
        [ class "card-deck justify-content-center" ]
        (List.map Card.view cards)

xontribCard : Model -> XontribData -> Card.Config Msg
xontribCard model xd =
    Card.config [ Card.attrs
                    [ style "min-width" "20em"
                    , style "max-width" "20em"
                    , style "padding" "0.25em"
                    , style "margin" "0.5em"
                    ] ]
        |> Card.headerH3 [] [ a [href xd.url] [ text xd.name ] ]
        |> Card.block [] [ Block.text [] ( textHtml xd.description ) ]
        |> Card.footer []
            [ if Set.member xd.name model.xontribs then
                Button.button [ Button.danger
                , Button.attrs [ onClick (XontribRemoved xd) ]
                ] [ text "Remove" ]
                else
                Button.button [ Button.success
                , Button.attrs [ onClick (XontribAdded xd) ]
                ] [ text "Add" ]
            ]

view : Model -> Html Msg
view model =
    div [style "padding" "0.75em 1.25em"]
        [ Grid.container []
            [ Grid.row []
                [ Grid.col [] [ div [ style "text-align" "left"] [ h2 [] [text "xonsh"] ] ]
                , Grid.col [] [ div [ style "text-align" "right"]
                                [ Button.button [ Button.success
                                , Button.attrs [ onClick SaveClicked ]
                                ] [ text "Save" ]
                              ] ]
                ]
            ]
        , p [] []
        , Tab.config TabMsg
            |> Tab.center
            |> Tab.items
                [ Tab.item
                    { id = "tabItemColors"
                    , link = Tab.link [] [ text "Colors" ]
                    , pane = Tab.pane []
                        [ text ("Current Selection: " ++ model.colorValue.name)
                        , p [] []
                        , div [style "padding" "0.75em 1.25em"] (textHtml model.colorValue.display)
                        , ListGroup.custom (List.map colorButton XonshData.colors)
                        ]
                    }
                , Tab.item
                    { id = "tabItemPrompt"
                    , link = Tab.link [] [ text "Prompt" ]
                    , pane = Tab.pane []
                        [ text ("Current Selection: " ++ model.promptValue.name)
                        , p [] []
                        , div [style "padding" "0.75em 1.25em"] (textHtml model.promptValue.display)
                        , ListGroup.custom (List.map promptButton XonshData.prompts)
                        ]
                    }
                , Tab.item
                    { id = "tabItemXontribs"
                    , link = Tab.link [] [ text "Xontribs" ]
                    , pane = Tab.pane [] [ centeredDeck (List.map (xontribCard model) XonshData.xontribs) ]
                    }
                ]
            |> Tab.view model.tabState
        ]


main : Program Decode.Value Model Msg
main =
  Browser.element
        { init = \_ -> init
        , view = view
        , update = update
        , subscriptions = \_ -> Sub.none
        }
