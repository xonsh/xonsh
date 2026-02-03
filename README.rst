xonsh
=====

.. raw:: html

    <img src="https://avatars.githubusercontent.com/u/17418188?s=200&v=4" alt="Xonsh shell icon." align="left" width="100px">

**Xonsh** is a Python-powered shell. Full-featured, cross-platform and AI-friendly. The language is a superset of Python 3 with seamless integration of shell functionality and commands. The name Xonsh should be pronounced like "consh" — a softer form of the word "conch" (🐚, ``@``), referring to the world of command shells.

.. raw:: html

    <br clear="left"/>

.. list-table::
   :widths: 1 1

   *  -  **Xonsh is the Shell**
      -  **Xonsh is Python**

   *  -  .. code-block:: shell

            cd $HOME

            id $(whoami) > ~/id.txt

            cat /etc/passwd | grep root

            $PROMPT = '@ '


      -  .. code-block:: python

            2 + 2

            var = "hello".upper()

            @.imp.json.loads('{"a":1}')

            [i for i in range(0,10)]

   *  -  **Xonsh is the Shell in Python**
      -  **Xonsh is Python in the Shell**

   *  -  .. code-block:: python

            len($(curl -L https://xon.sh))

            $PATH.append('/tmp')

            p'/etc/passwd'.read_text().find('usr')

            xontrib load dalias  # extension
            $(@json podman ps --format json)['ID']

      -  .. code-block:: python

            name = 'snail'
            echo @(name) > /tmp/@(name)

            with p'/tmp/dir'.mkdir().cd():
                touch @(input('File: '))

            aliases['e'] = 'echo @(2+2)'
            aliases['a'] = lambda args: print(args)

   *  -  **Xonsh is a Meta-Shell**
      -  **Xonsh is an Ecosystem**

   *  -  .. code-block:: python

            xontrib load sh \
                         fish_completer

            def nudf(cmd):
                return @.imp.pandas.DataFrame(
                  @.imp.json.loads(
                  $(nu -c @(cmd+'| to json'))))
            nudf!(ls -la)

            aliases['ai'] = 'ollama run llama3'
            ai! how to remove images in podman


      -  .. code-block:: python

            xontrib load term_integration \
                         prompt_starship  \
                         powerline        \
                         dracula          \
                         chatgpt          \
                         django           \
                         jupyter          \
                         1password        \
                         github_copilot   \
                         history_encrypt


If you like xonsh, :star: the repo and spread the word about xonsh.

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

- `Installation <https://github.com/xonsh/xonsh/blob/refactor_install_docs/docs/install.rst>`_ - isolated environment, package, container or portable AppImage.
- `Tutorial <https://xon.sh/tutorial.html>`_ - step by step introduction in xonsh.
- `Cheat sheet <https://github.com/anki-code/xonsh-cheatsheet>`_ - some beginners may find this a helpful place to start.

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
- `kash <https://github.com/jlevy/kash>`_: The knowledge agent shell.
- `Snakemake <https://snakemake.readthedocs.io/en/stable/snakefiles/rules.html#xonsh>`_: A workflow management system to create reproducible and scalable data analyses.
- `any-nix-shell <https://github.com/haslersn/any-nix-shell>`_: xonsh support for the ``nix run`` and ``nix-shell`` environments of the Nix package manager.
- `lix <https://github.com/lix-project/lix>`_: A modern, delicious implementation of the Nix package manager.
- `x-cmd <https://www.x-cmd.com/>`_: x-cmd is a vast and interesting collection of tools guided by the Unix philosophy.
- `rever <https://regro.github.io/rever-docs/>`_: Cross-platform software release tool.
- `Regro autotick bot <https://github.com/regro/cf-scripts>`_: Regro Conda-Forge autoticker.

Jupyter-based interactive notebooks via `xontrib-jupyter <https://github.com/xonsh/xontrib-jupyter>`_:

- `Jupyter and JupyterLab <https://jupyter.org/>`_: Interactive notebook platform.
- `Euporie <https://github.com/joouha/euporie>`_: Terminal based interactive computing environment.
- `Jupytext <https://jupytext.readthedocs.io/>`_: Clear and meaningful diffs when doing Jupyter notebooks version control.

Compiling, packaging, or accelerating xonsh:

- `AppImage <https://github.com/appimage>`_ is a format for distributing Linux applications and can be used to `create a standalone xonsh package <https://xon.sh/appimage.html>`_.
- `Nuitka <https://github.com/Nuitka/Nuitka>`_ is an optimizing Python compiler that can `build a native xonsh binary <https://github.com/xonsh/xonsh/issues/2895#issuecomment-3665753657>`_.
- `RustPython <https://github.com/RustPython/RustPython/>`_ is a Python interpreter written in Rust that can `run xonsh on top of Rust <https://github.com/xonsh/xonsh/issues/5082#issue-1611837062>`_.


Welcome to the xonsh shell community
************************************

The xonsh shell is developed by a community of volunteers. There are a few ways to help out:

- Solve a `popular issue <https://github.com/xonsh/xonsh/issues?q=is%3Aissue+is%3Aopen+sort%3Areactions-%2B1-desc>`_ or `high priority issue <https://github.com/xonsh/xonsh/issues?q=is%3Aopen+is%3Aissue+label%3Apriority-high+sort%3Areactions-%2B1-desc>`_ or a `good first issue <https://github.com/xonsh/xonsh/issues?q=is%3Aopen+is%3Aissue+label%3A%22good+first+issue%22+sort%3Areactions-%2B1-desc>`_. You can start with the `Developer guide <https://xon.sh/devguide.html>`_. Feel free to use LLM e.g. `Github Copilot <https://github.com/copilot>`_.
- Take an `idea <https://github.com/xonsh/xontrib-template/issues?q=is%3Aopen+is%3Aissue+label%3Aidea+sort%3Areactions-%2B1-desc>`_ and `create a new xontrib <https://github.com/xonsh/xontrib-template#why-use-this-template>`_.
- Contribute to `xonsh API <https://github.com/xonsh/xonsh/tree/main/xonsh/api>`_.
- Become xonsh core developer by deep diving into xonsh internals. E.g. we feel a lack of Windows support.
- Add xonsh support in third party tool: `package manager <https://github.com/topics/package-manager>`_, `terminal emulator <https://github.com/topics/terminal-emulators>`_, `console tool <https://github.com/topics/console>`_, `IDE <https://github.com/topics/ide>`_.
- Test xonsh with compiler, interpreter, optimizer and report upstream issues (e.g. `Nuitka <https://github.com/xonsh/xonsh/issues/2895#issuecomment-3665753657>`_, `RustPython <https://github.com/xonsh/xonsh/issues/5082#issue-1611837062>`_).
- Design more `logos and images <https://github.com/anki-code/xonsh-logo>`_, improve `xonsh website <https://xon.sh/>`_ (`src <https://github.com/xonsh/xonsh/blob/12f12ce94f1b6c92218e22fbdaaa846e16ac8b2d/docs/_templates/index.html#L9>`_).
- `Become a sponsor to xonsh <https://github.com/sponsors/xonsh>`_.
- Spread the good word about xonsh in the world.
- Give a star to xonsh repository and to `xontribs <https://github.com/topics/xontrib>`_ you like.

We welcome new contributors!

Credits
*******

- Thanks to `Zulip <https://zulip.com/>`_ for supporting the `xonsh community <https://xonsh.zulipchat.com/>`_!
- Thanks to ADS.FUND for supporting `xonsh token <https://ads.fund/token/0xadf7478450b69a349ed9634b18584d2d3da81464>`_!
