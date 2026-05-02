"""Smoke tests for ``xonsh.webconfig.routes``.

The route classes back individual pages of the browser-based xonsh config
UI. Each tests instantiates a route and exercises the ``get`` / ``post``
methods through their pure HTML-rendering paths — without ever spinning up
the SocketServer.
"""

from urllib import parse

import pytest

from xonsh.webconfig import routes as r
from xonsh.webconfig import tags as t


def _url(path):
    return parse.urlparse(path)


@pytest.fixture
def make_route(xession):
    """Factory that constructs a route instance with the right deps."""

    def _factory(cls, params=None, path=None):
        return cls(
            url=_url(path or cls.path),
            params=params or {},
            xsh=xession,
        )

    return _factory


# --- Routes registry --------------------------------------------------------


def test_routes_registry_includes_known_paths():
    paths = set(r.Routes.registry)
    assert "/" in paths
    assert "/prompts" in paths
    assert "/xontribs" in paths
    assert "/vars" in paths
    assert "/alias" in paths


def test_route_registry_subclassing_registers_new_paths():
    class _MyPage(r.Routes):
        path = "/_test_only_xyz"

    try:
        assert "/_test_only_xyz" in r.Routes.registry
        assert r.Routes.registry["/_test_only_xyz"] is _MyPage
    finally:
        r.Routes.registry.pop("/_test_only_xyz", None)


# --- ColorsPage -------------------------------------------------------------


def test_colors_page_renders_html(make_route):
    page = make_route(r.ColorsPage)
    out = t.to_str(list(page.get()))
    assert "<div" in out
    # the page renders its color cards as <div class="row"> wrappers
    assert "row" in out


def test_colors_page_post_updates_env_var(xession, make_route):
    page = make_route(r.ColorsPage, params={"selected": ["monokai"]})
    page.post(None)
    assert xession.env.get("XONSH_COLOR_STYLE") == "monokai"


def test_colors_page_post_no_selection_is_noop(xession, make_route):
    """When no ``selected`` param is provided, post() does nothing."""
    original = xession.env.get("XONSH_COLOR_STYLE")
    page = make_route(r.ColorsPage)
    page.post(None)
    assert xession.env.get("XONSH_COLOR_STYLE") == original


def test_colors_page_get_selected_returns_tag(make_route):
    page = make_route(r.ColorsPage, params={"selected": ["monokai"]})
    out = t.to_str(page.get_selected())
    assert "<div" in out


# --- PromptsPage ------------------------------------------------------------


def test_prompts_page_renders_html(make_route):
    page = make_route(r.PromptsPage)
    out = t.to_str(list(page.get()))
    assert "<div" in out
    assert "form" in out  # the editor form is part of the page


def test_prompts_page_post_updates_prompt(xession, make_route):
    page = make_route(r.PromptsPage)
    page.post({"PROMPT": "@ "})
    assert xession.env.get("PROMPT") == "@ "


def test_prompts_page_post_strips_carriage_returns(xession, make_route):
    page = make_route(r.PromptsPage)
    page.post({"PROMPT": "a\r\nb"})
    assert xession.env.get("PROMPT") == "a\nb"


def test_prompts_page_post_no_data_is_noop(xession, make_route):
    original = xession.env.get("PROMPT")
    page = make_route(r.PromptsPage)
    page.post({})
    assert xession.env.get("PROMPT") == original


# --- XontribsPage -----------------------------------------------------------


def test_xontribs_page_renders_html(make_route):
    page = make_route(r.XontribsPage)
    out = t.to_str(list(page.get()))
    assert "Popular xontrib sources" in out


def test_xontribs_page_mod_name():
    assert r.XontribsPage.mod_name("foo") == "xontrib.foo"


def test_xontribs_page_post_no_data_is_noop(make_route):
    page = make_route(r.XontribsPage)
    # post with empty dict must return None and not raise
    assert page.post({}) is None


# --- EnvVariablesPage -------------------------------------------------------


def test_env_variables_page_renders_table(make_route):
    page = make_route(r.EnvVariablesPage)
    out = t.to_str(list(page.get()))
    assert "<table" in out


# --- AliasesPage -----------------------------------------------------------


def test_aliases_page_renders_table_with_no_aliases(xession, make_route):
    """If ``xsh.aliases`` is empty/None, the page still renders without crashing."""
    page = make_route(r.AliasesPage)
    out = t.to_str(list(page.get()))
    assert "<div" in out


def test_aliases_page_renders_table_with_aliases(xession, make_route):
    xession.commands_cache.aliases.update(
        {"foo_xyz": "echo foo", "bar_xyz": "echo bar"}
    )
    try:
        page = make_route(r.AliasesPage)
        rows = list(page.get_rows())
        names_rendered = "".join(t.to_str(rows))
        assert "foo_xyz" in names_rendered
        assert "bar_xyz" in names_rendered
    finally:
        xession.commands_cache.aliases.pop("foo_xyz", None)
        xession.commands_cache.aliases.pop("bar_xyz", None)


def test_aliases_page_skips_callable_aliases(xession, make_route):
    xession.commands_cache.aliases.update(
        {"sa_xyz": lambda args: 0, "txt_xyz": "echo hi"}
    )
    try:
        page = make_route(r.AliasesPage)
        rendered = "".join(t.to_str(list(page.get_rows())))
        # the string alias is rendered, the callable one is not
        assert "txt_xyz" in rendered
        assert "sa_xyz" not in rendered
    finally:
        xession.commands_cache.aliases.pop("sa_xyz", None)
        xession.commands_cache.aliases.pop("txt_xyz", None)


# --- Routes.err / get_err_msgs ---------------------------------------------


def test_route_err_appends_to_err_msgs(make_route):
    page = make_route(r.ColorsPage)
    page.err_msgs = []  # reset class-level shared list
    page.err("**boom**")
    msgs = list(page.get_err_msgs())
    # get_err_msgs yields wrapped alert divs and clears the list afterwards
    assert msgs
    assert page.err_msgs == []


def test_route_get_err_msgs_yields_nothing_when_empty(make_route):
    """``get_err_msgs`` is a generator — it yields zero items when err_msgs is empty."""
    page = make_route(r.ColorsPage)
    page.err_msgs = []
    out = page.get_err_msgs()
    # the generator yields no items
    assert list(out or ()) == []


# --- Routes.get_nav_links --------------------------------------------------


def test_get_nav_links_yields_each_registered_page(make_route):
    page = make_route(r.ColorsPage)
    links = list(page.get_nav_links())
    # one link per registered page (with title) + one per external link
    assert len(links) >= len(r.Routes.registry)


def test_get_nav_links_marks_active_page(make_route):
    page = make_route(r.ColorsPage)
    links = list(page.get_nav_links())
    rendered = t.to_str(links)
    assert "active" in rendered


# --- Routes.get_sel_url ---------------------------------------------------


def test_get_sel_url_appends_query_string(make_route):
    page = make_route(r.ColorsPage)
    url = page.get_sel_url("monokai")
    assert url.startswith("/")
    assert "selected=monokai" in url


# --- Routes.get_display ---------------------------------------------------


def test_get_display_handles_valid_html():
    elem = r.Routes.get_display("<span>hi</span>")
    out = t.to_str(elem)
    assert "hi" in out
    assert "<div" in out


def test_get_display_falls_back_to_pre_for_invalid_html():
    elem = r.Routes.get_display("<<<broken")
    out = t.to_str(elem)
    assert "<pre" in out
