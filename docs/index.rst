the xonsh shell
===============

.. raw:: html

    <p style="text-align:center;">
    <span style="font-family:Times;font-size:28px;font-style:normal;font-weight:normal;text-decoration:none;text-transform:none;font-variant:small-caps;color:000000;">
    ~
    <script>
    var taglines = [
        "Exofrills in the shell",
        "No frills in the shell",
        "Become the Lord of the Files",
        "Break out of your shell",
        "The only shell that is also a shell",
        "All that is and all that shell be",
        "It cannot be that hard",
        "Pass the xonsh, Piggy",
        "Piggy glanced nervously into hell and cradled the xonsh",
        "The xonsh is a symbol",
        "It is pronounced <i>conch</i>",
        "It is pronounced <i>🐚</i>",
        "It is pronounced <i>kɒntʃ</i>",
        "The shell, bourne again",
        "Snailed it",
        "Starfish loves you",
        "Come snail away",
        "This is Major Tom to Ground Xonshtrol",
        "Sally sells csh and keeps xonsh to herself",
        "Nice indeed. Everything's accounted for, except your old shell.",
        "I wanna thank you for putting me back in my snail shell",
        "Crustaceanly Yours",
        "With great shell comes great reproducibility",
        "None shell pass",
        "You shell not pass!",
        "The x-on shell",
        "Ever wonder why there isn't a Taco Shell? Because it is a corny idea.",
        "It is pronounced <i>コンシュ</i>",
        "The carcolh will catch you!",
        "People xonshtantly mispronounce these things",
        "WHAT...is your favorite shell?",
        "Conches for the xonsh god!",
        "Python-powered, cross-platform, Unix-gazing shell",
        "Exploiting the workers and hanging on to outdated imperialist dogma since 2015."
        ];
    document.write(taglines[Math.floor(Math.random() * taglines.length)]);
    </script>
    ~
    <br />
    <br />
    </span>
    </p>

Xonsh is a Python-powered, cross-platform, Unix-gazing shell language and
command prompt. The language is a superset of Python 3.4+ with additional
shell primitives that you are used to from Bash and IPython. It works on
all major systems including Linux, Mac OSX, and Windows. Xonsh is meant
for the daily use of experts and novices alike.

**Try it out!**

.. raw:: html

    <style>
    .tryitbutton {
        background-color: #84A6C7;
        border: none;
        color: white;
        padding: 15px 32px;
        text-align: center;
        text-decoration: none;
        font-size: 22px;
        margin: 4px 2px;
        cursor: pointer;
        border-radius: 8px;
        position:relative;
        float: right;
        right: 35%;
        bottom: 240px;
    }
    </style>
    <div id="trydiv"><p style="text-align:center;">
    <iframe id="tryframe" data-src="_static/xonsh-live.png"
            src="_static/xonsh-live.png" width="80%" height="480px"
            style="overflow:hidden;" scrolling="no">
    </iframe>
    <button class="tryitbutton" id="trybutton">Click to Try Xonsh!</button>
    <script>
        $("#trybutton").click(function(){
            var tryframe = $("#tryframe");
            var trybutton = $("#trybutton");
            tryframe.attr("src", tryframe.data("src"));
            trybutton.remove();
        });
    </script>
    </p>
    </div>


..  <iframe id="tryframe" data-src="http://hermit.astro73.com/"
            src="_static/xonsh-live.png" width="80%" height="480px"
            style="overflow:hidden;" scrolling="no">
    </iframe>

=========
Contents
=========
**Installation:**

.. toctree::
    :titlesonly:
    :maxdepth: 1

    dependencies
    linux
    osx
    windows
    customization

**Guides:**

.. toctree::
    :titlesonly:
    :maxdepth: 1

    tutorial
    tutorial_hist
    tutorial_macros
    tutorial_xontrib
    tutorial_events
    tutorial_completers
    tutorial_history_backend
    tutorial_ptk
    bash_to_xsh
    python_virtual_environments

**Configuration & Setup:**

.. toctree::
    :titlesonly:
    :maxdepth: 1

    xonshrc
    xonshconfig
    envvars
    aliases
    xontribs
    events

**News & Media:**

.. toctree::
    :titlesonly:
    :maxdepth: 1

    talks_and_articles
    quotes


**Development Spiral:**

.. toctree::
    :titlesonly:
    :maxdepth: 1

    api/index
    advanced_events
    devguide/
    previous/index
    faq
    todo

