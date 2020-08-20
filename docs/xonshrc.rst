Run Control File
=========================
Xonsh allows you to have run control files to customize your shell behavior.  These are called ``xonshrc`` files.

The system-wide ``xonshrc`` file controls options that are applied to all users of Xonsh on a given system.  
You can create this file in ``/etc/xonshrc`` for Linux and OSX and in ``%ALLUSERSPROFILE%\xonsh\xonshrc`` on Windows.

Xonsh also allows you to have a run control file in your home directory. 
It can either be directly in the home directory at ``~/.xonshrc`` or for XDG compliance at ``~/.config/rc.xsh``. 
The options set in the local ``xonshrc`` only apply to the current user and will override any conflicting settings set in the system-wide control file.

These files are written in the xonsh language (a superset of Python). They are executed exactly once at startup.   
The control file usually contains:

* Assignment statements setting `environment variables <envvars.html>`_.  This includes standard OS environment variables that affect other programs and many that Xonsh uses for itself.
* Xonsh function defintions
* `Alias definitions <aliases.html>`_, many of which invoke the above functions with specified arguments.

The following is a real-world example of such a file.

:download:`Download xonshrc <xonshrc.xsh>`

.. include:: xonshrc.xsh
    :code: xonsh

Xonfig web
-----------

Xonsh provides a configuration wizard which helps you choose a color theme, customized prompt and add-in packages ("xontribs").  It 
initializes your personal run control file (usually at ``~/.xonshrc``).  To invoke it (from a xonsh prompt):

.. code-block:: xonshcon
  
  >>> xonfig web
  Web config started at 'http://localhost:8421'. Hit Crtl+C to stop.
  127.0.0.1 - - [23/Aug/2020 15:04:39] "GET / HTTP/1.1" 200 -

This will open your default browser on a page served from a local server.  You can exit the server by typing ``Ctrl+c`` at any time.

The page has:
 
:Colors: shows the  color themes built into Xonsh.  
  Simply click on a sample to select it.  Although color names are standardized across various terminal applications, 
  their actual appearance is not and do vary widely.  Seeing is believing! 
:Prompts: shows various sample prompts.  It is recommended to select one but to then edit the run control file to further refine your prompt.
:Xontribs: are community-contributed add-ins often used to enhance command completion and line editing, 
  but can affect any aspect of Xonsh behavior.  
  Choose one or more to suit your needs but note that they will require installation of additional
  packages.  You can extend Xonsh by `writing your own xontrib <tutorial_xontrib.html>`_, and are invited/urged to do so!
:Save: Click to write the configuration choices to your `~/.xonshrc`. This will add a few tagged lines to your run control file, but will not 
  overwrite it completely, so you can run `xonfig web` at any time.

Snippets for xonshrc
--------------------

The following are useful snippets and code that tweaks and adjust xonsh in various ways.
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


.. _customize the prompt: tutorial.html#customizing-the-prompt


Get better colors from the ``ls`` command
----------------------------------------------
The colors of the ``ls`` command may be hard to read in a dark terminal. If so, this is an excellent addition to the xonshrc file.

.. code-block:: xonshcon

    >>> $LS_COLORS='rs=0:di=01;36:ln=01;36:mh=00:pi=40;33:so=01;35:do=01;35:bd=40;33;01:cd=40;33;01:or=40;31;01:su=37;41:sg=30;43:ca=30;41:tw=30;42:ow=34;42:st=37;44:ex=01;32:'
    
Make JSON data directly pastable
--------------------------------
With the following snippet, xonsh will understand JSON data such as ``{ "name": "Tyler", "active": false, "age": null }``. 
Note that, though practical, this is rather hacky and might break other functionality. Use at your own risk.

.. code-block:: xonshcon

    >>> import builtins 
    >>> builtins.true = True
    >>> builtins.false = False
    >>> builtins.null = None
    
Display different date information every 10th time
---------------------------------------------------
For a compact shell prompts, some people prefer a very condensed time format. But when you have a lengthy shell session you might want the date to show up in your logs every now and then...

.. code-block:: xonshcon

    >>> import time
    >>> def get_shelldate():
    >>>     get_shelldate.fulldate %= 10 
    >>>     get_shelldate.fulldate += 1
    >>>     if get_shelldate.fulldate == 1:
    >>>         return time.strftime('%d%m%Y')
    >>>     return time.strftime('%H:%M')
    >>> get_shelldate.fulldate = 0
    >>> 
    >>> $PROMPT_FIELDS['shelldate'] = get_shelldate
    
Use the Nix Package manager with Xonsh
--------------------------------------
To users of the `Nix Package Manager <https://www.nixos.org/>`_ these few lines might be life-savers:

.. code-block:: xonshcon

    >>> import os.path
    >>> if os.path.exists(f"{$HOME}/.nix-profile") and not __xonsh__.env.get("NIX_PATH"):
    >>>     $NIX_REMOTE="daemon"
    >>>     $NIX_USER_PROFILE_DIR="/nix/var/nix/profiles/per-user/" + $USER
    >>>     $NIX_PROFILES="/nix/var/nix/profiles/default " + $HOME + "/.nix-profile"
    >>>     $NIX_SSL_CERT_FILE="/etc/ssl/certs/ca-certificates.crt"
    >>>     $NIX_PATH="nixpkgs=/nix/var/nix/profiles/per-user/root/channels/nixpkgs:/nix/var/nix/profiles/per-user/root/channels"
    >>>     $PATH += [f"{$HOME}/.nix-profile/bin", "/nix/var/nix/profiles/default/bin"]

Btw. a hacky solution to install xontribs that do not yet ship with ``nixpkgs`` is: 

.. code-block:: xonshcon

    >>> for p in map(lambda s: str(s.resolve()), p"~/.local/lib/".glob("python*/site-packages")):
    >>>     if p not in sys.path:
    >>>         sys.path.append(p)
    >>> 
    >>> $PYTHONPATH = "$USER/.local/lib/python3.7/site-packages"
    >>>     
    >>> python -m ensurepip --user
    >>> xonsh
    >>> python -m pip install --user -U pip xontrib-z xonsh-direnv

Just run the last three lines, do not put them in your `xonshrc`!
