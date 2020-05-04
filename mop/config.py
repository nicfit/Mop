import os
import sys
import json
import textwrap
import importlib
from pathlib import Path
from logging import getLogger
from typing import Tuple
from dataclasses import dataclass, fields

log = getLogger(__name__)


__all__ = ["CONFIG_DIR", "Config", "getConfig", "getState"]

CONFIG_DIR = Path("~/.config/Mop/").expanduser()
CACHE_DIR = Path("~/.cache/Mop/").expanduser()
DEFAULT_STATE_FILE = CACHE_DIR / "mop.json"

# Global config and state
_config = None
_state = None


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
    from eyed3.id3 import ID3_V2_4, ID3_V1_1

    preferred_id3_v1_version = ID3_V1_1
    preferred_id3_v2_version = ID3_V2_4
    preferred_id3_version = preferred_id3_v2_version
    """).lstrip()

    def __init__(self):
        super().__init__(self.DEFAULT_PATH, default=self.DEFAULT_CONFIG)

        sys_path = list(sys.path)
        sys.path.append(str(self._cfg_file.parent.resolve()))
        try:
            self._cfg_mod = importlib.import_module(self._cfg_file.stem)
        except Exception as ex:
            log.error(f"Config file parse error: {ex}", exc_info=ex)
            self._cfg_mod = None

        sys.path.clear()
        sys.path.extend(sys_path)

    def __getattr__(self, attr):
        # Remember, the is only call for attrs not found thru normal means
        if self._cfg_file and hasattr(self._cfg_mod, attr):
            return getattr(self._cfg_mod, attr)
        return None


Config = _PyConfig


def getConfig() -> Config:
    """Get application config instance"""
    global _config

    if _config is None:
        _config = Config()
    return _config


@dataclass
class AppState:
    main_window_pos: Tuple[int, int] = None
    main_window_size: Tuple[int, int] = None
    file_open_cwd: str = None
    file_open_action: str = None

    def __post_init__(self):
        # Convert lists to tuples
        if type(self.main_window_size) is list:
            self.main_window_size = tuple(self.main_window_size)
        if type(self.main_window_pos) is list:
            self.main_window_pos = tuple(self.main_window_pos)

    def save(self, filename):
        state = {}
        for field in fields(self):
            value = getattr(self, field.name)
            state[field.name] = value
        Path(filename).write_text(json.dumps(state), "utf8")

    @classmethod
    def load(Class, filename):
        cache_file = Path(filename)
        if cache_file.exists():
            state_json = json.loads(Path(filename).read_text())
            return Class(**state_json)
        else:
            return Class()


def getState() -> AppState:
    """Get application state instance"""
    global _state

    if _state is None:
        _state = AppState.load(DEFAULT_STATE_FILE)
    return _state
