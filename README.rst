xonsh
=====

.. raw:: html

    <img src="https://avatars.githubusercontent.com/u/17418188?s=200&v=4" alt="Xonsh shell icon." align="left" width="100px">

**Xonsh** is a Python-powered shell. Full-featured and cross-platform. The language is a superset of Python 3.6+ with additional shell primitives. The name Xonsh should be pronounced like "consh" - a softer form of the word "conch" (🐚, ``@``), referring to the world of command shells.

.. raw:: html

    <br clear="left"/>

.. list-table::
   :widths: 1 1

   *  -  **Xonsh is the Shell**
      -  **Xonsh is Python**

   *  -  .. code-block:: shell

            cd $HOME

            id $(whoami)

            cat /etc/passwd | grep root > ~/root.txt

            $PROMPT = '@ '


      -  .. code-block:: python

            2 + 2

            var = "hello".upper()

            import json; json.loads('{"a":1}')

            [i for i in range(0,10)]

   *  -  **Xonsh is the Shell in Python**
      -  **Xonsh is Python in the Shell**

   *  -  .. code-block:: python

            len($(curl -L https://xon.sh))

            $PATH.append('/tmp')

            p'/etc/passwd'.read_text().find('root')

            xontrib load dalias
            id = $(@json docker ps --format json)['ID']

      -  .. code-block:: python

            name = 'foo' + 'bar'.upper()
            echo @(name) > /tmp/@(name)

            ls @(input('file: '))
            touch @([f"file{i}" for i in range(0,10)])

            aliases['e'] = 'echo @(2+2)'
            aliases['a'] = lambda args: print(args)


If you like xonsh, :star: the repo, `write a tweet`_ and stay tuned by watching releases.

.. class:: center

    .. image:: https://img.shields.io/badge/Zulip%20Community-xonsh-green
            :target: https://xonsh.zulipchat.com/
            :alt: Join to xonsh.zulipchat.com

    .. image:: https://repology.org/badge/tiny-repos/xonsh.svg
            :target: https://repology.org/project/xonsh/versions
            :alt: repology.org

    .. image:: https://img.shields.io/badge/Docker%20Hub-xonsh-blue
            :target: https://hub.docker.com/u/xonsh
            :alt: hub.docker.com

    .. image:: https://img.shields.io/badge/AppImage-xonsh-lightblue
            :target: https://xon.sh/appimage.html
            :alt: AppImage

    .. image:: https://github.com/xonsh/xonsh/actions/workflows/test.yml/badge.svg
            :target: https://github.com/xonsh/xonsh/actions/workflows/test.yml
            :alt: GitHub Actions

    .. image:: https://codecov.io/gh/xonsh/xonsh/branch/master/graphs/badge.svg?branch=main
            :target: https://codecov.io/github/xonsh/xonsh?branch=main
            :alt: codecov.io

First steps
***********

Install xonsh from pip:

.. code-block:: shell

    python -m pip install 'xonsh[full]'

And visit https://xon.sh for more information:

- `Installation <https://xon.sh/contents.html#installation>`_ - using packages, docker or AppImage.
- `Tutorial <https://xon.sh/tutorial.html>`_ - step by step introduction in xonsh.

Some beginners find the `xonsh cheatsheet <https://github.com/anki-code/xonsh-cheatsheet>`_ a helpful place to start.

Extensions
**********

Xonsh has an extension/plugin system.  We call these additions ``xontribs``.

- `Xontribs on Github <https://github.com/topics/xontrib>`_
- `Awesome xontribs <https://github.com/xonsh/awesome-xontribs>`_
- `Core xontribs <https://xon.sh/api/_autosummary/xontribs/xontrib.html>`_
- `Create a xontrib step by step from template <https://github.com/xonsh/xontrib-template>`_

Projects that use xonsh or compatible
*************************************

- `conda <https://conda.io/projects/conda/en/latest/>`_ and `mamba <https://mamba.readthedocs.io/en/latest/>`_: Modern package managers.
- `Starship <https://starship.rs/>`_: Cross-shell prompt.
- `zoxide <https://github.com/ajeetdsouza/zoxide>`_: A smarter cd command.
- `gitsome <https://github.com/donnemartin/gitsome>`_: Supercharged Git/shell autocompleter with GitHub integration.
- `xxh <https://github.com/xxh/xxh>`_: Using xonsh wherever you go through the SSH.
- `Snakemake <https://snakemake.readthedocs.io/en/stable/snakefiles/rules.html#xonsh>`_: A workflow management system to create reproducible and scalable data analyses.
- `any-nix-shell <https://github.com/haslersn/any-nix-shell>`_: xonsh support for the ``nix run`` and ``nix-shell`` environments of the Nix package manager.
- `lix <https://github.com/lix-project/lix>`_: A modern, delicious implementation of the Nix package manager.
- `x-cmd <https://www.x-cmd.com/>`_: x-cmd is a vast and interesting collection of tools guided by the Unix philosophy.
- `rever <https://regro.github.io/rever-docs/>`_: Cross-platform software release tool.
- `Regro autotick bot <https://github.com/regro/cf-scripts>`_: Regro Conda-Forge autoticker.

Jupyter-based interactive notebooks via `xontrib-jupyter <https://github.com/xonsh/xontrib-jupyter>`_:

- `Jupyter and JupyterLab <https://jupyter.org/>`_: Interactive notebook platform.
- `euporie <https://github.com/joouha/euporie>`_: Terminal based interactive computing environment.
- `Jupytext <https://jupytext.readthedocs.io/>`_: Clear and meaningful diffs when doing Jupyter notebooks version control.

Welcome to the xonsh shell community
************************************

The xonsh shell is developed by a community of volunteers. There are a few ways to help out:

- Solve a `popular issue <https://github.com/xonsh/xonsh/issues?q=is%3Aissue+is%3Aopen+sort%3Areactions-%2B1-desc>`_ or `high priority issue <https://github.com/xonsh/xonsh/issues?q=is%3Aopen+is%3Aissue+label%3Apriority-high+sort%3Areactions-%2B1-desc>`_ or a `good first issue <https://github.com/xonsh/xonsh/issues?q=is%3Aopen+is%3Aissue+label%3A%22good+first+issue%22+sort%3Areactions-%2B1-desc>`_. You can start with the `Developer guide <https://xon.sh/devguide.html>`_.
- Take an `idea <https://github.com/xonsh/xontrib-template/issues?q=is%3Aopen+is%3Aissue+label%3Aidea+sort%3Areactions-%2B1-desc>`_ and `create a new xontrib <https://github.com/xonsh/xontrib-template#why-use-this-template>`_.
- Contribute to `xonsh API <https://github.com/xonsh/xonsh/tree/main/xonsh/api>`_.
- Become xonsh core developer by deep diving into xonsh internals. E.g. we feel a lack of Windows support.
- Implement and maintain xonsh support in third party tools e.g. conda, jupyter, zoxide, etc.
- Design more `logos and images <https://github.com/anki-code/xonsh-logo>`_, improve `xonsh website <https://xon.sh/>`_ (`src <https://github.com/xonsh/xonsh/blob/12f12ce94f1b6c92218e22fbdaaa846e16ac8b2d/docs/_templates/index.html#L9>`_).
- `Become a sponsor to xonsh <https://github.com/sponsors/xonsh>`_.
- `Write a tweet`_, post or an article to spread the good word about xonsh in the world.
- Give a star to xonsh repository and to `xontribs <https://github.com/topics/xontrib>`_ you like.

We welcome new contributors!

.. _write a tweet: https://twitter.com/intent/tweet?text=xonsh%20is%20a%20Python-powered,%20cross-platform,%20Unix-gazing%20shell%20language%20and%20command%20prompt.&url=https://github.com/xonsh/xonsh

Credits
*******

- Thanks to `Zulip <https://zulip.com/>`_ for supporting the `xonsh community <https://xonsh.zulipchat.com/>`_!
- Thanks to ADS.FUND for supporting `xonsh token <https://ads.fund/token/0xadf7478450b69a349ed9634b18584d2d3da81464>`_!
