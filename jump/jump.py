"""
Manage and connect to jupyter notebooks/labs on remote servers.

Run `jump.py --help` for usage instructions.
"""

import sys
import os
import time
import webbrowser
import socket
import subprocess
import platform
import textwrap
import re
import json
import urllib
import click

from plumbum import SshMachine, BG, colors
from jump import __version__


class JumpException(Exception):
    pass


def user_input(question, is_valid=lambda _: True, type_conversion=str, hint=""):
    """
    Request input from the command line.

    Args:
         question (str): The question to ask the user.
         is_valid (callable): A function that checks the user's response for validity and returns a boolean.
         type_conversion (callable): A function that converts the input string into whatever type is expected.
         hint (str): A hint to print to the command line in case of an invalid user response.
    """
    while True:
        answer = input(question + os.linesep)
        try:
            answer = type_conversion(answer)
            assert is_valid(answer)
            return answer
        except:
            print(colors.warn | "Input not understood." + os.linesep + hint + os.linesep)


class Remote(object):
    """Wrapper for a remote machine."""
    def __init__(self, name, user=None, password=None):
        self.name = name
        self.user = user
        self.password = password
        try:
            self.talk = self._collect_talk()
        except FileNotFoundError:
            raise JumpException("ssh seems to not be working on your machine. Unable to connect.")
        try:
            self.machine = SshMachine(self.name, user=self.user, password=self.password)
        except ValueError as e:
            if "write to closed file" in str(e):
                raise JumpException(textwrap.dedent(
                    """
                    The initial authentification was successful, but your ssh configuration seems to not support multiplexing.
                    Jump needs ssh multiplexing to work smoothly, i.e. the connection must be kept open.
                    To enable it, add the following lines to your ~/.ssh/config and retry:
                
                    Host * 
                        ControlMaster auto
                        ControlPath /tmp/ssh_mux_%h_%p_%r
                        ControlPersist 30m
                        ServerAliveInterval 90
                        
                    """))

    def __del__(self):
        if hasattr(self, "ssh_machine"):
            self.ssh_machine.close()

    def _collect_talk(self):
        """
        Visit remote to see if a stable connection can be established and find out if the remote talks about anything
        else than Jambalayalaya
        """
        # This is the initial connection to the server.
        # In order to support every possible authentification pattern expected by the remote, this command
        # is called as a subprocess rather than through plumbum or paramiko. How to provide the same flexibility in
        # those packages is not obvious to me.
        remotename = self.name if self.user is None else f"{self.user}@{self.name}"
        with subprocess.Popen(["ssh", remotename, 'echo "Jambalayalaya"'], stdout=subprocess.PIPE) as ssh:
            output = ssh.communicate()[0]
            if ssh.returncode:
                raise JumpException(f"Failed to connect to server. Make sure that you have a stable connection and "
                                    f"that the server {self.name} exists.")
            else:
                output = output.decode("utf8")
                assert "Jambalayalaya" in output
                talk = output.strip().split("Jambalayalaya")
        return talk

    def strip_talk(self, output):
        """
        Strip any unrelated talking from the remote's output.
        """
        output = output.strip()
        if len(self.talk[0]) > 0 and output.startswith(self.talk[0]):
            output = output[len(self.talk[0]):]
        if len(self.talk[1]) > 0 and output.endswith(self.talk[1]):
            output = output[:-len(self.talk[1])]
        return output

    def run_with_shell(self, command):
        """
        Run a command on the remote machine using the shell and set the environment variables

        Args:
            command (str): The command to run.

        Returns:
            The output of the command.
        """
        output = self.machine["sh"]("-c", "%s && env" % command)
        re_valid_path = re.compile(r'[^\s=\(\)%]+=')
        dic = {line.split('=',1)[0]:line.split('=',1)[1] for line in output.splitlines() if re_valid_path.match(line)}
        self.machine.env.update(dic)

        return output

    def get_list_notebooks(self, jupyter):
        """
        Get a list of all notebooks that are currently running on the remote machine.

        Returns:
            A list of dictionaries, each containing the information about a single notebook.
        """
        print(colors.green | "Retrieving a list of notebooks that are currently running on {} ...".format(self.name))
        try:
            running = jupyter("notebook", "list")
        except:
            raise JumpException("Fatal: Jupyter is not installed in remote environment. No executable {}".format(jupyter))
        running = self.strip_talk(running).split(os.linesep)[1:]
        return running

    def activate_virtualenv(self, env_name):
        self.run_with_shell(". %s/bin/activate" % env_name)

    def get_envs(self, package_manager):
        if package_manager in ("conda", "miniconda"):
            return self.get_conda_envs()
        elif package_manager in ("mamba", "micromamba"):
            return self.get_mamba_envs()
        else:
            raise JumpException("Package manager {} is not supported.".format(package_manager))

    def get_mamba_envs(self):
        print(colors.green | "Retrieving a list of mamba envs that are available on {} ...".format(self.name))
        self.run_with_shell(". $HOME/.bashrc")
        exe = self.machine.env['MAMBA_EXE']
        output = self.machine[exe]('env', 'list', '--json')
        
        env_list = json.loads(output)['envs']
        env_dict = {os.path.basename(env): env for env in env_list}
        if self.machine.env['MAMBA_ROOT_PREFIX'] in env_dict.values():
            env_dict['base'] = self.machine.env['MAMBA_ROOT_PREFIX']
        return env_dict

    def get_conda_envs(self):
        print(colors.green | "Retrieving a list of conda envs that are available on {} ...".format(self.name))
        self.run_with_shell(". $HOME/.bashrc")
        exe = self.machine.env['CONDA_EXE']
        output = self.machine[exe]('env', 'list', '--json')
        
        env_list = json.loads(output)['envs']
        env_dict = {os.path.basename(env): env for env in env_list}
        conda_base_path = self.machine.env['CONDA_EXE'].replace('/bin/conda', '')
        if conda_base_path in env_dict.values():
            env_dict['base'] = conda_base_path
        return env_dict

    def start_jupyter_server(self, jupyter_command, modules, running_servers, use_jupyter_lab=False):
        """
        Start a new jupyter server.

        Args:
            jupyter_command (plumbum remote command): The jupyter executable on the remote
            modules (iterable): A list or tuple of modules that should be loaded on the remote
            running_servers (list): A list of servers that are running
            use_jupyter_lab (bool): True to start a jupyter lab server, False for a jupyter notebook server.

        Returns:
            running_servers (list): Updated list of running servers
            server_id (list): Index of the server that was just started
        """
        subcommand = "lab" if use_jupyter_lab else "notebook"
        if modules:
            # try if the module loading works
            print(f"    Trying to load modules {modules}")
            load_command = " && module load ".join([". /etc/profile"] + list(modules))
            with subprocess.Popen(["ssh", self.name, load_command]) as ssh:
                ssh.communicate()
                if ssh.returncode:
                    raise JumpException(f"Failed to load modules")
            print(f"    Module loading successful")
            # Start the server
            print(colors.green | f"    Trying to start server with modules loaded")
            notebook_command = f'{load_command} && {jupyter_command.executable} {subcommand} --no-browser &'
            subprocess.Popen(["ssh", self.name, notebook_command], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL)

        else:
            jupyter_command[subcommand, "--no-browser"] & BG  # running in the background

        # Wait for server to start; update list of running servers
        print("    Waiting for remote jupyter server to start...")
        running = []
        while len(running) <= len(running_servers):
            time.sleep(1)
            running = jupyter_command("notebook", "list")
            running = self.strip_talk(running).split(os.linesep)[1:]
        new_servers = [i for i,s in enumerate(running) if s not in running_servers]
        assert len(new_servers) == 1
        print(colors.green | "Remote jupyter server started.")
        return running, new_servers[0]


