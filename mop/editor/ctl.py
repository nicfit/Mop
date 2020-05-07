import logging
from gi.repository import GObject
from eyed3.id3 import ID3_ANY_VERSION, ID3_V1, ID3_V1_1, ID3_V2, ID3_V2_4
from .common import (
    EntryEditorWidget,
    NumTotalEditorWidget, DateEditorWidget,
    SimpleUrlEditorWidget, SimpleCommentEditorWidget,
    AlbumTypeEditorWidget, TagVersionChoiceWidget, GenreEditorWidget,
)

log = logging.getLogger(__name__)


class EditorControl(GObject.GObject):
    COMMON_PAGE = 0
    EXTRAS_PAGE = 1
    IMAGES_PAGE = 2

    __gsignals__ = {
        "tag-changed": (GObject.SIGNAL_RUN_LAST, None, []),
    }

    EDITOR_WIDGETS = {
        "tag_title_entry": (EntryEditorWidget, ID3_ANY_VERSION),
        "tag_artist_entry": (EntryEditorWidget, ID3_ANY_VERSION),
        "tag_album_entry": (EntryEditorWidget, ID3_ANY_VERSION),
        "tag_track_num_entry": (NumTotalEditorWidget, ID3_V1_1),
        "tag_track_total_entry": (NumTotalEditorWidget, ID3_V2),
        "tag_disc_num_entry": (NumTotalEditorWidget, ID3_V2),
        "tag_disc_total_entry": (NumTotalEditorWidget, ID3_V2),
        "tag_release_date_entry": (DateEditorWidget, ID3_V2_4),
        "tag_recording_date_entry": (DateEditorWidget, ID3_V2),
        "tag_original_release_date_entry": (DateEditorWidget, ID3_V1),
        "tag_album_type_combo": (AlbumTypeEditorWidget, ID3_V2),
        "tag_genre_combo": (GenreEditorWidget, ID3_ANY_VERSION),
        "tag_version_combo": (TagVersionChoiceWidget, ID3_ANY_VERSION),
        "tag_comment_entry": (SimpleCommentEditorWidget, ID3_ANY_VERSION),
        "tag_url_entry": (SimpleUrlEditorWidget, ID3_V2),
        # Extras
        "tag_albumArtist_entry": (EntryEditorWidget, ID3_V2),
        "tag_origArtist_entry": (EntryEditorWidget, ID3_V2),
        "tag_composer_entry": (EntryEditorWidget, ID3_V2),
        "tag_encodedBy_entry": (EntryEditorWidget, ID3_V2),
        "tag_publisher_entry": (EntryEditorWidget, ID3_V2),
        "tag_copyright_entry": (EntryEditorWidget, ID3_V2),
    }

    def __init__(self, file_list_ctl, builder):
        super().__init__()

        self._file_list_ctl = file_list_ctl
        self._current_audio_file = None

        self._notebook = builder.get_object("editor_notebook")
        # XXX: Disable WIP notebook tabs
        self._notebook.get_nth_page(self.IMAGES_PAGE).hide()

        self._edit_prefer_v1_checkbutton = builder.get_object("default_prefer_v1_checkbutton")
        self._edit_prefer_v1_checkbutton.connect(
            "toggled", lambda _: self.edit(self.current_edit, disable_change_signal=True)
        )

        self._editor_widgets = {}
        for widget_name, (WidgetClass, min_id3_version) in self.EDITOR_WIDGETS.items():
            editor_widget = WidgetClass(widget_name, builder, self, min_id3_version)
            editor_widget.connect("tag-changed", self._onTagChanged)
            editor_widget.connect("tag-value-copy", self._onTagValueCopy)
            editor_widget.connect("tag-value-incr", self._onTagValueIncrement)

            self._editor_widgets[widget_name] = editor_widget

    def _onTagChanged(self, *args):
        log.debug(f"_onTagChanged: {args}")
        self._file_list_ctl.list_store.updateRow(self._file_list_ctl.current_audio_file)
        self.emit("tag-changed")

    def _onTagValueCopy(self, editor_widget, copy_value):
        for audio_file in self._file_list_ctl.list_store.iterAudioFiles():
            if editor_widget.set(audio_file, copy_value):
                log.debug("Setting tag_dirty1")
                audio_file.is_dirty = True
                self._file_list_ctl.list_store.updateRow(audio_file)

        # Update current edit
        self.edit(self.current_edit)

    def _onTagValueIncrement(self, editor_widget):
        track_num_entry = self._editor_widgets["tag_track_num_entry"]
        track_total_entry = self._editor_widgets["tag_track_total_entry"]

        if editor_widget == track_num_entry:
            # Track number -> 1, 2, 3, ...
            i = 1
            for audio_file in self._file_list_ctl.list_store.iterAudioFiles():
                if editor_widget.set(audio_file, str(i)):
                    log.debug("Setting tag_dirty2")
                    audio_file.is_dirty = True
                    self._file_list_ctl.list_store.updateRow(audio_file)
                i += 1
        elif editor_widget == track_total_entry:
            # Track total -> len(audio_files) ...
            all_files = list(self._file_list_ctl.list_store.iterAudioFiles())
            file_count = len(all_files)
            for audio_file in self._file_list_ctl.list_store.iterAudioFiles():
                # No second_v1_tag supported needed for totals
                if editor_widget.set(audio_file, str(file_count)):
                    log.debug("Setting tag_dirty3")
                    audio_file.is_dirty = True
                    self._file_list_ctl.list_store.updateRow(audio_file)

        # Update current edit
        self.edit(self.current_edit)

    def edit(self, audio_file, tag=None, disable_change_signal=False):
        self._current_audio_file = audio_file
        tag1 = audio_file.tag if audio_file else None
        tag2 = audio_file.second_v1_tag if audio_file else None

        if not tag:
            # If two tags and a selection has not yet been made.
            if tag2 and self._edit_prefer_v1_checkbutton.get_active():
                audio_file.selected_tag = tag2
            else:
                audio_file.selected_tag = tag1
        else:
            audio_file.selected_tag = tag

        self._edit_prefer_v1_checkbutton.set_visible(bool(tag2))

        assert audio_file.selected_tag in (tag1, tag2)

        if audio_file.selected_tag and audio_file.selected_tag.isV1():
            # ID3 v1 supports no Extras
            self._notebook.get_nth_page(self.EXTRAS_PAGE).hide()
        else:
            self._notebook.get_nth_page(self.EXTRAS_PAGE).show()

        for widget_name, widget in self._editor_widgets.items():
            try:
                widget.init(audio_file, disable_change_signal=disable_change_signal)
            except Exception as ex:
                log.exception(ex)

        self.file_list_ctl.list_store.updateRow(audio_file)

    @property
    def current_edit(self):
        return self._current_audio_file

    @property
    def file_list_ctl(self):
        return self._file_list_ctl
