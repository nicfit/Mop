from sys import version_info as python_version_info
from eyed3 import version as eyeD3_version
from gi import version_info as gtk_version_info
from eyed3.id3 import ID3_V1_0, ID3_V1_1, ID3_V2_3, ID3_V2_4, ID3_ANY_VERSION, versionToString
from pathlib import Path
from gi.repository import Gtk
from .config import getConfig


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
    def __init__(self):
        super().__init__("file_save_dialog")

        pref_version = getConfig().preferred_id3_version or ID3_ANY_VERSION
        if pref_version == ID3_ANY_VERSION:
            active_version = "vCurrent"
        else:
            active_version = versionToString(pref_version).replace(".", "")

        self._builder.get_object(f"{active_version}_radiobutton").set_active(True)

    def run(self):
        resp = super().run()

        options = dict(version=None, save_all=False)
        for label, version in (("vCurrent", None),
                               ("v24", ID3_V2_4), ("v23", ID3_V2_3),
                               ("v11", ID3_V1_1), ("v10", ID3_V1_0)):
            if self._builder.get_object(f"{label}_radiobutton").get_active():
                options["version"] = version
                break

        return resp, options


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
        self.set_website("https://github.com/nicfit/mop")
        # TODO:
        #self.set_logo()
        #self.set_artists()
        #self.set_documentors()
        #self.set_translator_credits()


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
        #audio_filter = Gtk.FileFilter()
        #audio_filter.set_name("Audio Files")
        #audio_filter.add_pattern("*.mp3")
        #self._dialog.set_filter(audio_filter)

    def _setAction(self, action):
        print(list(self._dialog.list_filters()))
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
