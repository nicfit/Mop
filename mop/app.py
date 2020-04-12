import logging

from pathlib import Path
from gi.repository import Gtk

from eyed3.id3 import ID3_V2_2, ID3_V2_4
from eyed3.utils import formatTime, formatSize

from .config import getState, DEFAULT_STATE_FILE
from .utils import eyed3_load, eyed3_load_dir, escapeMarkup
from .dialogs import Dialog, FileSaveDialog, AboutDialog, FileChooserDialog, NothingToDoDialog
from .editorctl import EditorControl
from .filesctl import FileListControl

log = logging.getLogger(__name__)
logging.getLogger("eyed3").setLevel(logging.ERROR)


class MopApp:

    def __init__(self):
        builder = Gtk.Builder()
        builder.add_from_file(str(Path(__file__).parent / "mop.ui"))

        self._builder = builder
        self._main_window = None
        self._is_shut_down = False

    def run(self, args):
        self._main_window = MopWindow(self._builder, args)

        handlers = {
            "on_file_quit_menu_item_activate": self.quit,
        }
        handlers.update(self._main_window.handlers)

        self._builder.connect_signals(handlers)
        self._main_window.window.connect("delete-event", self.quit)

        try:
            self._main_window.show()
            Gtk.main()
        except KeyboardInterrupt:
            pass
        except FileNotFoundError as ex:
            log.error(ex)
            return 1
        except Exception as ex:
            log.exception("Error:", ex)
            return 2

    def quit(self, *_):
        if self._main_window.shutdown():
            self._updateState()
            self._is_shut_down = True
            Gtk.main_quit()
        else:
            # Not quitting
            log.warning("Quit request rejected")
            return True

    def _updateState(self):
        app_state = getState()
        app_state.main_window_size = self._main_window.window.get_size()
        app_state.main_window_pos = self._main_window.window.get_position()
        app_state.save(DEFAULT_STATE_FILE)


