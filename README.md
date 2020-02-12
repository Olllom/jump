
jump
====

[![Conda Version](https://img.shields.io/conda/vn/conda-forge/jump.svg)](https://anaconda.org/conda-forge/jump) 
[![Conda Downloads](https://img.shields.io/conda/dn/conda-forge/jump.svg)](https://anaconda.org/conda-forge/jump) 

Running remote jupyter notebooks in a local browser window.

Free software: MIT license


Getting Started
---------------

```bash
conda install -c conda-forge jump
jump REMOTENAME
```

For options, type
```bash
jump --help
```

Examples
--------

Starting a new notebook server in remote conda environment `myenv` on a remote machine `mycluster`
```bash
jump mycluster -e myenv --new
```

Starting a new jupyter lab server in remote conda environment `myenv` on a remote machine `mycluster`
```bash
jump mycluster --lab -e myenv --new
```

Connecting to an existing jupyter server
```bash
jump mycluster -e myenv
```

Starting a new notebook server with remote module `cuda/9.2` loaded for GPU support
```bash
jump mycluster -e myenv --new -m cuda/9.2
```

Killing a notebook server
```bash
jump mycluster -e myenv --kill
```

Requirements
------------

On local (UNIX) machine:
- plumbum and click (are installed by the conda install command)
- ssh

On remote machine:
- anaconda or miniconda
- jupyter notebook (at least installed in one conda environment, jupyter > 5.1 required for the --kill option)
- jupyter lab (to support the `--lab` option)
- recommended: nb_conda

Windows systems are not supported.

Efficient SSH Setup
-------------------

In order to use this script efficiently, it is desirable to have
an efficient setup in your ~/.ssh/config file.

Concretely, you should prevent your ssh connection from prompting for
a password everytime you rune a local command, like this:

```
Host *
    ControlMaster auto
    ControlPath /tmp/ssh_mux_%h_%p_%r
    ControlPersist 60m
    ServerAliveInterval 90
```

Furthermore, you will want to set up shortcuts for the servers that
you use most often:

```
Host YOUR_SHORTCUT
    HostName FULL_REMOTE_NAME
    DynamicForward 8080
    User YOUR_USER_NAME_ON_THE_REMOTE`
```

If you have remotes that require tunneling through a login node,
you may also want to define those remotes explicitly:

```
Host NAME_OF_REMOTE
    ProxyCommand ssh FULL_LOGIN_NODE_NAME_OR_SHORTCUT -W %h:%p
```


