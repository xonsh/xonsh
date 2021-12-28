import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Iterable
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

    def __getitem__(self, item: "int|str|Elem|tuple[Elem, ...]"):  # type: ignore
        """nice sub-tree"""
        if isinstance(item, int):
            return super().__getitem__(item)
        if isinstance(item, str):
            self.text = item
        elif isinstance(item, etree.Element):
            self.append(item)
        elif isinstance(item, tuple) and isinstance(item[0], str):
            self.text = "".join(item)
        else:
            try:
                self.extend(item)
            except Exception as ex:
                logging.error(
                    f"Failed to extend node list. {ex!r} : {item!r} : {self.to_str()!r}"
                )
        return self

    def set_attrib(self, *cls: str, **kwargs: str):
        klass = " ".join(cls)
        classes = [klass, self.attrib.pop("class", "")]
        self.attrib["class"] = " ".join(filter(None, classes))
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

br = partial(Elem, "br")

h3 = partial(Elem, "h3")
h4 = partial(Elem, "h4")
h5 = partial(Elem, "h5")
card_title = partial(h5, "card-title")

li = partial(Elem, "li")
nav_item = partial(li, "nav-item")

p = partial(Elem, "p")
pre = partial(Elem, "pre")
code = partial(Elem, "code")

a = partial(Elem, "a")
nav_link = partial(a, "nav-link")


card = partial(div, "card")
card_header = partial(div, "card-header")
card_body = partial(div, "card-body")
card_text = partial(div, "card-text")

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
        if isinstance(elems, Elem):
            yield etree.tostring(elems)
        else:
            for el in elems:
                yield etree.tostring(el)

    txt = b"".join(_to_str()).decode()
    if debug:
        txt = to_pretty(txt)
    return txt


if __name__ == "__main__":
    nav = nav_item()[
        nav_link(href="/")["Colors"],
    ]
    gen = to_str(nav, debug=True)
    print(gen)
    assert gen.splitlines() == [
        '<li class="nav-item">',
        '\t<a class="nav-link" href="/">Colors</a>',
        "</li>",
    ]
