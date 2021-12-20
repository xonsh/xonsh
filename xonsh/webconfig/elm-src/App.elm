module App exposing (Model)

import Bootstrap.Button as Button
import Bootstrap.Card as Card
import Bootstrap.Card.Block as Block
import Bootstrap.Grid as Grid
import Bootstrap.ListGroup as ListGroup
import Bootstrap.Tab as Tab
import Browser
import Html exposing (..)
import Html.Attributes exposing (class, href, style)
import Html.Events exposing (onClick)
import Html.Parser
import Html.Parser.Util
import Http
import Json.Decode as Decode exposing (Decoder, Error(..))
import Json.Encode as Encode
import List
import Set exposing (Set)
import XonshData exposing (ColorData, PromptData, XontribData)


type alias Model =
    { tabState : Tab.State
    , prompts : List PromptData
    , xontribs : List XontribData
    , colors : List ColorData
    , promptValue : PromptData
    , colorValue : ColorData
    , xontribValue : Set String
    , errorMessage : Maybe String
    , error : Maybe Http.Error
    }


init : ( Model, Cmd Msg )
init =
    ( { tabState = Tab.initialState
      , prompts = []
      , xontribs = []
      , colors = []
      , promptValue =
            { name = "unknown", value = "$ ", display = "" }
      , colorValue =
            { name = "unknown", display = "" }
      , xontribValue = Set.empty
      , errorMessage = Nothing
      , error = Nothing
      }
    , Cmd.none
    )


type Msg
    = TabMsg Tab.State
    | PromptSelect PromptData
    | ColorSelect ColorData
    | XontribAdded XontribData
    | XontribRemoved XontribData
    | SaveClicked
    | Response (Result Http.Error ())
    | SendHttpRequest
    | DataReceived (Result Http.Error XonshData.RemoteData)


