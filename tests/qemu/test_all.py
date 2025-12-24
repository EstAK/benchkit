import benchkit
from benchkit.helpers.qemu import QEMUConfig
from benchkit.helpers.linux.initramfs import InitBuilder
import pathlib


if __name__ == "__main__":
    qemu_config = QEMUConfig(
        number_of_cpus=4,
        memory=4069,
        kernel=pathlib.Path("./build/bzImage"),
        shared_dir="shared",
        enable_pty=True,
        artifacts_dir="./build",
        clean_build=False,
    )

    qemu_config.isolcpus([1, 4])
    qemu_config.init = InitBuilder.default()

    with qemu_config.spawn() as qemu:
        with qemu.open_pty() as pty:
            str_ = pty.shell(command="ls")
