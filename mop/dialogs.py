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

    def run(self):
        try:
            resp = self._dialog.run()
            return resp
        finally:
            self._dialog.destroy()


class FileSaveDialog(Dialog):
    def __init__(self):
        super().__init__("file_save_dialog")

        pref_version = getConfig().preferred_id3_version or ID3_ANY_VERSION
        if pref_version == ID3_ANY_VERSION:
            active_version = "vCurrent"
        else:
            active_version = versionToString(pref_version).replace(".", "")

        print("V:", pref_version, active_version)
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
