# Copyright (C) 2025 Vrije Universiteit Brussel. All rights reserved.
# SPDX-License-Identifier: MIT

from __future__ import annotations

import fcntl
from io import TextIOWrapper
import pty
import select
import os
import subprocess
from typing import BinaryIO, List

from benchkit.communication import CommunicationLayer
from benchkit.utils.types import PathType, Command

CHUNK_SIZE: int = 1024

class PTYException(Exception):
    pass


class PTYCommLayer(CommunicationLayer):
    def __init__(
            self,
            port: PathType,

    ) -> None:
        self._port: PathType = port
        self._fd: int | None = None

        super().__init__()


    def start_comm(self):
        self._fd = os.open(self._port, os.O_RDWR | os.O_NOCTTY)

    def close_comm(self):
        #Exception handling here
        if self._fd is not None:
            self._fd.close()
        else:
            raise PTYException("The comm layer was manually closed or something else smh")
        
    def __enter__(self):
        # open and close file descriptors on demand to not maintain a fd opened for nothing
        if self._fd is None:
            self.start_comm()
        else:
            raise PTYException("The PTY was already initialized or failed to properly close")

    def __exit__(self, exception_type, exception_value, exception_traceback):
        self.close_comm()

    @property
    def remote_host(self) -> str | None:
        """Returns an identifier (typically hostname) of the remote host, or None if communication
        happens locally.

        Returns:
            str | None: name of the remote host or None if communication happens locally.
        """
        raise None

    @property
    def is_local(self) -> bool:
        """Returns whether the communication layer happens locally on the host.

        Returns:
            bool: whether the communication layer happens locally on the host.
        """
        raise False

    @property
    def ip_address(self) -> str:
        """Returns the IP address of the host.

        Returns:
            str: IP address of the host.
        """
        raise NotImplementedError() # this is not a certainty for all devices

    def pipe_shell(
        self,
        command: Command,
        current_dir: Optional[PathType] = None,
        shell: bool = False,
        print_command: bool = True,
        ignore_ret_codes: Iterable[int] = (),
    ):
        raise NotImplementedError()

    def shell(
        self,
        command: Command,
        std_input: str | None = None,
        current_dir: PathType | None = None,
        environment: Environment = None,
        shell: bool = False,
        print_input: bool = True,
        print_output: bool = True,
        print_curdir: bool = True,
        timeout: int = 1,
        output_is_log: bool = False,
        ignore_ret_codes: Iterable[int] = (),
        ignore_any_error_code: bool = False,
    ) -> str:
        """Run a shell command on the target host.

        Args:
            command (Command):
                command to run on the target host.
            std_input (str | None, optional):
                input to pipe into the command to run, None if there is no input to provide.
                Defaults to None.
            current_dir (PathType | None, optional):
                directory where to run the command. Defaults to None.
            environment (Environment, optional):
                environment to pass to the command to run. Defaults to None.
            shell (bool, optional):
                whether a shell must be created to run the command. Defaults to False.
            print_input (bool, optional):
                whether to print the command on benchkit logs. Defaults to True.
            print_output (bool, optional):
                whether to print the command output on benchkit logs. Defaults to True.
            print_curdir (bool, optional):
                whether to print the current directoru on benchkit logs. Defaults to True.
            timeout (int):
                number of seconds to wait for the command to complete, or None for no timeout.
                Defaults to None.
            output_is_log (bool, optional):
                whether the output of the command is expected to be logging (e.g., when running
                `cmake`). If it is the case, the logging will be printed in a `tail -f` fashion.
                Defaults to False.
            ignore_ret_codes (Iterable[int], optional):
                List of error code to ignore if it is the return code of the command.
                Defaults to () (empty collection).
            ignore_any_error_code (bool, optional):
                whether to error any error code returned by the command.

        Returns:
            str: the output of the command.
        """
        if current_dir != None             \
                or shell != False          \
                or print_curdir == True    \
                or output_is_log == True   \
                or ignore_ret_codes != ()  \
                or ignore_any_error_code != False:

            raise PTYException("Not supported attributes")

        command_str:str = ""
        if environment is not None:
            environment: List[str] =[f"{k}={v}" for k,v in dict(environment).items()]
            command_str += " ".join(environment)

        command_str += str(command)
        if std_input is not None:
            command_str += f"| {std_input}"

        if print_input:
            print(command_str) # is that the benchkit logs ?

        if self._fd is not None:
            buf = bytearray()
            while True:
                r, _, _ = select.select([self._fd], [], [], float(timeout))
                if not r:
                    break
                chunk = os.read(self._fd, CHUNK_SIZE)
                buf.extend(chunk)

            output: str = buf.decode(errors="replace")
            if print_output:
                print(output)
            return output
        else:
            raise PTYException("Open the communication before sending a command")

    def shell_succeed(
        self,
        command: Command,
        std_input: str | None = None,
        current_dir: PathType | None = None,
        environment: Environment = None,
        shell: bool = False,
        print_input: bool = True,
        print_output: bool = True,
        print_curdir: bool = False,
        timeout: int | None = None,
        output_is_log: bool = False,
        ignore_ret_codes: Iterable[int] = (),
    ) -> bool:
        """Executes a command and return whether it succeeded without error.

        Args:
            command (Command):
                command to run on the target host.
            std_input (str | None, optional):
                input to pipe into the command to run, None if there is no input to provide.
                Defaults to None.
            current_dir (PathType | None, optional):
                directory where to run the command. Defaults to None.
            environment (Environment, optional):
                environment to pass to the command to run. Defaults to None.
            shell (bool, optional):
                whether a shell must be created to run the command. Defaults to False.
            print_input (bool, optional):
                whether to print the command on benchkit logs. Defaults to True.
            print_output (bool, optional):
                whether to print the command output on benchkit logs. Defaults to True.
            print_curdir (bool, optional):
                whether to print the current directoru on benchkit logs. Defaults to True.
            timeout (int | None, optional):
                number of seconds to wait for the command to complete, or None for no timeout.
                Defaults to None.
            output_is_log (bool, optional):
                whether the output of the command is expected to be logging (e.g. when running
                `cmake`). If it is the case, the logging will be printed in a `tail -f` fashion.
                Defaults to False.
            ignore_ret_codes (Iterable[int], optional):
                List of error code to ignore if it is the return code of the command.
                Defaults to () (empty collection).

        Returns:
            bool: whether the executed command succeeded without error.
        """
        succeed = True
        try:
            self.shell(
                command=command,
                std_input=std_input,
                current_dir=current_dir,
                environment=environment,
                shell=shell,
                print_input=print_input,
                print_output=print_output,
                print_curdir=print_curdir,
                timeout=timeout,
                output_is_log=output_is_log,
                ignore_ret_codes=ignore_ret_codes,
            )
        except subprocess.CalledProcessError:
            succeed = False
        return succeed

    def background_subprocess(
        self,
        command: Command,
        stdout: PathType,
        stderr: PathType,
        cwd: PathType | None,
        env: dict | None,
        establish_new_connection: bool = False,
    ) -> subprocess.Popen:
        """Start a background process with the provided command.

        Args:
            command (Command):
                background command to run on the target host.
            stdout (PathType):
                path to the file where to write the stdout output of the background process.
            stderr (PathType):
                path to the file where to write the stderr output of the background process.
            cwd (PathType | None):
                working directory of the background command to run.
            env (dict | None):
                environment variables to pass to the command to run.
            establish_new_connection (bool, optional):
                whether to establish a new connection to the background process.

        Returns:
            subprocess.Popen: the process handle from the subprocess module.
        """
        raise NotImplementedError()

    def signal(
        self,
        pid: int,
        signal_code: int,
    ) -> None:
        """Send a signal to the given process.

        Args:
            pid (int): pid of the process to send the signal to.
            signal_code (int): code of the signal to send.
        """
        self.shell(command=f"kill -{signal_code} {pid}")

    def get_process_nb_threads(
        self,
        process_handle: subprocess.Popen,
    ) -> int:
        """get number of threads of the given process.

        Args:
            process_handle (subprocess.Popen): process to query.

        Returns:
            int: _description_
        """
        raise NotImplementedError(
            "TODO not implemented on remote: we need the pid of the remote process... "
            "(I don't know how to do it now)"
        )

    def get_process_status(
        self,
        process_handle: subprocess.Popen,
    ) -> str:
        """get status of the given process.

        Args:
            process_handle (subprocess.Popen): process to query.

        Returns:
            str: status of the given process.
        """
        raise NotImplementedError(
            "TODO not implemented on remote: we need the pid of the remote process... "
            "(I don't know how to do it now)"
        )

    def path_exists(
        self,
        path: PathType,
    ) -> bool:
        """Whether the given path exist on the target host.

        Args:
            path (PathType): path to check existence.

        Returns:
            bool: whether the given path exist on the target host.
        """
        raise NotImplementedError()

    def read_file(
        self,
        path: PathType,
    ) -> str:
        """Read content of given filename on target host.
        Communication-aware equivalent of `file.read()`.

        Args:
            path (PathType): path of the file to read on the target host.

        Returns:
            str: content of the file.
        """
        raise NotImplementedError()

    def file_size(
        self,
        path: PathType,
    ) -> int:
        """Gets the size of the given file on target host.

        Args:
            path (PathType): path of the file on the target host.

        Returns:
            int: size of the file.
        """
        raise NotImplementedError()

    def write_content_to_file(
        self,
        content: str,
        output_filename: PathType,
        privileged: bool = False,
    ) -> None:
        """Write given content on the given file on the target host.
        Communication-aware equivalent of `file.write()`.

        Args:
            content (str): content of the file to write.
            output_filename (PathType): path of the file where to write the content on the target
                                        host.
            privileged (bool, optional): whether the write operation needs to be root.
                                         Defaults to False.
        """
        raise NotImplementedError()

    def append_line_to_file(
        self,
        line: str,
        output_filename: PathType,
        privileged: bool = False,
    ) -> None:
        """Append given line on the given file on the target host.

        Args:
            line (str): line to append.
            output_filename (PathType): path of the file where to append the content on the target
                                        host.
            privileged (bool, optional): whether the write operation needs to be root.
                                         Defaults to False.
        """
        raise NotImplementedError

    def host_to_comm_path(self, host_path: Path) -> Path:
        """
        Convert a path from the host namespace to the namespace visible to the communication
        platform (e.g., container, remote host).

        This function is used to adapt paths that Benchkit generates (e.g., to save results)
        into equivalent paths visible inside the platform that actually runs the benchmark.

        Default behavior assumes a shared filesystem and returns the original path.

        Override in platform-specific subclasses if path rewriting is required
        (e.g., Docker volume mounts or remote mount points).

        Args:
            host_path (Path): Absolute path on the host machine.

        Returns:
            Path: Corresponding path visible to the communication platform.
        """
        return host_path

    def comm_to_host_path(self, comm_path: Path) -> Path:
        """
        Convert a platform-side path (e.g., from inside a container or remote node)
        to the corresponding host-side path.

        Default implementation assumes the platform shares the host filesystem and performs
        no rewriting. Override in subclasses if path translation is required.

        Args:
            comm_path (Path): Path as seen by the platform.

        Returns:
            Path: Corresponding path on the host system.
        """
        return comm_path

    def copy_from_host(self, source: PathType, destination: PathType) -> None:
        """Copy a file from the host (the machine benchkit is run on), to the
           target machine the benchmark will be performed on.

        Args:
            source (PathType): The source path where the file or folder is stored.
            destination: (PathType): The destination path where the file has to be
                                     copied to on the remote.
        """
        raise NotImplementedError("Copy from host is not implemented for this communication layer")

    def copy_to_host(self, source: PathType, destination: PathType) -> None:
        """Copy a file to the host (the machine benchkit is run on), from the
           target machine the benchmark will be performed on.

        Args:
            source (PathType): The source path where the file or folder is stored on the remote.
            destination: (PathType): The destination path where the file has to be
                                     copied to on the host.
        """
        raise NotImplementedError("Copy to host is not implemented for this communication layer")

    def hostname(self) -> str:
        """Get hostname of the target host.

        Returns:
            str: hostname of the target host.
        """
        result = self.shell(
            command="hostname",
            print_input=False,
            print_output=False,
        ).strip()
        return result

    def current_user(self) -> str:
        """Get current user in the target host.

        Returns:
            str: current user in the target host.
        """
        result = self.shell(
            command="whoami",
            print_input=False,
            print_output=False,
        ).strip()
        return result

    def realpath(self, path: PathType) -> Path:
        """Get real path, following symlinks, of the given path.
        Communication aware equivalent of path.resolve().

        Args:
            path (PathType): path on the host to get.

        Returns:
            pathlib.Path: absolute and real path.
        """
        output = self.shell(
            command=f"readlink -fm {path}",
            print_input=False,
            print_output=False,
        ).strip()
        result = Path(output)
        return result

    def isfile(self, path: PathType) -> bool:
        """Return whether the given path is a file on the target host.
        Communication-aware equivalent of `path.is_file()`.

        Args:
            path (PathType): path to the given file to check.

        Returns:
            bool: whether the given path is a file on the target host.
        """
        return self._bracket_test(path=path, opt="-f")

    def makedirs(self, path: PathType, exist_ok: bool) -> None:
        """Create a directory on the target host, with all the path leading to it.
        Communication-aware equivalent of `mkdir -p /path1/path2/path3`.

        Args:
            path (PathType): path of the new directory to create on the target host.
            exist_ok (bool): whether to ignore the fact that directory might already exist.
        """
        exist_opt = " -p " if exist_ok else ""
        self.shell(
            command=f"mkdir{exist_opt} {path}",
            print_input=False,
            print_output=False,
        )

    def remove(self, path: PathType, recursive: bool) -> None:
        """Remove a file or directory on the target host.

        Args:
            path (PathType): path of file or directory that needs to be removed on the target host.
            recursive (bool): whether to recursively delete everything in this path.
        """
        command = ["rm"] + (["-r"] if recursive else []) + [str(path)]
        self.shell(
            command=command,
            print_input=False,
            print_output=False,
        )

    def isdir(self, path: PathType) -> bool:
        """Return whether the given path is a file on the target host.
        Communication-aware equivalent of `path.is_dir()`.

        Args:
            path (PathType): path to the given directory to check.

        Returns:
            bool: whether the given path is a directory on the target host.
        """
        return self._bracket_test(path=path, opt="-d")

    def which(self, cmd: str) -> Path | None:
        """Return the absolute path of a given executable in the path.

        Args:
            cmd (str): the executable command to find.

        Returns:
            pathlib.Path | None: the absolute path to the command executable or None if the command
                                 is not found.
        """
        command = f"which {cmd}"
        which_succeed = self.shell_succeed(
            command=command,
            print_input=False,
            print_output=False,
        )

        if not which_succeed:
            return None

        path = self.shell(
            command=command,
            print_input=False,
            print_output=False,
        ).strip()

        if not path:
            return None

        result = Path(path)
        return result

    def _bracket_test(
        self,
        path: PathType,
        opt: str,
    ) -> bool:
        succeed = True
        try:
            self.shell(command=f"[ {opt} {path} ]", print_input=False, print_output=False)
        except subprocess.CalledProcessError as cpe:
            if 1 != cpe.returncode:
                raise cpe
            succeed = False
        return succeed
    
