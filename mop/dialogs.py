from logging import getLogger
from sys import version_info as python_version_info
from collections import Counter, namedtuple
from typing import Optional
from eyed3 import version as eyeD3_version
from gi import version_info as gtk_version_info
from eyed3.id3 import (
    ID3_V1_0, ID3_V1_1, ID3_V2_3, ID3_V2_4, versionToString,
    LATIN1_ENCODING, UTF_8_ENCODING, UTF_16_ENCODING, UTF_16BE_ENCODING,
)
from pathlib import Path
from gi.repository import Gtk
from .config import getConfig

log = getLogger(__name__)


class Dialog:
    def __init__(self, dialog_name):
        builder = Gtk.Builder()
        builder.add_from_file(str(Path(__file__).parent / "dialogs.ui"))
        self._dialog = builder.get_object(dialog_name)
        if self._dialog is None:
            raise ValueError(f"Dialog not found: {dialog_name}")
        self._builder = builder

    def run(self, destroy=True):
        try:
            resp = self._dialog.run()
            return resp
        finally:
            if destroy:
                self._dialog.destroy()


class FileSaveDialog(Dialog):
    _id3_v23_encodings_model = Gtk.ListStore(str, int)
    _id3_v23_encodings_model.append(["utf16", ord(UTF_16_ENCODING)])
    _id3_v23_encodings_model.append(["utf16be", ord(UTF_16BE_ENCODING)])
    _id3_v23_encodings_model.append(["latin", ord(LATIN1_ENCODING)])
    _id3_v24_encodings_model = Gtk.ListStore(str, int)
    _id3_v24_encodings_model.append(["utf8", ord(UTF_8_ENCODING)])
    for row in _id3_v23_encodings_model:
        _id3_v24_encodings_model.append(row[:])

    SaveOptions = namedtuple("SaveOptions", ["id3_v1_version", "id3_v2_version", "id3_v2_encoding"])

    def __init__(self, audio_files):
        super().__init__("file_save_dialog")

        pref_v1_version = getConfig().preferred_id3_v1_version or ID3_V1_1
        pref_v2_version = getConfig().preferred_id3_v2_version or ID3_V2_4

        self._save_v2_checkbutton = self._builder.get_object("save_id3v2_checkbutton")
        self._save_v1_checkbutton = self._builder.get_object("save_id3v1_checkbutton")

        def toggleVersionFrame(checkbutton):
            checkbutton.get_parent().get_child().set_sensitive(checkbutton.get_active())
        self._save_v2_checkbutton.connect("toggled", toggleVersionFrame)
        self._save_v1_checkbutton.connect("toggled", toggleVersionFrame)

        # Counters of ID3 versions, encodings, etc.
        v1_versions, v2_versions = Counter(), Counter()
        v2_encodings = Counter()
        for f in audio_files:
            if f.tag:
                # Version
                if f.tag.isV2():
                    v2_versions[f.tag.version] += 1
                    if f.second_v1_tag:
                        v1_versions[f.second_v1_tag.version] += 1
                else:
                    assert f.tag.isV1()
                    v1_versions[f.tag.version] += 1

                # Encodings
                if f.tag.isV2():
                    for text_frame in [f.tag.frame_set[fid][0] for fid in f.tag.frame_set
                                            if fid.startswith(b"T")]:
                        v2_encodings[text_frame.encoding] += 1

        default_v1_version = v1_versions.most_common()[0][0] \
                                if v1_versions.most_common() else pref_v1_version
        log.debug(f"Most common v1 versions: {default_v1_version}")
        default_v2_version = v2_versions.most_common()[0][0] \
                                if v2_versions.most_common() else pref_v2_version
        log.debug(f"Most common v2 versions: {default_v2_version}")
        default_v2_encoding = v2_encodings.most_common()[0][0] \
                                if v2_encodings.most_common() else None
        log.debug(f"Most common v2 encoding: {default_v2_encoding}")

        self._save_v2_checkbutton.set_active(len(v2_versions))
        toggleVersionFrame(self._save_v2_checkbutton)
        self._save_v1_checkbutton.set_active(len(v1_versions))
        toggleVersionFrame(self._save_v1_checkbutton)

        # Version combo boxes
        v2_combo = self._builder.get_object("save_id3v2_version_combobox")
        v1_combo = self._builder.get_object("save_id3v1_version_combobox")

        for combo, opts, default_version in [(v2_combo, [ID3_V2_4, ID3_V2_3], default_v2_version),
                                             (v1_combo, [ID3_V1_1, ID3_V1_0], default_v1_version)]:
            combo.remove_all()
            for v in opts:
                combo.append(str(v), versionToString(v))
            if default_version:
                combo.set_active_id(str(default_version))

        # Encoding combo boxes
        v2_enc_combo = self._builder.get_object("save_id3v2_encoding_combobox")

        def initEncodings(combobox, id3_version: Optional[tuple], active_encoding: Optional[bytes]):
            id3_version = id3_version or eval(combobox.get_active_id())
            assert type(id3_version) is tuple

            v2_enc_combo.set_model(self._id3_v24_encodings_model if id3_version[:2] >= (2, 4)
                                                                 else self._id3_v23_encodings_model)

            if active_encoding:
                for i, row in enumerate(v2_enc_combo.get_model()):
                    if row[1] == ord(active_encoding):
                        v2_enc_combo.set_active(i)
                        break
            else:
                # TODO: Use default encoding preference if most_common is empty; based if off
                # TODO: active version
                v2_enc_combo.set_active(0)

        initEncodings(v2_enc_combo, default_v2_version, default_v2_encoding)
        v2_combo.connect("changed",
                         lambda *args: initEncodings(v2_combo, None, None))

        self._v2_combo = v2_combo
        self._v1_combo = v1_combo
        self._v2_encoding_combo = v2_enc_combo

    def run(self, destroy=True):
        resp = super().run(destroy=False)
        if resp != Gtk.ResponseType.OK:
            self._dialog.destroy()
            return resp, None

        # Options
        id3_v1_version = None
        id3_v2_version = None
        id3_v2_encoding = None
        try:
            if self._save_v2_checkbutton.get_active():
                # a version tuple as a string, eval to get it back...
                id3_v2_version = eval(self._v2_combo.get_active_id())
                # convert encoding int ordinal back to byte
                active_enc = self._v2_encoding_combo.get_active_iter()
                enc_model = self._v2_encoding_combo.get_model()
                id3_v2_encoding = bytes(chr(enc_model.get_value(active_enc, 1)), "ascii")

            if self._save_v1_checkbutton.get_active():
                id3_v1_version = eval(self._v1_combo.get_active_id())

            return resp, self.SaveOptions(id3_v1_version=id3_v1_version,
                                          id3_v2_version=id3_v2_version,
                                          id3_v2_encoding=id3_v2_encoding)
        finally:
            if destroy:
                self._dialog.destroy()


