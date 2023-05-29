
jump
====

[![Conda Version](https://img.shields.io/conda/vn/conda-forge/jump.svg)](https://anaconda.org/conda-forge/jump) 
[![Conda Downloads](https://img.shields.io/conda/dn/conda-forge/jump.svg)](https://anaconda.org/conda-forge/jump) 

Jump simplifies the process of starting and connecting to remote jupyter notebook servers. It support the creation of new notebook servers, as well as connecting to existing ones. It also supports the use of remote environments, such as conda/mamba or virtualenv environments. It can be very useful in particular when the connection to the remote machine is unstable.

Free software: MIT license

# Installation

With conda/mamba:

```bash
conda install -c conda-forge jump
```

with pip:

```bash
python -m pip install jump
```


# Getting Started


After the installation the executable `jump` should be available in your path. To open a new session on a remote machine using a conda enviroment, type


```bash
jump --env-type conda REMOTEMACHINE
```

# Features

- Start a new notebook server on a remote machine
- Connect to an existing notebook server on a remote machine
- Support for conda/mamba and virtualenv environments
- Support for jupyter lab
- Support for killing a notebook server


For options, type
```bash
jump --help
```

> **Warning**
> Jump do not kill automatically your sessions. Closing the browser tab will not kill the session on the server. You have to kill the session manually using the `kill` action. This feature is useful if your connection to the remote machine drops. In that case you only need to attach your session again.

# Examples

Starting a new notebook server in remote virtual environment `myenv` on a remote machine `REMOTEMACHINE` (`start` at the end is optional)

```bash
jump --env-type virtualenv --env-name myenv REMOTEMACHINE start
```

Starting a new jupyter lab server in remote conda environment `myenv` on a remote machine `REMOTEMACHINE`

```bash
jump --env-type conda --env-name myenv start REMOTEMACHINE --lab
```

Listing all the running notebook servers on a remote machine `REMOTEMACHINE`

```bash
jump --env-type mamba --env-name myenv REMOTEMACHINE list
```

Connecting to an existing jupyter server

```bash
jump --env-type conda --env-name myenv REMOTEMACHINE attach
```

Starting a new notebook server with remote module `cuda/9.2` loaded for GPU support

```bash
jump --env-type conda --env-name -m cuda/9.2 REMOTEMACHINE start
```

Killing a notebook server

```bash
jump --env-type conda --env-name myenv REMOTEMACHINE kill
```

Killing all notebook servers
```bash
jump  --env-type conda --env-name myenv REMOTEMACHINE kill --all
```

# Requirements

On local (UNIX) machine:
- plumbum and click (are installed automatically)
- ssh

On remote machine:
- anaconda/miniconda or mamba/micromamba or a virtualenv
- jupyter notebook (at least installed in one environment, jupyter > 5.1 required for the kill action)
- jupyter lab (to support the `--lab` option)

Windows systems are not supported.

# Efficient SSH Setup

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
