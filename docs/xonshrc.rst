Run Control File
=========================
Xonsh allows you to have run control files to customize your shell behavior.  These are called ``xonshrc`` files.

The system-wide ``xonshrc`` file controls options that are applied to all users of Xonsh on a given system.  You can create this file in ``/etc/xonshrc`` for Linux and OSX and in ``%ALLUSERSPROFILE%\xonsh\xonshrc`` on Windows.

Xonsh also allows you to have a run control file in your home directory called ``~/.xonshrc``.  The options set in the local ``xonshrc`` only apply to the current user and will override any conflicting settings set in the system-wide control file.

These files are written in the xonsh language, of course. They are executed exactly once
at startup. The following is a real-world example of such a file.

:download:`Download xonshrc <xonshrc.xsh>`

.. include:: xonshrc.xsh
    :code: xonsh


Snippets for xonshrc
=========================
The following are usefull snippets and code that tweaks and adjust xonsh in various ways.
If you have any useful tricks, feel free to share them.

Adjust how git branch label behaves
-------------------------------------------
Xonsh adds a colored branch name to the prompt when working with git or hg repositories.
This behavior can be controlled with the ``$PROMPT`` environment variable. See how to `customize the prompt`_ .
The branch name changes color if the work dir is dirty or not. This is controlled by the ``{branch_color}`` formatter string.


The following snippet reimplements the formatter also to include untracked files when considering if a git directory is dirty.

.. code-block:: xonshcon

    >>> from xonsh.prompt.vc_branch import git_dirty_working_directory
    >>> $PROMPT_FIELDS['branch_color'] = lambda: ('{BOLD_INTENSE_RED}'
                                                   if git_dirty_working_directory(include_untracked=True)
                                                   else '{BOLD_INTENSE_GREEN}')


.. _customize the prompt: http://xon.sh/tutorial.html#customizing-the-prompt


Get better colors from the ``ls`` command
----------------------------------------------
The colors of the ``ls`` command may be hard to read in a dark terminal. If so, this is an excellent addition to the xonshrc file.

.. code-block:: xonshcon

    >>> $LS_COLORS='rs=0:di=01;36:ln=01;36:mh=00:pi=40;33:so=01;35:do=01;35:bd=40;33;01:cd=40;33;01:or=40;31;01:su=37;41:sg=30;43:ca=30;41:tw=30;42:ow=34;42:st=37;44:ex=01;32:'
