import logging
from pathlib import Path
from gi.repository import GObject, Gtk, Pango
from eyed3.core import AudioFile

log = logging.getLogger(__name__)


class AudioFileListStore:
    # Column indexes
    FILENAME = 0
    TRACK_NUM = 1
    TITLE = 2
    ARTIST = 3
    ALBUM = 4
    TEXT_WEIGHT = 5

    model_map = {
        FILENAME: ("Filename", str),
        TRACK_NUM: ("Track", str),
        TITLE: ("Title", str),
        ARTIST: ("Artist", str),
        ALBUM: ("Album", str),
        TEXT_WEIGHT: ("__text_weight__", int),
    }

    def __init__(self):
        self._audio_files = {}  # Relies on py3.7 ordered dict.
        self._list_store = Gtk.ListStore(*(spec[1] for spec in self.model_map.values()))

    @property
    def store(self):
        return self._list_store

    def __len__(self):
        return len(self._list_store)

    def clear(self):
        self._audio_files.clear()
        self._list_store.clear()

    @staticmethod
    def makeRow(audio_file):
        path = Path(audio_file.path)

        def track_num(tag):
            n, t = tag.track_num
            return f"{n or ''}{'/' if t else ''}{t or ''}"

        dirty = audio_file.is_dirty

        tag = audio_file.selected_tag or audio_file.tag
        return [
            path.stem,
            track_num(tag) if tag else None,
            tag.title if tag else None,
            tag.artist if tag else None,
            tag.album if tag else None,
            Pango.Weight.BOOK if not dirty else Pango.Weight.BOLD
        ]

    def updateRow(self, audio_file):
        row = self.getRow(audio_file)
        for i, r in enumerate(self.makeRow(audio_file)):
            row[i] = r

    def append(self, audio_file):
        path = Path(audio_file.path)
        if path in self._audio_files:
            raise ValueError(f"Duplicate AudioFile error: {path}")

        self._audio_files[path] = audio_file
        self._list_store.append(self.makeRow(audio_file))

    def getRow(self, key):
        """`key` may be index, path, or AudioFile"""
        if len(self._list_store) == 0:
            return None

        if type(key) is int:
            return self._list_store[key]
        else:
            if isinstance(key, AudioFile):
                key = key.path
            return self._list_store[list(self._audio_files.keys()).index(Path(key))]

    def getAudioFile(self, key):
        """`key` may be index, path, or AudioFile"""
        if len(self._audio_files) == 0:
            return None

        if type(key) is int:
            return list(self._audio_files.values())[key]
        else:
            if isinstance(key, AudioFile):
                key = key.path
            return self._audio_files[Path(key)]

    def iterAudioFiles(self):
        for f in self._audio_files.values():
            yield f

    def iterRows(self):
        for r in self._list_store:
            yield r


class FileListControl(GObject.GObject):
    __gsignals__ = {
        "current-edit-changed": (GObject.SIGNAL_RUN_LAST, None, [])
    }

    def __init__(self, tree_view):
        super().__init__()

        for i, (title, type_) in AudioFileListStore.model_map.items():
            if title.startswith("_"):
                continue

            cell_renderer = Gtk.CellRendererText()
            column = Gtk.TreeViewColumn(title, cell_renderer, text=i)
            column.add_attribute(cell_renderer, 'weight', AudioFileListStore.TEXT_WEIGHT)
            tree_view.append_column(column)

        select = tree_view.get_selection()
        select.connect("changed", self._onSelectionChanged)
        self.tree_view = tree_view

        self.list_store = AudioFileListStore()
        self._current = dict(index=None, audio_file=None)
        self.total_size_bytes = 0
        self.total_time_secs = 0

    @property
    def current_audio_file(self):
        return self._current["audio_file"]

    @property
    def current_index(self):
        return self._current["index"]

    @property
    def is_dirty(self):
        for _ in self.dirty_files:
            return True
        return False

    @property
    def dirty_files(self):
        curr_files = self.list_store._audio_files.values() \
                        if self.list_store._audio_files is not None else []
        return [af for af in curr_files if af.is_dirty]

    def setFiles(self, audio_files: list):
        self.total_size_bytes, self.total_time_secs = 0, 0

        self.list_store.clear()
        self.tree_view.set_model(self.list_store.store)

        for audio_file in audio_files:
            self.list_store.append(audio_file)
            self.total_size_bytes += audio_file.info.size_bytes
            self.total_time_secs += audio_file.info.time_secs

        # Size widget according to # audio_files
        n, w, h = len(audio_files), -1, 50

        h += 30 * (n - 2)
        self.tree_view.get_parent().set_size_request(w, min(h, 300))

        # Select first row
        self.tree_view.set_cursor(0)

    def _onSelectionChanged(self, selection):
        self._current["index"] = None
        self._current["audio_file"] = None

        model, tree_iter = selection.get_selected()
        if tree_iter is not None:
            self._current["index"] = selection.get_selected_rows()[1][0][0]
            self._current["audio_file"] = self.list_store.getAudioFile(self._current["index"])

        log.debug(f"File selection: {self._current}")
        self.emit("current-edit-changed")
