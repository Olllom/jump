"""
Manage and connect to jupyter notebooks that are running on remote servers (in conda environments).
Requires the python packages click and plumbum on the local machine and conda (+ jupyter and nb_conda)
on the remote machine.

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
from collections import OrderedDict

from plumbum import SshMachine, BG, colors

import click


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
    def __init__(self, name, user=None):
        self.name = name
        self.user = user
        try:
            self.talk = self._collect_talk()
        except FileNotFoundError:
            raise JumpException("ssh seems to not be working on your machine. Unable to connect.")
        try:
            self.machine = SshMachine(self.name, user=self.user)
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

    def __call__(self, command):
        stdin, stdout, stderr = self.client.exec_command(command)
        return stdout

    def _collect_talk(self):
        """
        Visit remote to see if a stable connection can be established and find out if the remote talks about anything
        else than Jambalaya, Baby!
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

    def get_conda_envs(self):
        """
        Get the conda environments and their paths on the remote machine.

        Returns:
            A dictionary {env_name: env_path}
        """
        print(colors.green | "Retrieving a list of environments that are available on {} ...".format(self.name))
        # Running ssh as a subprocess to make sure conda is detected; conda is usually implemented as a bash function,
        # therefore not supported by plumbum's remote["command"] syntax.
        remotename = self.name if self.user is None else f"{self.user}@{self.name}"
        with subprocess.Popen(["ssh", remotename, "conda", "env", "list"],
                              stdout=subprocess.PIPE) as ssh_conda:
            env_list = ssh_conda.communicate()[0]
        env_list = self.strip_talk(env_list.decode("utf8")).split(os.linesep)
        env_dict = OrderedDict()
        for line in env_list:
            line = line.strip()
            if line.startswith('#'): continue
            if " conda " in line and "environments:" in line:
                continue
            line = line.replace("*","")
            env_dict[line.split()[0]] = line.split()[1]
        return env_dict


def get_free_local_socket():
    """
    Get a TCP port on the local machine that is not occupied by any process.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        addr = s.getsockname()
        return addr[1]


@click.command()
@click.argument("remote_name", type=str)
@click.option("-e", "--conda_env", default=None,
              help="Name of the remote conda environment")
@click.option("-u", "--user", default=None,
              help="User name on remote machine. Not required,"
                   "if your local ~/.ssh/config file is configured properly.")
@click.option("--kill/--no-kill", default=False,
              help="Kill notebook servers running on remote.")
def run_remote(remote_name, conda_env, user, kill):
    """
    Jump on a jupyter notebook that is running on a remote
    server in a conda environment.
    """
    if platform.system() == "Windows":
        raise JumpException("Sorry, Windows operating systems are not supported, yet.")

    print(colors.green | "Trying to establish a connection to {}".format(remote_name))
    remote = Remote(remote_name, user)

    # Check if conda environment is specified, else prompt for it
    conda_environment_paths = remote.get_conda_envs()
    if conda_env is None:
        for i, env in enumerate(conda_environment_paths):
            print(colors.blue | "{:>3}:    {:<35} {}".format(i+1, env, conda_environment_paths[env]))
        i = user_input(
            "Enter the ID of the remote conda environment that would you like to run the notebook in:",
            type_conversion=int,
            is_valid=lambda x: x>0 and x<=len(conda_environment_paths),
            hint="Enter a number between 1 and {}".format(len(conda_environment_paths))
        )
        conda_env = list(conda_environment_paths.items())[i-1][0]

    print(colors.green | "Trying to run jupyter notebook in remote conda environment {}".format(conda_env))

    # Get a list of running notebooks
    jupyter = remote.machine["{}/bin/jupyter".format(conda_environment_paths[conda_env])]
    try:
        running = jupyter("notebook", "list")
    except:
        raise JumpException("Fatal: Jupyter is not installed in remote conda environment {}".format(conda_env))
    running = remote.strip_talk(running).split(os.linesep)[1:]

    # no notebooks running: Ask the user, whether they want to start a new server
    if len(running) == 0:
        print(colors.warn | "No servers running on remote.")
        start_new = user_input(
            "Would you like to start a new jupyter notebook server? (y/n)",
            is_valid=lambda x: x in "yn",
            hint="Enter y or n."
        )
        if start_new == 'n':
            return 1
        else: # 'y'
            # Start notebook
            print("Starting notebook server on remote {} in environment {}".format(remote.name, conda_env))
            jupyter["notebook", "--no-browser"] & BG # running in the background

            # Wait for server to start; update list of running servers
            print("    Waiting for remote notebook server to start...")
            started = False
            while not started:
                time.sleep(1)
                running = jupyter("notebook", "list")
                running = remote.strip_talk(running).split(os.linesep)[1:]
                started = (len(running) > 0)
            print(colors.green | "Remote notebook server started.")

        # One notebook server running: Use this!
        if len(running) < 2:
            running = running[0]

        # Multiple notebook servers running: Ask the user which one to use
        else:
            print(colors.warn | "Multiple servers running on remote:")
            for i in range(len(running)):
                print(colors.blue | "  {:>3}: {}".format(i, running[i]))
            i = int(input("Which id would you like" + os.linesep))
            running = running[i]
        running = running.split(' :')[0]

        # Retrieve port number of remote notebook server
        print("Using running server.")
        print("    ", running)
        remote_port = running.split(":")[2].split("/")[0]
        remote_path = running.split("/")[3]

        # Kill
        if kill:
            killing = input(colors.red | "Would you like to kill the notebook server? (y/n)" + os.linesep)
            while killing not in ["y", "n"]:
                killing = input("Press y or n" + os.linesep)
            if killing == 'n':
                return 1
            else:
                print("Killing notebook server running on remote port {}".format(remote_port))
                jupyter("notebook", "stop", "{}".format(remote_port))
                print(colors.green | "Done.")
                return 1

        # Bind remote port to a free local port
        local_port = get_free_local_socket()
        local_url = "http://localhost:{}/{}".format(local_port, remote_path)
        print(colors.green | "Opening Tunnel between local port {} and remote port {}".format(local_port, remote_port))
        os.system("ssh -f {} -L {}:localhost:{} -N".format(remote.name, local_port, remote_port))

        # Open remote server in a local web browser
        print(colors.green | "Opening web browser at local url:")
        print("    ", local_url)
        webbrowser.open(local_url)


def main():
    try:
        returncode = run_remote()
    except JumpException as e:
        print(colors.red & colors.bold | str(e))
        sys.exit(1)
    sys.exit(returncode)