url =
    "/data.json"


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
            ( { model | xontribValue = Set.insert value.name model.xontribValue }
            , Cmd.none
            )

        XontribRemoved value ->
            ( { model | xontribValue = Set.remove value.name model.xontribValue }
            , Cmd.none
            )

        SaveClicked ->
            --    ( { model | error = Nothing, response = Nothing }
            ( { model | error = Nothing }
            , saveSettings model
            )

        Response (Ok _) ->
            --( { model | error = Nothing, response = Just response }, Cmd.none )
            ( { model | error = Nothing }, Cmd.none )

        Response (Err error) ->
            --( { model | error = Just error, response = Nothing }, Cmd.none )
            ( { model | error = Just error }, Cmd.none )

        SendHttpRequest ->
            ( model, getRemoteData )

        DataReceived (Ok data) ->
            let
                xontrib =
                    Set.fromList data.xontribValue
            in
            ( { model
                | xontribs = data.xontribs
                , colors = data.colors
                , prompts = data.prompts
                , promptValue = data.promptValue
                , xontribValue = xontrib
                , colorValue = data.colorValue
              }
            , Cmd.none
            )

        DataReceived (Err err) ->
            -- todo: alert error
            let
                errmsg =
                    Debug.log "err" (buildErrorMessage err)

                newModel =
                    { model
                        | errorMessage = Just errmsg
                    }
            in
            ( newModel, Cmd.none )


buildErrorMessage : Http.Error -> String
buildErrorMessage httpError =
    case httpError of
        Http.BadUrl message ->
            message

        Http.Timeout ->
            "Server is taking too long to respond. Please try again later."

        Http.NetworkError ->
            "Unable to reach server."

        Http.BadStatus statusCode ->
            "Request failed with status code: " ++ String.fromInt statusCode

        Http.BadBody message ->
            message


getRemoteData : Cmd Msg
getRemoteData =
    Http.get
        { url = url
        , expect = Http.expectJson DataReceived XonshData.remoteDataDecoder
        }


encodeModel : Model -> Encode.Value
encodeModel model =
    Encode.object
        [ ( "prompt", Encode.string model.promptValue.value )
        , ( "colors", Encode.string model.colorValue.name )
        , ( "xontribs", Encode.set Encode.string model.xontribValue )
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


promptButton : PromptData -> ListGroup.CustomItem Msg
promptButton pd =
    ListGroup.button
        [ ListGroup.attrs [ onClick (PromptSelect pd) ]
        , ListGroup.info
        ]
        [ text pd.name
        , p [] []
        , span [] (textHtml pd.display)
        ]



--colorButton : ColorData -> ListGroup.CustomItem Msg


colorButton cd =
    let
        display =
            Debug.log "color" (textHtml cd.display)
    in
    Card.config [ Card.secondary, Card.attrs [] ]
        |> Card.header [ class "text-center" ]
            [ h3 [] [ text cd.name ]
            ]
        |> Card.block []
            [ Block.custom <| span [] display
            , Block.custom <|
                Button.button [ Button.primary, Button.attrs [ onClick (ColorSelect cd) ] ] [ text "Select" ]
            ]
        |> Card.view



-- textHtml cd.display


centeredDeck : List (Card.Config msg) -> Html.Html msg
centeredDeck cards =
    Html.div
        [ class "card-deck justify-content-center" ]
        (List.map Card.view cards)


xontribCard : Model -> XontribData -> Card.Config Msg
xontribCard model xd =
    Card.config
        [ Card.attrs
            [ style "min-width" "20em"
            , style "max-width" "20em"
            , style "padding" "0.25em"
            , style "margin" "0.5em"
            ]
        ]
        |> Card.headerH3 [] [ a [ href xd.url ] [ text xd.name ] ]
        |> Card.block [] [ Block.text [] (textHtml xd.description) ]
        |> Card.footer []
            [ if Set.member xd.name model.xontribValue then
                Button.button
                    [ Button.danger
                    , Button.attrs [ onClick (XontribRemoved xd) ]
                    ]
                    [ text "Remove" ]

              else
                Button.button
                    [ Button.success
                    , Button.attrs [ onClick (XontribAdded xd) ]
                    ]
                    [ text "Add" ]
            ]


view : Model -> Html Msg
view model =
    div [ style "padding" "0.75em 1.25em" ]
        [ Grid.container []
            [ Grid.row []
                [ Grid.col [] [ div [ style "text-align" "left" ] [ h2 [] [ text "xonsh" ] ] ]
                , Grid.col []
                    [ div [ style "text-align" "right" ]
                        [ Button.button
                            [ Button.success
                            , Button.attrs [ onClick SaveClicked ]
                            ]
                            [ text "Save" ]
                        ]
                    ]
                , Grid.col []
                    [ div [ style "text-align" "right" ]
                        [ Button.button
                            [ Button.success
                            , Button.attrs [ onClick SendHttpRequest ]
                            ]
                            [ text "Reload" ]
                        ]
                    ]
                ]
            ]
        , p [] []
        , Tab.config TabMsg
            |> Tab.center
            |> Tab.items
                [ Tab.item
                    { id = "tabItemColors"
                    , link = Tab.link [] [ text "Colors" ]
                    , pane =
                        Tab.pane []
                            [ text ("Current Selection: " ++ model.colorValue.name)
                            , p [] []
                            , div [ style "padding" "0.75em 1.25em" ] (textHtml model.colorValue.display)
                            , div [] (List.map colorButton model.colors)
                            ]
                    }
                , Tab.item
                    { id = "tabItemPrompt"
                    , link = Tab.link [] [ text "Prompt" ]
                    , pane =
                        Tab.pane []
                            [ text ("Current Selection: " ++ model.promptValue.name)
                            , p [] []
                            , div [ style "padding" "0.75em 1.25em" ] (textHtml model.promptValue.display)
                            , ListGroup.custom (List.map promptButton model.prompts)
                            ]
                    }
                , Tab.item
                    { id = "tabItemXontribs"
                    , link = Tab.link [] [ text "Xontribs" ]
                    , pane = Tab.pane [] [ centeredDeck (List.map (xontribCard model) model.xontribs) ]
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
