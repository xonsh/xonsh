from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Type

import logging

from . import xonsh_data, tags as t
from urllib import parse


class Routes:
    path: str
    registry: "dict[str, Type[Routes]]" = {}
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

    @staticmethod
    def get_display(display):
        try:
            display = t.etree.fromstring(display)
        except Exception as ex:
            logging.error(f"Failed to parse color-display {ex!r}. {display!r}")
            display = t.pre()[display]
        return display

    def to_card(self, name: str, display: str, clickable=False, header=""):
        params = parse.urlencode({"selected": name})
        url = self.path + "?" + params

        title = name
        if clickable:
            title = t.a("stretched-link", href=url)[name]

        card = t.card()

        if header:
            card.append(t.card_header()[header])

        card.append(
            t.card_body()[
                t.card_title()[title],
                self.get_display(display),
            ]
        )
        return card


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

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.prompts = dict(xonsh_data.render_prompts())

    def get_selected(self):
        name = "default"
        selected = self.params.get("selected")
        if selected:
            name = selected[0]
        name = name if name in self.prompts else "default"

        prompt = self.prompts[name]
        card = self.to_card(name, prompt["display"])
        return t.row()[
            t.col()[card],
        ]

    def get_cols(self):
        for name, prompt in self.prompts.items():
            yield t.row()[
                t.col()[
                    self.to_card(name, prompt["display"], clickable=True),
                ]
            ]

    def get(self):
        # banner
        yield self.get_selected()

        yield t.br()
        yield t.br()
        # rest
        yield from self.get_cols()


class XontribsPage(Routes):
    path = "/xontribs"
    nav_title = "Xontribs"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.xontribs = dict(xonsh_data.render_xontribs())

    def xontrib_card(self, name, data):
        # todo: button to remove/add
        title = t.a(href=data["url"])[name]
        display = data["display"]
        header = t.card_header()[
            title,
            t.btn_primary("ml-2", "p-1")["Add"],
        ]
        return t.card()[
            header,
            t.card_body()[
                self.get_display(display),
            ],
        ]

    def get(self):
        for name, data in self.xontribs.items():
            yield t.row()[
                t.col()[
                    self.xontrib_card(name, data),
                ]
            ]
            yield t.br()
