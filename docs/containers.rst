Docker container
================

Xonsh publishes a handful of containers, primarily targeting CI and automation use cases. All of them are published on `Docker Hub <https://hub.docker.com/u/xonsh>`__.

* ``xonsh/xonsh``: A base container providing basic xonsh
* ``xonsh/interactive``: xonsh with additions for people
* ``xonsh/action``: xonsh with additions for GitHub Actions

All containers use the same tagging scheme:

* ``<version>``/``latest``: Based on ``python:3`` (Debian Buster)
* ``<version>-slim``/``slim``: Based on ``python:3-slim`` (Debian Buster, slim variant)
* ``<version>-alpine``/``alpine``: Based on ``python:3-alpine`` (Alpine Linux)

You can select specific versions of xonsh. However, you cannot select specific versions of Python. Everything is rebuilt daily.

All containers include an ``xpip`` utility to let you easily install packages from a Dockerfile.

The container source can be found in the `container project <https://github.com/xonsh/container>`_.

``xonsh/xonsh``
---------------

(`Docker Hub <https://hub.docker.com/r/xonsh/xonsh>`__)

A basic container, including Python itself, xonsh, and the linux extras. This container is deliberately kept minimal.


``xonsh/interactive``
---------------------

(`Docker Hub <https://hub.docker.com/r/xonsh/interactive>`__)

A container made for humans (such as getting a shell inside of a pod). It includes prompt toolkit and pygments so that xonsh is more usable interactively.


``xonsh/action``
----------------

(`Docker Hub <https://hub.docker.com/r/xonsh/action>`__)

A container with extras for GitHub Actions.

First, some of the inputs are parsed into more helpful forms:

* ``$GITHUB_EVENT``: The event that triggered the action (parsed from ``$GITHUB_EVENT_PATH``)
* ``$INPUT``: The input arguments configured in the workflow (from ``$INPUT_*``)

In addition, if you have `PyGithub <https://github.com/PyGithub/PyGithub>`_ or `gqlmod <https://gqlmod.readthedocs.io/en/stable/>`_ installed, and an authentication token was found, they will be configured:

* PyGithub: A ``Github`` object can be found at ``$GITHUB``
* gqlmod: the token will be applied globally and the library will be ready to use
