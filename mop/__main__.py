import sys
import pathlib
import logging
import argparse
from nicfit.logger import addCommandLineArgs as addLoggingArgs
from .app import MopApp
from .__about__ import version


class ArgumentParser(argparse.ArgumentParser):
    def __init__(self):
        super().__init__(prog="mop")
        self._initArgs()

    def _initArgs(self):
        self.add_argument("--version", action="version", version=f"%(prog)s {version}")
        addLoggingArgs(self, hide_args=True)
        self.add_argument("path_args", nargs="*", metavar="PATH", type=pathlib.Path,
                          help="An audio file or directory of audio files.")


def main():
    logging.basicConfig(stream=sys.stderr, level=logging.INFO)

    cli = ArgumentParser()
    args = cli.parse_args()

    app = MopApp()
    return app.run(args)


if __name__ == "__main__":
    sys.exit(main() or 0)
