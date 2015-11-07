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



    