def get_free_local_socket():
    """
    Get a TCP port on the local machine that is not occupied by any process.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        addr = s.getsockname()
        return addr[1]


def open_local(url_remote, remote_host):
    """
    Open a remote url in a local web browser.
    """
    url_parsed = urllib.parse.urlparse(url_remote)

    # Bind remote port to a free local port
    local_port = get_free_local_socket()
    local_url = url_parsed._replace(netloc="localhost:{}".format(local_port)).geturl()
    print(colors.green | "Opening Tunnel between local port {} and remote port {}".format(local_port, url_parsed.port))
    os.system("ssh -f {} -L {}:localhost:{} -N".format(remote_host, local_port, url_parsed.port))

    # Open remote server in a local web browser
    print(colors.green | "Opening web browser at local url:")
    print("    ", local_url)
    webbrowser.open(local_url)


@click.group(invoke_without_command=True)
@click.argument("remote_hostname", type=str)
@click.option("-u", "--user", default=None,
              help="User name on remote machine. Not required,"
                   "if your local ~/.ssh/config file is configured properly.")
@click.option("--password", default=None, help="the ssh password.")
@click.option("-e", "--env-name", default=None,
              help="Name of the remote environment")
@click.option("--env-type", type=click.Choice(["conda", "miniconda", "mamba", "micromamba", "virtualenv", "none"]), default="conda",
              help="Type of the remote environment")
@click.option("--setup-script", default=None, help='Script to be executed before starting up the jupyter server.')
@click.option("-m", "--module", multiple=True, help="Modules to be loaded before starting up the jupyter server.")
@click.option("-j", "--jupyter-command", default=None, help="Jupyter command on the remote.")
@click.version_option(__version__)
@click.pass_context
def cli(ctx, remote_hostname, user, password, env_name, env_type, setup_script, module, jupyter_command):
    if platform.system() == "Windows":
        raise JumpException("Sorry, Windows operating systems are not supported, yet.")

    ctx.ensure_object(dict)

    print(colors.green | "Trying to establish a connection to {}".format(remote_hostname))
    remote = Remote(remote_hostname, user, password)

    if setup_script is not None:
        print(colors.green | "Trying to run setup script {}".format(setup_script))
        remote.run_with_shell(setup_script)

    if env_type == "none":
        if env_name is not None:
            raise JumpException("Fatal: --env-name specified, but no --env-type specified")
        # no environment specified, use jupyter from the system environment
        default_jupyter_command = "jupyter"
    elif env_type == 'virtualenv':
        if env_name is None:
            raise JumpException("Fatal: --env-name must be specified for virtualenvs")
        print(colors.green | "Setup virtualenv %s" % env_name)
        remote.activate_virtualenv(env_name)
        default_jupyter_command = "jupyter"
    else:
        available_envs = remote.get_envs(env_type)
        if env_name is not None:
            if env_name not in available_envs:
                raise JumpException("Fatal: Environment {} not found in remote machine, list of available environments: {}".format(env_name, available_envs))
            default_jupyter_command = '%s/bin/jupyter' % available_envs[env_name]
        else:
            for i, (proposed_envname, proposed_envpath) in enumerate(available_envs.items()):
                print(colors.blue | "{:>3}:    {:<35} {}".format(i+1, proposed_envname, proposed_envpath))
            i = user_input(
                "Enter the ID of the remote conda environment that you would like to run the jupyter server in:",
                type_conversion=int,
                is_valid=lambda x: 0 < x <= len(available_envs),
                hint="Enter a number between 1 and {}".format(len(available_envs))
            )
            env_name = list(available_envs.keys())[i]
            default_jupyter_command = '%s/bin/jupyter' % available_envs[env_name]

    if jupyter_command is None:
        jupyter_command = default_jupyter_command
    jupyter = remote.machine[jupyter_command]


    # Get a list of running servers
    running = remote.get_list_notebooks(jupyter)

    ctx.obj["remote_hostname"] = remote_hostname
    ctx.obj["remote"] = remote
    ctx.obj['jupyter'] = jupyter
    ctx.obj["module"] = module
    ctx.obj["running"] = running

    if ctx.invoked_subcommand is None:
        if len(running) == 0:
            ctx.invoke(start, lab=False)
        else:
            ctx.invoke(attach)


@cli.command()
@click.pass_context
def attach(ctx):
    """
    Jump on a running jupyter kernel running on the remote host
    """
    remote = ctx.obj["remote"]
    running = ctx.obj["running"]

    if len(running) == 0:
        print(colors.warn | "No servers running on remote.")
        return
    elif len(running) == 1:
        server_id = 0
    elif len(running) > 1:
        print(colors.warn | "Multiple servers running on remote:")
        for i in range(len(running)):
            print(colors.blue | "  {:>3}: {}".format(i+1, running[i]))
        server_id = user_input(
            "Which id would you like? ",
            type_conversion=int,
            is_valid=lambda x: 1 <= x <= len(running),
            hint=f"Enter a number between 1 and {len(running)}"
        ) - 1

    notebook_server = running[server_id].split(' :')[0]
    print(f"Using server: {notebook_server}")
    open_local(notebook_server, remote.name)


@cli.command("list")
@click.pass_context
def list_notebooks(ctx):
    """
    List all running jupyter servers on a remote host
    """
    running = ctx.obj["running"]
    
    print('\n'.join(running))


@cli.command()
@click.option("--lab/--no-lab", default=False,
              help="Start a jupyter lab server instead of a regular notebook server. ")
@click.pass_context
def start(ctx, lab):
    """
    Start a new jupyter server on the remote host
    """

    remote = ctx.obj["remote"]
    jupyter = ctx.obj["jupyter"]
    module = ctx.obj["module"]
    running = ctx.obj["running"]

    print(f"Starting {'lab' if lab else 'notebook'} server on remote {remote.name}")
    running, server_id = remote.start_jupyter_server(jupyter, module, running, use_jupyter_lab=lab)

    notebook_server = running[server_id].split(' :')[0]

    # Retrieve port number of remote notebook server
    print(f"Using server: {notebook_server}")

    open_local(notebook_server, remote.name)


@cli.command()
@click.option("-a", "--all", "killall", is_flag=True, default=False)
@click.pass_context
def kill(ctx, killall=False):
    """ kill a remote jupyter server """
    print(colors.green | f"Killing jupyter server on {ctx.obj['remote_hostname']}")
    jupyter = ctx.obj['jupyter']
    remote = ctx.obj['remote']
    running = ctx.obj['running']
    
    server_to_be_killed = []

    if len(running) == 0:
        print(colors.warn | "No servers running on remote, cannot kill.")
        return 1
    elif killall:
        server_to_be_killed = running[:]
    elif len(running) == 1:
        server_to_be_killed = [running[0]]
    elif len(running) > 1:
        # Multiple servers running: Ask the user which one to use
        print(colors.warn | "Multiple servers running on remote:")
        for i in range(len(running)):
            print(colors.blue | "  {:>3}: {}".format(i+1, running[i]))
        server_id = user_input(
            "Which id would you like? (use 0 to kill all of them) ",
            type_conversion=int,
            is_valid=lambda x: 0 <= x <= len(running),
            hint=f"Enter a number between 0 and {len(running)}"
        ) - 1

        if server_id != -1:
            server_to_be_killed = [running[server_id]]
        else:
            server_to_be_killed = running[:]

    for server in server_to_be_killed:
        # Retrieve port number of remote notebook server
        url_server = server.split("::")[0]
        remote_port = urllib.parse.urlparse(url_server).port

        print(f"Killing jupyter server {server} running on remote port {remote_port}")
        jupyter("notebook", "stop", "{}".format(remote_port))
    print(colors.green | "Done.")
    return 1



def main():
    try:
        returncode = cli(obj={})
    except JumpException as e:
        print(colors.red & colors.bold | str(e))
        sys.exit(1)
    sys.exit(returncode)
