====
jump
====

Running remote jupyter notebooks in a local browser window.

Free software: MIT license



Requirements
------------

On local (UNIX) machine:
- plumbum and click
- ssh

On remote machine:
- anaconda or miniconda
- jupyter notebook (at least installed in one conda environment,
  jupyter > 5.1 required for the --kill option)
- recommended: nb_conda

Efficient SSH Setup
-------------------

In order to use this script efficiently, it is desirable to have
an efficient setup in your ~/.ssh/config file.

Concretely, you should prevent your ssh connection from prompting for
a password everytime you rune a local command, like this::

Host *
    ControlMaster auto
    ControlPath /tmp/ssh_mux_%h_%p_%r
    ControlPersist 60m
    ServerAliveInterval 90

Furthermore, you will want to set up shortcuts for the servers that
you use most often::

Host YOUR_SHORTCUT
    HostName FULL_REMOTE_NAME
    DynamicForward 8080
    User YOUR_USER_NAME_ON_THE_REMOTE

If you have remotes that require tunneling through a login node,
you may also want to define those remotes explicitly:

Host NAME_OF_REMOTE
    ProxyCommand ssh FULL_LOGIN_NODE_NAME_OR_SHORTCUT -W %h:%p