class MopWindow:
    def __init__(self, builder, args):
        self._args = args
        self._builder = builder
        self._window = builder.get_object("main_window")
        self._window.set_title("Mop")

        self._file_info_label = builder.get_object("current_file_info_label")
        self._file_path_label = builder.get_object("current_edit_filename_label")
        self._file_size_label = builder.get_object("current_edit_size_label")
        self._file_time_label = builder.get_object("current_edit_time_label")

        self._file_mpeg_info_labels = dict()
        for label in ("mpeg_info_label", "mpeg_mode_label",
                      "mpeg_bitrate_label", "mpeg_sample_rate_label"):
            self._file_mpeg_info_labels[label] = builder.get_object(f"current_edit_{label}")

        # AudioFile list control
        self._file_list_control = FileListControl(builder.get_object("audio_files_tree_view"))
        self._file_list_control.connect("current-edit-changed", self._onFileEditChange)

        # Tag editor control
        self._editor_control = EditorControl(self._file_list_control, builder)

    def show(self):
        # Restore last window size and position
        app_state = getState()
        if app_state.main_window_pos is not None:
            self.window.move(*app_state.main_window_pos)
        if app_state.main_window_size is not None:
            self.window.resize(*app_state.main_window_size)

        # Load files
        audio_files = []
        if not self._args.path_args:
            self._onDirectoryOpen(None)
        else:
            for path in self._args.path_args or []:
                if path.exists():
                    if path.is_dir():
                        audio_files += eyed3_load_dir(path)
                    else:
                        if af := eyed3_load(path):
                            audio_files.append(af)

            self._file_list_control.setFiles(audio_files)

        if self._file_list_control.current_audio_file:
            # Not using show_all here since some widgets may have hidden
            self._window.show()
        else:
            if NothingToDoDialog().run() == Gtk.ResponseType.OK:
                # Clear path args that failed to load
                self._args.path_args = None
                self.show()
            else:
                raise FileNotFoundError("Nothing to do")

    @property
    def window(self):
        return self._window

    @property
    def handlers(self):
        return {
            "on_file_open_menu_item_activate": self._onDirectoryOpen,
            "on_file_save_menu_item_activate": self._onFileSaveAll,
            "on_help_about_menu_item_activate": self._onHelpAbout,
        }

    def _onFileSaveAll(self, _):
        if not self._file_list_control.is_dirty:
            log.debug("Files not dirty, nothing to save")
            return

        files = list(self._file_list_control.dirty_files)

        resp, opts = FileSaveDialog().run()
        if resp == Gtk.ResponseType.OK:
            for audio_file in files:
                for tag in (audio_file.tag, audio_file.second_v1_tag):
                    if tag and tag.is_dirty:
                        self._saveTag(audio_file, tag, opts["version"])

        # Restored current edit based on file list selection.
        self._editor_control.edit(self._file_list_control.current_audio_file)

    def _saveTag(self, audio_file, tag, id3_version):
        assert tag is not None
        assert tag.is_dirty
        assert id3_version != ID3_V2_2
        main_tag = audio_file.tag

        if tag.version == ID3_V2_2 and id3_version is None:
            # Cannot save v2.2
            id3_version = ID3_V2_4

        try:
            log.debug(f"Saving tag {audio_file.path}, {id3_version=}")
            audio_file.tag = tag
            if id3_version and id3_version[0] == 1 and tag.isV1():
                audio_file.tag.save(version=id3_version)
            elif id3_version and id3_version[0] == 2 and tag.isV2():
                audio_file.tag.save(version=id3_version)
            else:
                audio_file.tag.save()

            audio_file.tag.is_dirty = False
        finally:
            audio_file.tag = main_tag

        self._editor_control.edit(audio_file)
        self._file_list_control.list_store.updateRow(audio_file)

    def _onDirectoryOpen(self, _):
        state = getState()
        dialog = FileChooserDialog(state.file_open_cwd,
                                   FileChooserDialog.stringToAction(state.file_open_action))

        def trackCurrentFolder(file_chooser):
            state.file_open_cwd = file_chooser.get_current_folder()
        dialog.connect("current-folder-changed", trackCurrentFolder)

        audio_files = []
        filenames, action = dialog.run()
        for f in filenames or []:
            path = Path(f)
            if path.is_dir():
                dir_files = eyed3_load_dir(f)
                audio_files += dir_files
            else:
                if audio_file := eyed3_load(path):
                    audio_files.append(audio_file)

        if audio_files:
            self._file_list_control.setFiles(audio_files)

        state.file_open_action = dialog.actionToSting(action)

    def shutdown(self):
        if self._file_list_control.is_dirty:
            resp = Dialog("quit_confirm_dialog").run()

            if resp in (Gtk.ResponseType.OK, Gtk.ResponseType.CLOSE):
                if resp == Gtk.ResponseType.OK:
                    self._onFileSaveAll(None)
            elif resp == Gtk.ResponseType.CANCEL:
                # Cancel the shutdown
                return False
            else:
                raise ValueError(f"Quit confirm response: {resp}")

        return True

    @staticmethod
    def _onHelpAbout(_):
        about_dialog = AboutDialog()
        about_dialog.run()
        about_dialog.destroy()

    def _onFileEditChange(self, list_control):
        num = len(list_control.list_store)

        # File n of N label
        if list_control.current_index is not None:
            self._file_info_label.set_markup(
                f"<b>File {list_control.current_index + 1}  of  {num}</b>"
            )
        else:
            self._file_info_label.set_markup("")
            return

        audio_file = list_control.current_audio_file
        if not audio_file:
            return

        # File info
        self._file_path_label.set_markup(escapeMarkup(f"<b>Path:</b> {audio_file.path}"))
        self._file_size_label.set_markup(
            f"<b>Size:</b>  {formatSize(audio_file.info.size_bytes)}"
            f"  [{formatSize(list_control.total_size_bytes)} total]"
        )
        self._file_time_label.set_markup(
            f"<b>Time:</b>  {formatTime(audio_file.info.time_secs)}"
            f"  [{formatTime(list_control.total_time_secs)} total]",
        )

        # Audio info (mpeg)
        info = audio_file.info
        text = f"<b>MPEG</b> {info.mp3_header.version}, "\
               f"Layer {'I' * info.mp3_header.layer}, " \
               f"{info.mp3_header.mode}"\
            if info else ""
        self._file_mpeg_info_labels["mpeg_info_label"].set_markup(text)

        text = f"<b>Bitrate:</b> {info.bit_rate_str}" if info else ""
        self._file_mpeg_info_labels["mpeg_bitrate_label"].set_markup(text)

        text = f"<b>Sample rate:</b> {info.mp3_header.sample_freq} Hz" if info else ""
        self._file_mpeg_info_labels["mpeg_sample_rate_label"].set_markup(text)

        # Tag info editor
        self._editor_control.edit(list_control.current_audio_file)
