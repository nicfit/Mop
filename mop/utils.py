import logging
from pathlib import Path
from typing import Optional
import eyed3
from eyed3.core import AudioFile

log = logging.getLogger(__name__)


def eyed3_load(path) -> Optional[AudioFile]:
    audio_file = eyed3.load(path)
    if audio_file and audio_file.info:
        log.debug(f"Handle audio file: {audio_file}")
        if audio_file.tag is None:
            audio_file.initTag()

        # Add flag for tracking edits
        audio_file.tag.is_dirty = False
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
