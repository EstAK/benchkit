import benchkit
from benchkit.helpers.qemu import QEMU
import pathlib


if __name__ == "__main__":

    qemu = QEMU(number_of_cpus=4,
                memory=4069,
                kernel=pathlib.Path("./build/bzImage"),
                shared_dir="shared",
                enable_pty=True,
                artifacts_dir="./build",)

    with qemu as vm:
        pass

    pass