==========
Comparison
==========
Xonsh is significantly different from most other shells or shell tools. The following
table lists features and capabilities that various tools may or may not share.

.. list-table::
    :widths: 3 1 1 1 1 1 1
    :header-rows: 1
    :stub-columns: 1

    * -
      - Bash
      - zsh
      - plumbum
      - fish
      - IPython
      - xonsh
    * - Sane language
      -
      -
      - ✓
      - ✓
      - ✓
      - ✓
    * - Easily scriptable
      - ✓
      - ✓
      - ✓
      - ✓
      -
      - ✓
    * - Native cross-platform support
      -
      -
      - ✓
      - ✓
      - ✓
      - ✓
    * - Meant as a shell
      - ✓
      - ✓
      -
      - ✓
      -
      - ✓
    * - Tab completion
      - ✓
      - ✓
      -
      - ✓
      - ✓
      - ✓
    * - Man-page completion
      -
      -
      -
      - ✓
      -
      - ✓
    * - Large standard library
      -
      - ✓
      -
      -
      - ✓
      - ✓
    * - Typed variables
      -
      -
      - ✓
      - ✓
      - ✓
      - ✓
    * - Syntax highlighting
      -
      -
      -
      - ✓
      - in notebook
      - w/ prompt-toolkit
    * - Pun in name
      - ✓
      -
      - ✓
      -
      -
      - ✓
    * - Rich history
      -
      -
      -
      -
      -
      - ✓



.. include:: dependencies.rst


============
Contributing
============
We highly encourage contributions to xonsh!  If you would like to contribute,
it is as easy as forking the repository on GitHub, making your changes, and
issuing a pull request.  If you have any questions about this process don't
hesitate to ask the mailing list (xonsh@googlegroups.com) or the `Gitter <https://gitter.im/xonsh/xonsh>`_ channel.

See the `Developer's Guide <devguide.html>`_ for more information about contributing.

==========
Contact Us
==========
If you have questions or comments, please send them to the mailing list
xonsh@googlegroups.com, page us on IRC, contact the author directly, or
open an issue on GitHub.
`Join the mailing list here! <https://groups.google.com/forum/#!forum/xonsh>`_

=============
Helpful Links
=============

* `Documentation <http://xon.sh>`_
* `Gitter <https://gitter.im/xonsh/xonsh>`_
* `Mailing list <https://groups.google.com/forum/#!forum/xonsh>`_
* `IRC: channel #xonsh on OFTC <http://www.oftc.net/>`_
* `GitHub Repository <https://github.com/xonsh/xonsh>`_
* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

.. raw:: html

    <a href="https://github.com/xonsh/xonsh" class='github-fork-ribbon' title='Fork me on GitHub'>Fork me on GitHub</a>

    <style>
    /*!
     * Adapted from
     * "Fork me on GitHub" CSS ribbon v0.2.0 | MIT License
     * https://github.com/simonwhitaker/github-fork-ribbon-css
     */

    .github-fork-ribbon, .github-fork-ribbon:hover, .github-fork-ribbon:hover:active {
      background:none;
      left: inherit;
      width: 12.1em;
      height: 12.1em;
      position: absolute;
      overflow: hidden;
      top: 0;
      right: 0;
      z-index: 9999;
      pointer-events: none;
      text-decoration: none;
      text-indent: -999999px;
    }

    .github-fork-ribbon:before, .github-fork-ribbon:after {
      /* The right and left classes determine the side we attach our banner to */
      position: absolute;
      display: block;
      width: 15.38em;
      height: 1.54em;
      top: 3.23em;
      right: -3.23em;
      box-sizing: content-box;
      transform: rotate(45deg);
    }

    .github-fork-ribbon:before {
      content: "";
      padding: .38em 0;
      background-image: linear-gradient(to bottom, rgba(0, 0, 0, 0), rgba(0, 0, 0, 0.1));
      box-shadow: 0 0.07em 0.4em 0 rgba(0, 0, 0, 0.3);
      pointer-events: auto;
    }

    .github-fork-ribbon:after {
      content: attr(title);
      color: #000;
      font: 700 1em "Helvetica Neue", Helvetica, Arial, sans-serif;
      line-height: 1.54em;
      text-decoration: none;
      text-align: center;
      text-indent: 0;
      padding: .15em 0;
      margin: .15em 0;
      border-width: .08em 0;
      border-style: dotted;
      border-color: #777;
    }

    </style>
