import logging

from pathlib import Path
from gi.repository import Gtk

from eyed3.utils import formatTime, formatSize

from .config import getState
from .utils import eyed3_load, eyed3_load_dir
from .dialogs import Dialog, FileSaveDialog
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
        app_state.main_window_position = self._main_window.window.get_position()
        app_state.save()


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

        # Restore last window size and position
        app_state = getState()
        if None not in app_state.main_window_position:
            self.window.move(*app_state.main_window_position)
        if None not in app_state.main_window_size:
            self.window.resize(*app_state.main_window_size)

        if self._file_list_control.current_audio_file:
            # Not using show_all here since some widgets may have hidden
            self._window.show()
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
        files = list(self._file_list_control.dirty_files)
        if not files:
            log.debug("Files not dirty, nothing to save")
            return

        resp, opts = FileSaveDialog().run()
        if resp == Gtk.ResponseType.OK:
            for audio_file in files:
                self._saveTag(audio_file, opts["version"])

    # TODO: right click menu save file
    def _onFileSave(self, _):
        current = self._file_list_control.current_audio_file
        if not current.tag.is_dirty:
            log.debug("File not dirty")
            return

        resp, opts = FileSaveDialog().run()
        if resp == Gtk.ResponseType.OK:
            self._saveTag(current, opts["version"])

    def _saveTag(self, audio_file, id3_version):
        assert audio_file.tag.is_dirty
        log.debug(f"Saving tag {audio_file.path}, {id3_version=}")
        audio_file.tag.save(version=id3_version)

        audio_file.tag.is_dirty = False
        self._file_list_control.list_store.updateRow(audio_file)

    def _onDirectoryOpen(self, _):
        # FIXME: wip select files or dirs
        '''
        builder = Gtk.Builder()
        builder.add_from_file(str(Path(__file__).parent / "dialogs.ui"))
        dialog = builder.get_object("file_open_dialog")
        '''
        dialog = Gtk.FileChooserDialog(
            "Please select files or directories to load", self._window,
            Gtk.FileChooserAction.OPEN | Gtk.FileChooserAction.SELECT_FOLDER,
            (Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
             Gtk.STOCK_OPEN, Gtk.ResponseType.OK)
        )
        dialog.set_select_multiple(True)

        '''
        ffilter = Gtk.FileFilter()
        ffilter.set_name("Audio Files")
        ffilter.add_pattern("*.mp3")
        dialog.add_filter(ffilter)
        '''

        audio_files = []
        try:
            response = dialog.run()
            if response == Gtk.ResponseType.OK:
                for d in dialog.get_filenames():
                    path = Path(d)
                    print("PATH:", path)
                    if path.is_dir():
                        dir_files = eyed3_load_dir(d)
                        audio_files += dir_files
                    else:
                        if audio_file := eyed3_load(path):
                            audio_files.append(audio_file)
        finally:
            dialog.destroy()

        if audio_files:
            self._file_list_control.setFiles(audio_files)

    def shutdown(self):
        if self._file_list_control.is_dirty:
            resp = Dialog("quit_confirm_dialog").run()

            if resp in (Gtk.ResponseType.OK, Gtk.ResponseType.CLOSE):
                if resp == Gtk.ResponseType.OK:
                    self._onFileSave(None)
            elif resp == Gtk.ResponseType.CANCEL:
                # Cancel the shutdown
                return False
            else:
                raise ValueError(f"Quit confirm response: {resp}")

        return True

    @staticmethod
    def _onHelpAbout(_):
        about_dialog = Gtk.AboutDialog()
        # FIXME: get this data from elsewhere
        about_dialog.set_program_name("Mop")
        about_dialog.set_version("0.1")
        about_dialog.set_website("https://github.com/nicfit/mop")
        about_dialog.set_authors(["Travis Shirk <travis@pobox.com>"])
        about_dialog.set_license_type(Gtk.License. GPL_3_0_ONLY)

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
        self._file_path_label.set_markup(f"<b>Path:</b> {audio_file.path}")
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
        text = f"<b>MPEG</b> {info.mp3_header.version}, Layer {'I' * info.mp3_header.layer}" \
                if info else ""
        self._file_mpeg_info_labels["mpeg_info_label"].set_markup(text)

        text = f"<b>Mode:</b> {info.mp3_header.mode}" if info else ""
        self._file_mpeg_info_labels["mpeg_mode_label"].set_markup(text)

        text = f"<b>Bitrate:</b> {info.bit_rate_str}" if info else ""
        self._file_mpeg_info_labels["mpeg_bitrate_label"].set_markup(text)

        text = f"<b>Sample rate:</b> {info.mp3_header.sample_freq} Hz" if info else ""
        self._file_mpeg_info_labels["mpeg_sample_rate_label"].set_markup(text)

        # Tag info editor
        self._editor_control.edit(list_control.current_audio_file)
