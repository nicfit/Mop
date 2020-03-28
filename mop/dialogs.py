from eyed3.id3 import ID3_V1_0, ID3_V1_1, ID3_V2_3, ID3_V2_4
from pathlib import Path
from gi.repository import Gtk


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
    def __init__(self, active_version="Current"):
        super().__init__("file_save_dialog")
        self._builder.get_object(f"v{active_version}_radiobutton").set_active(True)

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
