the xonsh shell
===============

.. raw:: html 

    <p style="text-align:center;">
    <span style="font-family:Times;font-size:28px;font-style:normal;font-weight:normal;text-decoration:none;text-transform:none;font-variant:small-caps;color:000000;">
    <br />
    ~ 
    <script>
    var phrases = [
        "Exofrills in the shell",
        "No frills in the shell",
        "Become the Lord of the Files",
        "Break out of your shell",
        "It should not be that hard",
        "Pass the xonsh, Piggy", 
        "The shell, bourne again",
        "Starfish loves you",
        "Sally sells csh and keeps xonsh to herself",
        ];
    document.write(phrases[Math.floor(Math.random() * phrases.length)]);
    </script>
    ~
    <br />
    <br />
    </span>
    </p>

Polyphemus is a continuous integration tool that front-ends to 
`GitHub <https://github.com/>`_ et al. and backends to 
`BaTLaB <https://www.batlab.org/>`_.  This fills a similar role to that of Travis-CI
or the GitHub plugin for Jenkins.  However, BaTLab has a wider variety of machines
than Travis-CI and is cheaper (free) than running your own machines with Jenkins.

=========
Contents
=========

.. toctree::
    :maxdepth: 1

    tutorial
    batlab
    api/index
    rcdocs
    previous/index
    faq
    other
    authors

============
Installation
============
Since polyphemus is pure Python code, the ``pip`` or ``easy_install`` may be used
to grab and install the code::

    $ pip install polyphemus

    $ easy_install polyphemus


The source code repository for polyphemus may be found at the 
`GitHub project site <http://github.com/polyphemus-ci/polyphemus>`_.
You may simply clone the development branch using git::

    git clone git://github.com/polyphemus-ci/polyphemus.git

Also, if you wish to have the optional BASH completion, please add the 
following lines to your ``~/.bashrc`` file::

    # Enable completion for polyphemus
    eval "$(register-python-argcomplete polyphemus)"

============
Dependencies
============
Polyphemus currently has the following external dependencies,

*Run Time:*

    #. `flask <http://flask.pocoo.org/>`_
    #. `paramiko <http://www.lag.net/paramiko/>`_
    #. `github3.py <http://github3py.readthedocs.org/en/latest/>`_
    #. `argcomplete <https://argcomplete.readthedocs.org/en/latest/>`_, optional for BASH completion
    #. `apache 2 <http://httpd.apache.org/>`_, optional for real deployment
    #. `modwsgi <https://code.google.com/p/modwsgi/>`_, optional for apache

==========
Contact Us
==========
If you have questions or comments, please send them to the mailing list
polyphemus-ci@googlegroups.com or contact the author directly or open an issue on
GitHub. 
`Join the mailing list here! <https://groups.google.com/forum/#!forum/polyphemus-ci>`_

============
Contributing
============
We highly encourage contributions to polyphemus!  If you would like to contribute, 
it is as easy as forking the repository on GitHub, making your changes, and 
issuing a pull request.  If you have any questions about this process don't 
hesitate to ask the mailing list (polyphemus-ci@googlegroups.com). We are particularly
interested in adding bitbucket and mercurial support.

=============
Helpful Links
=============

* `Documentation <http://xonsh.org>`_
* `Mailing list <https://groups.google.com/forum/#!forum/polyphemus-ci>`_
* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`


