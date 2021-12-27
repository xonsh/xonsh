import xml.etree.ElementTree as etree


class Elem(etree.Element):
    def __init__(
        self,
        tag: "str",
        attrib: "dict[str, str]" = None,
        klass: "str|None" = None,
        **kwargs: "str",
    ):
        super().__init__(tag)
        if attrib:
            kwargs.update(attrib)
        self.set_attrib(klass, **kwargs)

    def __getitem__(self, item: "int|str|tuple[Elem]"):
        """nice sub-tree"""
        if isinstance(item, int):
            return super().__getitem__(item)
        if isinstance(item, str):
            self.text = item
        else:
            self.extend(item)
        return self

    def set_attrib(self, klass=None, **kwargs: str):
        classes = [klass, self.attrib.pop("class", "")]
        self.attrib["class"] = " ".join(filter(None, classes))
        self.attrib.update(kwargs)

    def __call__(self, klass=None, **kwargs: str):
        self.set_attrib(klass, **kwargs)
        return self

    def to_str(self) -> bytes:
        return etree.tostring(self)


class Tags:
    """collection of tags"""

    def __getattr__(self, name: str):
        """wrap around the element"""
        return Elem(name)


def li(**kwargs):
    return Elem("li", **kwargs)


def nav_item(**kwargs):
    return li(klass="nav-item", **kwargs)


def a(**kwargs):
    return Elem("a", **kwargs)


def nav_link(**kwargs):
    return a(klass="nav-link", **kwargs)


def to_pretty(txt: str):
    import xml.dom.minidom

    dom = xml.dom.minidom.parseString(txt)
    txt: str = dom.toprettyxml()
    return "".join(txt.splitlines(keepends=True)[1:])


def to_str(elems: "list[Elem]|Elem", debug=False) -> str:
    def _to_str():
        if isinstance(elems, list):
            for el in elems:
                yield etree.tostring(el)
        else:
            yield etree.tostring(elems)

    txt = b"".join(_to_str()).decode()
    if debug:
        txt = to_pretty(txt)
    return txt


# dynamic new tags
T = Tags()

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
