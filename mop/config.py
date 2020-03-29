import os
import sys
import textwrap
import importlib
from pathlib import Path

__all__ = ["CONFIG_DIR", "Config", "getConfig"]

# Global config
_config = None
CONFIG_DIR = Path("~/.config/Mop/").expanduser()


class _ConfigFile:
    """
    Not a subclass of pathlib.Path but implements its interface.
    """
    def __init__(self, filename, default: str=None, mode=None):
        self._path = Path(str(filename)).expanduser()

        if not self.exists() and default is not None:
            if not self.parent.exists():
                self.parent.mkdir(parents=True)

            umask = os.umask(0)
            os.umask(umask)
            mode = mode or (0o666 ^ umask)
            self.touch(mode=mode)

            self.write_text(default, encoding="utf8")

        elif not self.exists():
            raise FileNotFoundError(str(self))

    def __getattr__(self, attr):
        return getattr(self._path, attr)


class _Config:
    DEFAULT_PATH = None
    DEFAULT_CONFIG = None

    def __init__(self, filename, **kwargs):
        self._cfg_file = _ConfigFile(filename, **kwargs)


class _PyConfig(_Config):
    DEFAULT_PATH = CONFIG_DIR / "mop_cfg.py"
    DEFAULT_CONFIG = textwrap.dedent("""
    from eyed3.id3 import ID3_ANY_VERSION, ID3_V2_4, ID3_V2_3, ID3_V1_1, ID3_V1_0

    preferred_id3_version = ID3_ANY_VERSION
    """).lstrip()

    def __init__(self):
        super().__init__(self.DEFAULT_PATH, default=self.DEFAULT_CONFIG)

        sys_path = list(sys.path)
        try:
            sys.path.append(str(self._cfg_file.parent.resolve()))
            self._cfg_mod = importlib.import_module(self._cfg_file.stem)
        finally:
            sys.path.clear()
            sys.path.extend(sys_path)

    def __getattr__(self, attr):
        # Config module first
        if hasattr(self._cfg_mod, attr):
            return getattr(self._cfg_mod, attr)
        # Self second
        else:
            return super().__getattr__(attr)


Config = _PyConfig


def getConfig() -> Config:
    """Get application config instance"""
    global _config

    if _config is None:
        _config = Config()
    return _config
