# Developer's Guide

![knight-vs-snail](_static/knight-vs-snail.jpg)

Welcome to the xonsh developer's guide! This is a place for developers to
place information that does not belong in the user's guide or the library
reference but is useful or necessary for the next people that come along to
develop xonsh.

> **Note:** All code changes must go through the pull request review procedure.

## Making Your First Change

First, install xonsh from source and open a xonsh shell in your favorite
terminal application. See installation instructions for details, but it
is recommended to do an 'editable' install via `pip`

```{prompt} bash
pip install -U "pip>=25.1"
pip install -e .[dev]
```

Next, make a trivial change (e.g. `print("hello!")` in `main.py`).

Finally, run the following commands. You should see the effects of your change
(e.g. `hello!`):

```{prompt} bash
env XONSH_DEBUG=1 xonsh
```

## Changelog

1. Use [conventional commits](https://www.conventionalcommits.org/en/v1.0.0/) for your git commits and Pull-Request titles
2. [CHANGELOG.md](CHANGELOG.md) is automatically generated from these commit messages using [release-please-action](https://github.com/googleapis/release-please-action)
3. We squash the Pull-Request commits when merging to maintain linear history. So it is important to use

## Style Guide

xonsh is a pure Python project, and so we use PEP8 (with some additions) to
ensure consistency throughout the code base.

### Rules to Write By

It is important to refer to things and concepts by their most specific name.
When writing xonsh code or documentation please use technical terms
appropriately. The following rules help provide needed clarity.

#### Interfaces

* User-facing APIs should be as generic and robust as possible.
* Tests belong in the top-level `tests` directory.
* Documentation belongs in the top-level `docs` directory.

#### Expectations

* Code must have associated tests and adequate documentation.
* User-interaction code (such as the Shell class) is hard to test.
  Mechanism to test such constructs should be developed over time.
* Have *extreme* empathy for your users.
* Be selfish. Since you will be writing tests you will be your first user.

### Python Style Guide

xonsh follows [PEP8](https://www.python.org/dev/peps/pep-0008/) for all Python code. The following rules apply where
[PEP8](https://www.python.org/dev/peps/pep-0008/) is open to interpretation.

* Use absolute imports (`import xonsh.tools`) rather than explicit
  relative imports (`import .tools`). Implicit relative imports
  (`import tools`) are never allowed.
* We use sphinx with the numpydoc extension to autogenerate API documentation. Follow
  the [numpydoc](https://numpydoc.readthedocs.io/en/latest/format.html#docstring-standard) standard for docstrings.
* Simple functions should have simple docstrings.
* Lines should be at most 80 characters long. The 72 and 79 character
  recommendations from PEP8 are not required here.
* Tests should be written with [pytest](https://docs.pytest.org/) using a procedural style. Do not use
  unittest directly or write tests in an object-oriented style.
* Test generators make more dots and the dots must flow!
* We use [ruff](https://docs.astral.sh/ruff/) for linting and formatting the code. It is used as a [pre-commit](https://pre-commit.com/) hook. Enable it by running:

```{prompt} bash
pre-commit install
pre-commit run --all-files
```

## How to Test

### Docker

If you want to run your "work in progress version" without installing
and in a fresh environment you can use Docker. If Docker is installed
you just have to run this:

```{prompt} bash
python xonsh-in-docker.py
```

This will build and run the current state of the repository in an isolated
container (it may take a while the first time you run it). There are two
additional arguments you can pass this script.

* The version of python
* the version of `prompt_toolkit`

Example:

```{prompt} bash
python docker.py 3.4 0.57
```

Ensure your cwd is the root directory of the project (i.e., the one containing the
.git directory).

### Dependencies

Prep your environment for running the tests:

```{prompt} bash
pip install -e '.[dev]'
```

### Running the Tests - Basic

Run all the tests using pytest:

```{prompt} bash
pytest -q
```

Use "-q" to keep pytest from outputting a bunch of info for every test.

### Running the Tests - Advanced

To perform all unit tests:

```{prompt} bash
pytest
```

If you want to run specific tests you can specify the test names to
execute. For example to run test_aliases:

```{prompt} bash
pytest test_aliases.py
```

Note that you can pass multiple test names in the above examples:

```{prompt} bash
pytest test_aliases.py test_environ.py
```

### Writing the Tests - Advanced

(refer to pytest documentation)

With the Pytest framework you can use bare `assert` statements on
anything you're trying to test, note that the name of the test function
has to be prefixed with `test_`:

```python
def test_whatever():
    assert is_true_or_false
```

The conftest.py in tests directory defines fixtures for mocking various
parts of xonsh for more test isolation. For a list of the various fixtures:

```{prompt} bash
pytest --fixtures
```

when writing tests it's best to use pytest features i.e. parametrization:

```python
@pytest.mark.parametrize('env', [test_env1, test_env2])
def test_one(env, xession):
    # update the environment variables instead of setting the attribute
    # which could result in leaks to other tests.
    # each run will have the same set of default env variables set.
    xession.env.update(env)
    ...
```

this will run the test two times each time with the respective `test_env`.
This can be done with a for loop too but the test will run
only once for the different test cases and you get less isolation.

With that in mind, each test should have the least `assert` statements,
preferably one.

At the moment, xonsh doesn't support any pytest plugins.

Happy Testing!

## How to Document

Documentation takes many forms. This will guide you through the steps of
successful documentation.

### Docstrings

No matter what language you are writing in, you should always have
documentation strings along with you code. This is so important that it is
part of the style guide. When writing in Python, your docstrings should be
in reStructured Text using the [numpydoc](https://numpydoc.readthedocs.io/en/latest/format.html#docstring-standard) format.

### Auto-Documentation Hooks

The docstrings that you have written will automatically be connected to the
website, once the appropriate hooks have been setup. At this stage, all
documentation lives within xonsh's top-level `docs` directory.
We uses the sphinx tool to manage and generate the documentation, which
you can learn about from [the sphinx website](http://sphinx-doc.org/).
If you want to generate the documentation, first xonsh itself must be installed
and then you may run the following command from the `docs` dir:

```{prompt} bash (~/xonsh/docs)$
make html
```

For each new
module, you will have to supply the appropriate hooks. This should be done the
first time that the module appears in a pull request. From here, call the
new module `mymod`. The following explains how to add hooks.

### Python Hooks

Python API documentation is generated for the entries in `docs/api.rst`.
[sphinx-autosummary](https://www.sphinx-doc.org/en/master/usage/extensions/autosummary.html)
is used to generate documentation for the modules.
Mention your module `mymod` under appropriate header.
This will discover all of the docstrings in `mymod` and create the
appropriate webpage.

## Building the Website

Building the website/documentation requires the following dependencies:

1. [Sphinx](http://sphinx-doc.org/)
2. [Furo Theme](https://pradyunsg.me/furo/)
3. [numpydoc](https://numpydoc.readthedocs.io/en/latest/format.html#docstring-standard)
4. [MyST Parser](https://myst-parser.readthedocs.io)

Note that xonsh itself needs to be installed too.

If you have cloned the git repository, you can install all of the doc-related
dependencies by running:

```{prompt} bash
pip install -e ".[doc]"
```

### Procedure for modifying the website

The xonsh website source files are located in the `docs` directory.
A developer first makes necessary changes, then rebuilds the website locally
by executing the command:

```{prompt} bash
make html
```

This will generate html files for the website in the `_build/html/` folder.

You can watch for changes and automatically rebuild the documentation with the following command:

```{prompt} bash
make serve
```

The developer may view the local changes by opening these files with their
favorite browser, e.g.:

```{prompt} bash
firefox _build/html/index.html
```

Once the developer is satisfied with the changes, the changes should be
committed and pull-requested per usual. The docs are built and deployed using
GitHub Actions.

Docs associated with the latest release are hosted at [https://xon.sh](https://xon.sh)
while docs for the current `main` branch are available at [https://xon.sh/dev](https://xon.sh/dev).

## Branches and Releases

Mainline xonsh development occurs on the `main` branch. Other branches
may be used for feature development (topical branches) or to represent
past and upcoming releases.

### Maintenance Tasks

You can cleanup your local repository of transient files such as \*.pyc files
created by unit testing by running:

```{prompt} bash
rm -f xonsh/parser_table.py xonsh/completion_parser_table.py
rm -f xonsh/*.pyc tests/*.pyc
rm -fr build
```

### Performing the Release

This is done through the [rever](https://github.com/regro/rever). To get a list of the
valid options use:

```{prompt} bash
pip install re-ver
```

You can perform a full release:

```{prompt} bash
rever check
rever <version-number>
```

### Cross-platform testing

Most of the time, an actual VM machine is needed to test the nuances of cross platform testing.
But alas here are some other ways to test things

1. Windows

   - [wine](https://www.winehq.org/) can be used to emulate the development environment. It provides cmd.exe with its default installation.

2. OS X

   - [darlinghq](https://www.darlinghq.org/) can be used to emulate the development environment for Linux users.
     Windows users can use Linux inside a virtual machine or WSL to run the same.
   - [OSX KVM](https://github.com/kholia/OSX-KVM) can be used for virtualization.

3. Linux

   - It far easier to test things for Linux. [docker](https://www.docker.com/) is available on all three platforms.

One can leverage the Github Actions to provide a reverse shell to test things out.
Solutions like [actions-tmate](https://mxschmitt.github.io/action-tmate/) are available,
but they should not in any way violate the Github Action policies.

## Document History

Portions of this page have been forked from the PyNE documentation,
Copyright 2011-2015, the PyNE Development Team. All rights reserved.