class AboutDialog(Gtk.AboutDialog):
    def __init__(self, *args, **kwargs):
        from .__about__ import project_name, version, author, author_email, years, release_name

        super().__init__(*args, **kwargs)
        self.set_program_name(project_name)

        version_str = version
        if release_name:
            version_str += f" ({release_name})"
        self.set_version(version_str)

        # TODO: support multiple authors (AUTHORS.rst)
        self.set_authors([f"{author} <{author_email}>"])
        self.set_license_type(Gtk.License. GPL_3_0_ONLY)
        self.set_copyright(f"Copyright © {author}, {years}")

        def versionInfoToString(info):
            return ".".join([str(x) for x in info])

        self.set_comments(f"Running with Python {versionInfoToString(python_version_info[:3])}, "
                          f"GTK+ {versionInfoToString(gtk_version_info)}, "
                          "and "
                          f"eyeD3 {eyeD3_version}")
        # TODO: Get URL from __about__
        self.set_website_label("GitHub")
        self.set_website("https://github.com/nicfit/Mop")
        # TODO:
        '''
        self.set_logo()
        self.set_artists()
        self.set_documentors()
        self.set_translator_credits()
        '''


class FileChooserDialog(Dialog):
    def __init__(self, current_dir=None, action=Gtk.FileChooserAction.SELECT_FOLDER):
        super().__init__("file_chooser_dialog")
        action = action if action is not None else Gtk.FileChooserAction.SELECT_FOLDER

        if current_dir:
            self._dialog.set_current_folder(current_dir)
        self._dialog.set_select_multiple(True)

        for radiobutton in ("file_chooser_open_dirs_radiobutton",
                            "file_chooser_open_files_radiobutton"):
            radiobutton = self._builder.get_object(radiobutton)
            radiobutton.connect("toggled", self._onActionChange)
            if f"_{self.actionToSting(action)}_" in radiobutton.get_name():
                radiobutton.set_active(True)
                self._setAction(action)

        # FIXME: WIP
        '''
        audio_filter = Gtk.FileFilter()
        audio_filter.set_name("Audio Files")
        audio_filter.add_pattern("*.mp3")
        self._dialog.set_filter(audio_filter)
        '''

    def _setAction(self, action):
        if action == Gtk.FileChooserAction.SELECT_FOLDER:
            '''
            for flt in list(self._dialog.list_filters()):
                self._dialog.remove_filter(flt)
            '''
        else:
            '''
            audio_filter = Gtk.FileFilter()
            audio_filter.set_name("Audio Files")
            audio_filter.add_pattern("*.mp3")
            self._dialog.set_filter(audio_filter)
            '''

        self._dialog.set_action(action)

    def _onActionChange(self, radiobutton):
        if radiobutton.get_active():
            if "_dirs_" in radiobutton.get_name():
                self._setAction(Gtk.FileChooserAction.SELECT_FOLDER)
            else:
                self._setAction(Gtk.FileChooserAction.OPEN)

    def run(self):
        resp = super().run(destroy=False)
        try:
            if resp == Gtk.ResponseType.CANCEL:
                return None, None
            else:
                # XXX: tuple retval, blech
                return list(sorted(self._dialog.get_filenames())), self._dialog.get_action()
        finally:
            self._dialog.destroy()

    @staticmethod
    def actionToSting(action):
        return "dirs" if action == Gtk.FileChooserAction.SELECT_FOLDER else "files"

    @staticmethod
    def stringToAction(action_str):
        return Gtk.FileChooserAction.SELECT_FOLDER if action_str == "dirs" \
                                                   else Gtk.FileChooserAction.OPEN

    def connect(self, *args):
        self._dialog.connect(*args)


class NothingToDoDialog(Dialog):
    def __init__(self):
        super().__init__("nothing_to_do_dialog")
