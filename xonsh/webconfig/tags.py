import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable
import xml.etree.ElementTree as etree
from functools import partial


class Elem(etree.Element):
    def __init__(
        self,
        tag: "str",
        *cls: str,
        **kwargs: "str",
    ):
        super().__init__(tag)
        self.set_attrib(*cls, **kwargs)

    def __getitem__(self, item: "int|str|Elem|Iterable[Elem]"):  # type: ignore
        """nice sub-tree"""
        if isinstance(item, int):
            return super().__getitem__(item)
        if isinstance(item, str):
            self.text = (self.text or "") + item
        elif isinstance(item, etree.Element):
            self.append(item)
        else:
            for ele in item:
                try:
                    _ = self[ele]  # recursive call
                except Exception as ex:
                    logging.error(
                        f"Failed to append to node list. {ex!r} : {item!r}>{ele!r} : {self.to_str()!r}"
                    )
                    break
        return self

    def set_attrib(self, *cls: str, **kwargs: str):
        klass = " ".join(cls)
        classes = [klass, self.attrib.pop("class", "")]
        cls_str = " ".join(filter(None, classes))
        if cls_str:
            self.attrib["class"] = cls_str
        self.attrib.update(kwargs)

    def __call__(self, *cls: str, **kwargs: str):
        self.set_attrib(*cls, **kwargs)
        return self

    def to_str(self) -> bytes:
        return etree.tostring(self)


div = partial(Elem, "div")
row = partial(div, "row")
col = partial(div, "col")
col_sm = partial(div, "col-sm")
col_md = partial(div, "col-md")

alert = partial(div, "alert", role="alert")

br = partial(Elem, "br")

h3 = partial(Elem, "h3")
h4 = partial(Elem, "h4")
h5 = partial(Elem, "h5")
card_title = partial(h5, "card-title")

li = partial(Elem, "li")
nav_item = partial(li, "nav-item")

p = partial(Elem, "p")
small = partial(Elem, "small")
pre = partial(Elem, "pre")
code = partial(Elem, "code")

a = partial(Elem, "a")
nav_link = partial(a, "nav-link")

form = partial(Elem, "form")
inline_form = partial(form, "d-inline")

card = partial(div, "card")
card_header = partial(div, "card-header")
card_body = partial(div, "card-body")
card_text = partial(div, "card-text")
card_footer = partial(div, "card-footer")

textarea = partial(Elem, "textarea")

table = partial(Elem, "table")
tbl = partial(table, "table")  # bootstrap table
tr = partial(Elem, "tr")
th = partial(Elem, "th")
td = partial(Elem, "td")

btn = partial(Elem, "button", "btn", type="button")
btn_primary = partial(btn, "btn-primary")
btn_primary_sm = partial(btn_primary, "btn-sm")


def to_pretty(txt: str):
    import xml.dom.minidom

    dom = xml.dom.minidom.parseString(txt)
    txt = dom.toprettyxml()
    return "".join(txt.splitlines(keepends=True)[1:])


def to_str(elems: "Iterable[Elem]|Elem", debug=False) -> str:
    def _to_str():
        if isinstance(elems, etree.Element):
            yield etree.tostring(elems)
        else:
            for idx, el in enumerate(elems):
                try:
                    yield etree.tostring(el)
                except Exception:
                    logging.error(
                        f"Failed to serialize {el!r}. ({elems!r}.{idx!r})",
                        exc_info=True,
                    )

    txt = b"".join(_to_str()).decode()
    if debug:
        txt = to_pretty(txt)
    return txt


if __name__ == "__main__":
    nav = nav_item()[nav_link(href="/")["Colors"],]
    gen = to_str(nav, debug=True)
    print(gen)
    assert gen.splitlines() == [
        '<li class="nav-item">',
        '\t<a class="nav-link" href="/">Colors</a>',
        "</li>",
    ]
