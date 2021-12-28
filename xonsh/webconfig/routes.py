from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import *

    RouteT = TypeVar("Route", bound="Routes")
import logging

from . import xonsh_data, tags as t
from urllib import parse


class Routes:
    path: str
    registry: "dict[str, Type[RouteT]]" = {}
    navbar = False
    nav_title: "str|None" = None

    def __init__(
        self,
        url: "parse.ParseResult",
        params: "dict[str, list[str]]",
        env=None,
    ):
        self.url = url
        self.params = params
        self.env = env or {}

    def __init_subclass__(cls, **kwargs):
        cls.registry[cls.path] = cls

    def get_nav_links(self):
        for page in self.registry.values():
            klass = []
            if page.path == self.url.path:
                klass.append("active")
            if page.nav_title:
                yield t.nav_item(*klass)[
                    t.nav_link(href=page.path)[page.nav_title],
                ]


class XonshData(Routes):
    path = "/data.json"

    def get(self):
        colors = list(xonsh_data.render_colors())
        prompts = list(xonsh_data.render_prompts())
        return {
            "xontribs": list(xonsh_data.render_xontribs()),
            "colors": colors,
            "prompts": prompts,
            "colorValue": colors[0],
            "promptValue": prompts[0],
        }


class ColorsPage(Routes):
    path = "/"
    nav_title = "Colors"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.colors = dict(xonsh_data.render_colors())

    def to_card(self, name: str, display: str, clickable=False):
        try:
            display = t.etree.fromstring(display)
        except Exception as ex:
            logging.error(f"Failed to parse color-display {ex!r}. {display!r}")
            display = t.pre()[display]
        params = parse.urlencode({"selected": name})
        url = self.path + "?" + params

        title = name
        if clickable:
            title = t.a("stretched-link", href=url)[name]

        return t.card()[
            t.card_body()[
                t.card_title()[title],
                display,
            ],
        ]

    def get_cols(self):
        for name, display in self.colors.items():
            yield t.col_sm()[
                self.to_card(name, display, clickable=True),
            ]

    def get_selected(self):
        selected = self.params.get("selected")
        if selected:
            name = selected[0]
        else:
            name = self.env.get("XONSH_COLOR_STYLE")
        name = name if name in self.colors else "default"
        display = self.colors[name]
        card = self.to_card(name, display)
        # todo: show form to set color
        card.append(
            t.div("card-footer")[
                "Set Color",
            ]
        )
        return t.row()[
            t.div("col")[card],
        ]

    def get(self):
        # banner
        yield self.get_selected()

        yield t.br()
        yield t.br()
        # rest
        cols = list(self.get_cols())
        yield t.row()[cols]


class PromptsPage(Routes):
    path = "/prompts"
    nav_title = "Prompts"

    def get(self):
        return


class XontribsPage(Routes):
    path = "/xontribs"
    nav_title = "Xontribs"

    def get(self):
        return
