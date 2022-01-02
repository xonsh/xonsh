from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Type, Any

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

    def to_card(self, name: str, display: str, clickable=False, header=()):
        params = parse.urlencode({"selected": name})
        url = self.path + "?" + params

        def get_body():
            if not header:
                body_title = name
                if clickable:
                    body_title = t.a("stretched-link", href=url)[name]
                yield t.card_title()[body_title]
            yield self.get_display(display)

        card = t.card()

        if header:
            card.append(t.card_header()[header])

        card.append(t.card_body()[get_body()])
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
        self.var_name = "XONSH_COLOR_STYLE"

    def get_cols(self):
        for name, display in self.colors.items():
            yield t.col_sm()[
                self.to_card(name, display, clickable=True),
            ]

    def get_selected(self):
        selected = self.params.get("selected")
        current = self.env.get(self.var_name)
        if selected and selected != current:
            name = selected[0]
            # update env-variable
            form = t.inline_form(method="post")[
                t.btn_primary("ml-2", "p-1", type="submit", name=self.var_name)[
                    f"Update ${self.var_name}",
                ],
            ]
            header = (
                f"Selected: {name}",
                form,
            )
        else:
            name = current
            header = (f"Current: {name}",)
        name = name if name in self.colors else "default"
        display = self.colors[name]

        card = self.to_card(name, display, header=header)
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

    def post(self, _):
        selected = self.params.get("selected")
        if selected:
            self.env[self.var_name] = selected[0]
        # todo: update rc file


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
        return self.to_card(
            name,
            data["display"],
            header=(
                title,
                t.btn_primary("ml-2", "p-1")["Load"],
            ),
        )

    def get(self):
        for name, data in self.xontribs.items():
            yield t.row()[
                t.col()[
                    self.xontrib_card(name, data),
                ]
            ]
            yield t.br()


class EnvVariablesPage(Routes):
    path = "/vars"
    # nav_title = ""

    def post(self):
        return
