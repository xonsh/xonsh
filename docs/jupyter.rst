Xonsh kernel for Jupyter
========================

Xonsh provides a kernel for Jupyter Notebook and Lab so you can execute xonsh commands in a notbook cell without any additional magic.

Installation
-------------

Install Jupyter and Xonsh in the same environment, then configure the Xonsh kernel for Jupyter:

.. code-block:: xonshcon

    $ xonfig jupyter-kernel
    Installing Jupyter kernel spec:
      root: None
      prefix: <env_prefix>
      as user: False

_<Env_prefix>_ is the path prefix of the Jupyter and Xonsh environment.  ``xonfig jupyter-kernel --help`` shows options 
for installing the kernel spec in the user config folder or in a non-standard environment prefix.

You can confirm the status of the installation:

.. code-block:: xonshcon

    $ xonfig info
    +------------------+-----------------------------------------------------+
    | xonsh            | 0.9.21                                              |
    | Git SHA          | d42b4140                                            |
    
                   . . . . .

    | on jupyter       | True                                                |
    | jupyter kernel   | <env_prefix>\share\jupyter\kernels\xonsh            |
    +------------------+-----------------------------------------------------+

Or:

.. code-block:: xonshcon

    $ jupyter kernelspec list
    Available kernels:
      python3    <env_prefix>\share\jupyter\kernels\python3
      xonsh      <env_prefix>\share\jupyter\kernels\xonsh
     


