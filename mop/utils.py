import logging
import eyed3

from pathlib import Path
from typing import Optional
from eyed3.id3 import ID3_V1, ID3_DEFAULT_VERSION
from eyed3.core import AudioFile
from .config import getConfig

log = logging.getLogger(__name__)


def eyed3_load(path) -> Optional[AudioFile]:
    """Wrapper for eyed3.load.
    Adds the following members to AudioFile:
    - is_dirty
    - second_v1_tag
    - selected_tag
    """

    audio_file = eyed3.load(path)
    if audio_file and audio_file.info:
        log.debug(f"Handle audio file: {audio_file}")
        audio_file.second_v1_tag = None
        audio_file.selected_tag = None

        if audio_file.tag is None:
            audio_file.initTag(getConfig().preferred_id3_version or ID3_DEFAULT_VERSION)
        elif audio_file.tag.isV2():
            # v2 preferred, but there may also be an ID3 v1 tag
            v1_audio_file = eyed3.load(path, tag_version=ID3_V1)
            if v1_audio_file.tag:
                log.debug("Found extra v1 tag")
                audio_file.second_v1_tag = v1_audio_file.tag

        # Add flag for tracking edits
        audio_file.is_dirty = False

        return audio_file
    else:
        log.debug(f"Handle file: {path}")
        return None


def eyed3_load_dir(audio_dir) -> list:
    class FileHandler(eyed3.utils.FileHandler):
        def __init__(self):
            self.audio_files = []

        def handleDirectory(self, d, files):
            for f in files:
                if audio_file := eyed3_load(Path(d) / f):
                    self.audio_files.append(audio_file)

    if audio_dir is not None:
        handler = FileHandler()
        eyed3.utils.walk(handler, audio_dir, recursive=True)
        return handler.audio_files


def escapeMarkup(s: str) -> str:
    return s.replace("&", "&amp;")
