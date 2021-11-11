**Added:**

* New `Parser` which provides a `.parse` method for parsing Xonsh syntax

**Changed:**

* Split new `Parser` class from `Execer` to handle contextual parsing
* `xonsh.parser.Parser` now returns new `Parser` class, rather than the renamed
`StrictParser`.

**Deprecated:**

**Removed:**

**Fixed:**

**Security:**
