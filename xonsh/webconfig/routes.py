import cgi
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

    def get_sel_url(self, name):
        params = parse.urlencode({"selected": name})
        return self.path + "?" + params

    @staticmethod
    def get_display(display):
        try:
            display = t.etree.fromstring(display)
        except Exception as ex:
            logging.error(f"Failed to parse color-display {ex!r}. {display!r}")
            display = t.pre()[display]
        return display


class ColorsPage(Routes):
    path = "/"
    nav_title = "Colors"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.colors = dict(xonsh_data.render_colors())
        self.var_name = "XONSH_COLOR_STYLE"

    def to_card(self, name: str, display: str):
        return t.card()[
            t.card_body()[
                t.card_title()[
                    t.a("stretched-link", href=self.get_sel_url(name))[name]
                ],
                self.get_display(display),
            ]
        ]

    def get_cols(self):
        for name, display in self.colors.items():
            yield t.col_sm()[
                self.to_card(name, display),
            ]

    def _get_selected_header(self):
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
            return (f"Selected: {name}", form), name
        return (f"Current: {current}",), current

    def get_selected(self):
        header, name = self._get_selected_header()
        name = name if name in self.colors else "default"
        display = self.colors[name]

        card = t.card()[
            t.card_header()[header],
            t.card_body()[self.get_display(display)],
        ]

        return t.row()[
            t.col()[card],
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
        prompts = xonsh_data.render_prompts(self.env)
        self.current = next(prompts)
        self.prompts = dict(prompts)
        self.var_name = "PROMPT"
        # todo: support updating RIGHT_PROMPT, BOTTOM_TOOLBAR

    def to_card(self, name: str, display: str):
        return t.card()[
            t.card_body()[
                t.card_title()[
                    t.a("stretched-link", href=self.get_sel_url(name))[name]
                ],
                self.get_display(display),
            ]
        ]

    def _get_selected_header(self):
        ps_names = self.params.get("selected")
        if ps_names:
            name = ps_names[0]
            if name in self.prompts:
                return f"Selected: {name}", name
        return f"Current: ", None

    def get_selected(self):
        header, cur_sel = self._get_selected_header()
        if cur_sel is None:
            prompt = self.current["value"]
            display = self.current["display"]
        else:
            cont = self.prompts[cur_sel]
            prompt: str = cont["value"]
            display = cont["display"]
        # update env-variable
        input = t.textarea(
            "form-control",
            name=self.var_name,
            rows=str(len(prompt.splitlines())),
        )[prompt]

        card = t.card()[
            t.card_header()[header],
            t.card_body()[
                t.card_title()["Edit"],
                input,
                t.br(),
                t.card_title()["Preview"],
                t.p("text-muted")[
                    "It is not a live preview. Click `Set` to get the updated view."
                ],
                self.get_display(display),
            ],
            t.card_footer("py-1")[
                t.btn_primary("py-1", type="submit")[
                    f"Set",
                ],
            ],
        ]
        return t.row()[
            t.col()[t.form(method="post")[card]],
        ]

    def get_cols(self):
        for name, prompt in self.prompts.items():
            yield t.row()[
                t.col()[
                    self.to_card(name, prompt["display"]),
                ]
            ]

    def get(self):
        # banner
        yield self.get_selected()

        yield t.br()
        yield t.br()
        # rest
        yield from self.get_cols()

    def post(self, data: "cgi.FieldStorage"):
        if data:
            self.env[self.var_name] = data.getvalue(self.var_name)
        # todo: update rc file


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
