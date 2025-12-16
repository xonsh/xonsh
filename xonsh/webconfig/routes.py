import logging
import sys
from urllib import parse

from xonsh.built_ins import XonshSession
from xonsh.environ import Env

from . import tags as t
from . import xonsh_data
from .file_writes import insert_into_xonshrc


class Routes:
    path: str
    registry: "dict[str, type[Routes]]" = {}
    navbar = False
    nav_title: "str|None" = None
    err_msgs: "list" = []
    """session storage for error messages"""

    def __init__(
        self,
        url: "parse.ParseResult",
        params: "dict[str, list[str]]",
        xsh: "XonshSession",
    ):
        self.url = url
        self.params = params
        self.env: Env = xsh.env
        self.xsh = xsh

    def __init_subclass__(cls, **kwargs):
        cls.registry[cls.path] = cls

    def err(self, msg: str):
        html = xonsh_data.rst_to_html(msg)
        tree = t.etree.fromstring(html)
        self.err_msgs.append(tree)

    def get_nav_links(self):
        for page in self.registry.values():
            klass = []
            if page.path == self.url.path:
                klass.append("active")

            title = page.nav_title() if callable(page.nav_title) else page.nav_title
            if title:
                yield t.nav_item(*klass)[t.nav_link(href=page.path)[title],]

    def get_err_msgs(self):
        if not self.err_msgs:
            return
        for msg in self.err_msgs:
            yield t.alert("alert-danger")[msg]
        self.err_msgs.clear()

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

    def update_rc(self, **kwargs):
        # todo: handle updates and deletion as well
        insert_into_xonshrc(kwargs)


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
            yield t.col_sm()[self.to_card(name, display),]

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

        return t.row()[t.col()[card],]

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
            self.update_rc(color=selected[0])


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
        return "Current: ", None

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
        txt_area = t.textarea(
            "form-control",
            name=self.var_name,
            rows=str(len(prompt.splitlines())),
        )[prompt]

        card = t.card()[
            t.card_header()[header],
            t.card_body()[
                t.card_title()["Edit"],
                txt_area,
                t.br(),
                t.card_title()["Preview"],
                t.p("text-muted")[
                    "It is not a live preview. `Set` to get the updated view."
                ],
                self.get_display(display),
            ],
            t.card_footer("py-1")[t.btn_primary("py-1", type="submit")["Set",],],
        ]
        return t.row()[t.col()[t.form(method="post")[card]],]

    def get_cols(self):
        for name, prompt in self.prompts.items():
            yield t.row()[t.col()[self.to_card(name, prompt["display"]),]]

    def get(self):
        # banner
        yield self.get_selected()

        yield t.br()
        yield t.br()
        # rest
        yield from self.get_cols()

    def post(self, data: dict[str, str]):
        if prompt := data.get(self.var_name):
            prompt = prompt.replace("\r", "")
            self.env[self.var_name] = prompt
            self.update_rc(prompt=prompt)


class XontribsPage(Routes):
    path = "/xontribs"
    nav_title = "Xontribs"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.xontribs = dict(xonsh_data.render_xontribs())

    @staticmethod
    def mod_name(name):
        return f"xontrib.{name}"

    @staticmethod
    def is_loaded(name):
        return XontribsPage.mod_name(name) in sys.modules

    def xontrib_card(self, name, data):
        from xonsh.xontribs import find_xontrib

        title = t.a(href=data["url"])[name]
        if find_xontrib(name):
            act_label = "Add"
            if self.is_loaded(name):
                act_label = "Remove"
            action = t.inline_form(method="post")[
                t.btn_primary("ml-2", "p-1", type="submit", name=name)[act_label,],
            ]
        else:
            title = title("stretched-link")  # add class
            action = ""
        return t.card()[
            t.card_header()[title, action],
            t.card_body()[self.get_display(data["display"]),],
        ]

    def get(self):
        yield t.card()[
            t.card_body()[
                t.card_title()["Popular xontrib sources"],
                t.card_body()[
                    t.li()[
                        t.a(href="https://github.com/topics/xontrib")[
                            "Xontribs on Github"
                        ]
                    ],
                    t.li()[
                        t.a(href="https://github.com/xonsh/awesome-xontribs")[
                            "Awesome xontribs"
                        ]
                    ],
                    t.li()[
                        t.a(
                            href="https://xon.sh/api/_autosummary/xontribs/xontrib.html"
                        )["Core xontribs"]
                    ],
                    t.li()[
                        t.a(href="https://github.com/xonsh/xontrib-template")[
                            "Create a xontrib step by step from template"
                        ]
                    ],
                ],
            ]
        ]
        yield t.br()
        for name, data in self.xontribs.items():
            yield t.row()[t.col()[self.xontrib_card(name, data),]]
            yield t.br()

    def post(self, data: dict[str, str]):
        if not data:
            return
        name = list(data)[0]
        if self.is_loaded(name):
            # todo: update rc file
            del sys.modules[self.mod_name(name)]
        else:
            from xonsh.xontribs import xontribs_load

            _, err, _ = xontribs_load([name])
            if err:
                self.err(err)
            else:
                self.update_rc(xontribs=[name])


class EnvVariablesPage(Routes):
    path = "/vars"
    nav_title = "Variables"

    def get_header(self):
        yield t.tr()[
            t.th("text-right")["Name"],
            t.th()["Value"],
        ]

    def get_rows(self):
        for name in sorted(self.env.keys()):
            if not self.env.is_configurable(name):
                continue
            value = self.env[name]
            envvar = self.env.get_docs(name)
            html = xonsh_data.rst_to_html(envvar.doc)
            yield t.tr()[
                t.td("text-right")[str(name)],
                t.td()[
                    t.p()[repr(value)],
                    t.small()[self.get_display(html)],
                ],
            ]

    def get_table(self):
        rows = list(self.get_rows())
        yield t.tbl("table-striped")[
            self.get_header(),
            rows,
        ]

    def get(self):
        yield t.div("table-responsive")[self.get_table()]


class AliasesPage(Routes):
    path = "/alias"
    nav_title = "Aliases"

    def get_header(self):
        yield t.tr()[
            t.th("text-right")["Name"],
            t.th()["Value"],
        ]

    def get_rows(self):
        if not self.xsh.aliases:
            return
        for name in sorted(self.xsh.aliases.keys()):
            alias = self.xsh.aliases[name]
            if callable(alias):
                continue
            # todo:
            #  1. do not edit default aliases as well
            #  2. way to update string aliases

            yield t.tr()[
                t.td("text-right")[str(name)],
                t.td()[t.p()[repr(alias)],],
            ]

    def get_table(self):
        rows = list(self.get_rows())
        yield t.tbl("table-sm", "table-striped")[
            self.get_header(),
            rows,
        ]

    def get(self):
        yield t.div("table-responsive")[self.get_table()]
