the xonsh shell
===============

.. raw:: html 

    <p style="text-align:center;">
    <span style="font-family:Times;font-size:28px;font-style:normal;font-weight:normal;text-decoration:none;text-transform:none;font-variant:small-caps;color:000000;">
    <br />
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
        "It is pronounced <i>konk</i>",
        "It is pronounced <i>conch</i>",
        "It is pronounced <i>quanxh</i>",
        "It is pronounced <i>zonsch</i>",
        "The shell, bourne again",
        "Snailed it",
        "Starfish loves you",
        "Come snail away",
        "This is Major Tom to Ground Xonshtrol",
        "Sally sells csh and keeps xonsh to herself",
        "Nice indeed. Everything's accounted for, except your old shell.",
        ];
    document.write(taglines[Math.floor(Math.random() * taglines.length)]);
    </script>
    ~
    <br />
    <br />
    </span>
    </p>

xonsh is a Python-ish, BASHwards-compatible shell language and command prompt.
The language is a superset of Python 3.4 with additional shell primitives
that you are used to from BASH and IPython. xonsh is 
meant for the daily use of experts and novices alike.

**At a glance**

.. raw:: html 

    <p style="text-align:center;">

.. raw:: html

    <video controls> <source src="_static/xonsh-demo.webm" type="video/webm"><img src="_static/xonsh-demo.gif"></video>

.. raw:: html 

    </p>

=========
Contents
=========

.. toctree::
    :titlesonly:
    :maxdepth: 1

    tutorial
    windows
    api/index
    devguide/
    previous/index
    faq
    todo

============
Installation
============
You can install xonsh using conda, pip, or from source.

**conda:**

.. code-block:: bash

    $ conda install -c scopatz xonsh

**pip:**

.. code-block:: bash

    $ pip install xonsh

**source:** Download the source `from github <https://github.com/scopatz/xonsh>`_
(`zip file <https://github.com/scopatz/xonsh/archive/master.zip>`_), then run
the following from the source directory,

.. code-block:: bash

    $ python setup.py install

If you run into any problems, please let us know!

============
Dependencies
============
xonsh currently has the following external dependencies,

*Run Time:*

    #. Python v3.4+
    #. PLY

*Documentation:*

    #. Sphinx
    #. Numpydoc
    #. Cloud Sphinx Theme

============
Contributing
============
We highly encourage contributions to xonsh!  If you would like to contribute, 
it is as easy as forking the repository on GitHub, making your changes, and 
issuing a pull request.  If you have any questions about this process don't 
hesitate to ask the mailing list (xonsh@googlegroups.com). 

==========
Contact Us
==========
If you have questions or comments, please send them to the mailing list
xonsh@googlegroups.com, contact the author directly, or open an issue on
GitHub. 
`Join the mailing list here! <https://groups.google.com/forum/#!forum/xonsh>`_

=============
Helpful Links
=============

* `Documentation <http://xonsh.org>`_
* `Mailing list <https://groups.google.com/forum/#!forum/xonsh>`_
* `GitHub Repository <https://github.com/scopatz/xonsh>`_
* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

.. raw:: html

    <a href="https://github.com/scopatz/xonsh"><img style="position: absolute; top: 0; right: 0; border: 0;" src="https://camo.githubusercontent.com/52760788cde945287fbb584134c4cbc2bc36f904/68747470733a2f2f73332e616d617a6f6e6177732e636f6d2f6769746875622f726962626f6e732f666f726b6d655f72696768745f77686974655f6666666666662e706e67" alt="Fork me on GitHub" data-canonical-src="https://s3.amazonaws.com/github/ribbons/forkme_right_white_ffffff.png"></a>
