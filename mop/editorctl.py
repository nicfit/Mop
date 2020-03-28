import logging
from functools import partial
from contextlib import contextmanager
from eyed3 import id3, core
from eyed3.id3 import ID3_V1_0, ID3_V1_1, ID3_V2_3, ID3_V2_4, Genre
from gi.repository import GObject, Gtk, Gdk

from .core import GENRES

log = logging.getLogger(__name__)
ENTRY_ICON_PRIMARY = Gtk.EntryIconPosition.PRIMARY
ENTRY_ICON_SECONDARY = Gtk.EntryIconPosition.SECONDARY


class EditorWidget(GObject.GObject):
    __gsignals__ = {
        "tag-changed": (GObject.SIGNAL_RUN_LAST, None, []),
        # tag-value-copy(EditorWidget, new_value) -> None
        "tag-value-copy": (GObject.SIGNAL_RUN_LAST, None, (str,)),
        # tag-value-incr(EditorWidget) -> None
        "tag-value-incr": (GObject.SIGNAL_RUN_LAST, None, []),
    }

    def __init__(self, name, widget, editor_ctl):
        super().__init__()

        self._name = name
        self._editor_ctl = editor_ctl
        self._on_change_active = True

        self.widget = widget
        self._connect()

    def init(self, tag):
        raise NotImplementedError()

    def get(self):
        raise NotImplementedError()

    def set(self, tag, value) -> bool:
        getter, setter = self._getAccessors(tag)
        # Normalize "" to None
        if (value or None) != (getter() or None):
            log.debug(f"Set tag value: {value}")
            setter(value)
            return True
        return False

    def _connect(self):
        self.widget.connect("changed", self._onChanged)
        self.widget.connect("icon-release", self._onDeepCopy)

    def _extractPropertyName(self):
        prop = ""
        cap_next = False
        for c in self._name[len("tag_"):-len("_entry")]:
            if c == "_":
                cap_next = True
            else:
                if cap_next:
                    cap_next = False
                    c = c.upper()
                prop += c
        prop = prop[0].upper() + prop[1:]
        return prop

    def _getAccessors(self, tag, prop=None):
        prop = prop or self._extractPropertyName()

        getter_name = f"_get{prop}"
        setter_name = f"_set{prop}"
        if hasattr(tag, getter_name) and hasattr(tag, setter_name):
            return getattr(tag, getter_name), getattr(tag, setter_name)
        else:
            raise ValueError(f"Unsupported property name: {prop}")

    def _onChanged(self, widget):
        if self._on_change_active and self._editor_ctl.current_edit:
            tag = self._editor_ctl.current_edit.tag
            if self.set(tag, widget.get_text()):
                tag.is_dirty = True
                self.emit("tag-changed")

    def _onDeepCopy(self, entry, icon_pos, button):
        raise NotImplementedError()

    @contextmanager
    def _onChangeInactive(self):
        """Context manager for deactiving on-change events."""
        self._on_change_active = False
        try:
            yield None
        finally:
            self._on_change_active = True


class EntryEditorWidget(EditorWidget):
    def init(self, tag):
        with self._onChangeInactive():
            if tag:
                getter, _ = self._getAccessors(tag)
                curr_val = getter()
                self.widget.set_text(str(curr_val or ""))
            else:
                self.widget.set_text("")

    def get(self):
        return self.widget.get_text()

    def _onDeepCopy(self, entry, icon_pos, button):
        if icon_pos == ENTRY_ICON_SECONDARY:
            self.emit("tag-value-copy", self.get())


class SimpleAccessorEditorWidgetABC(EntryEditorWidget):

    def init(self, tag):
        with self._onChangeInactive():
            if tag:
                getter, _ = self._getAccessors(tag)
                text_frame = getter()
                self.widget.set_text(text_frame.text if text_frame else "")
            else:
                self.widget.set_text("")


class SimpleCommentEditorWidget(SimpleAccessorEditorWidgetABC):
    def _getAccessors(self, tag, prop=None):
        descr = ""
        lang = id3.DEFAULT_LANG

        def setter(val):
            tag.comments.set(val, descr, lang=lang)

        return partial(tag.comments.get, descr, lang=lang), setter


class SimpleUrlEditorWidget(SimpleAccessorEditorWidgetABC):
    def _getAccessors(self, tag, prop=None):
        descr = ""

        def setter(val):
            tag.user_url_frames.set(val, descr)

        return partial(tag.user_url_frames.get, descr), setter

    def init(self, tag):
        with self._onChangeInactive():
            if tag:
                getter, _ = self._getAccessors(tag)
                url_frame = getter()
                self.widget.set_text(url_frame.url if url_frame else "")
            else:
                self.widget.set_text("")


class NumTotalEditorWidget(EntryEditorWidget):

    def __init__(self, name, num_widget, editor_ctl, is_total=False):
        self._is_total = is_total
        super().__init__(name, num_widget, editor_ctl)

    def _connect(self):
        self.widget.connect("changed", self._onChanged)
        self.widget.connect("icon-release", self._onDeepCopy)

    def _getAccessors(self, tag, prop=None):
        prop = self._extractPropertyName()
        if self._is_total:
            prop = prop.replace("Total", "Num")
        return super()._getAccessors(tag, prop=prop)

    def set(self, tag, value) -> bool:
        getter, setter = self._getAccessors(tag)
        curr = getter()
        value = int(value) if value else None
        new_value = (curr[0], value) if self._is_total else (value, curr[1])
        if new_value != curr:
            setter(new_value)
            return True

    def _onDeepCopy(self, entry, icon_pos, button):
        if icon_pos == ENTRY_ICON_PRIMARY:
            self.emit("tag-value-incr")
        elif icon_pos == ENTRY_ICON_SECONDARY:
            super()._onDeepCopy(entry, icon_pos, button)

    def init(self, tag):
        with self._onChangeInactive():
            if not tag:
                self.widget.set_text("")
                return

            getter, _ = self._getAccessors(tag)
            curr_val = getter()[0 if not self._is_total else 1]
            self.widget.set_text(str(curr_val) if curr_val is not None else "")


class DateEditorWidget(EntryEditorWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._default_fg = self.widget.get_style().fg

    def set(self, tag, value) -> bool:
        getter, setter = self._getAccessors(tag)
        try:
            date = core.Date.parse(value) if value else None
        except ValueError:
            self.widget.modify_fg(Gtk.StateFlags.NORMAL, Gdk.color_parse("red"))
        else:
            if getter() != date:
                setter(date)
                self.widget.modify_fg(Gtk.StateFlags.NORMAL, Gdk.color_parse("black"))
                return True


class ComboBoxEditorWidget(EditorWidget):

    def get(self):
        return self.widget.get_active_text()

    def _connect(self):
        self.widget.connect("changed", self._onChanged)
        self._deep_copy_widget.connect("clicked", self._onDeepCopy)

    def _onDeepCopy(self, widget):
        self.emit("tag-value-copy", self.get())


class AlbumTypeEditorWidget(ComboBoxEditorWidget):
    def __init__(self, name, widget, deep_copy_widget, editor_ctl):
        self._deep_copy_widget = deep_copy_widget
        super().__init__(name, widget, editor_ctl)

        with self._onChangeInactive():
            self.widget.remove_all()
            for t in [""] + core.ALBUM_TYPE_IDS:
                self.widget.append(t, t.upper())

    def init(self, tag):
        with self._onChangeInactive():
            for i, titer in enumerate(self.widget.get_model()):
                if (titer[0].lower() or None) == (tag.album_type or None):
                    self.widget.set_active(i)
                    break

    def set(self, tag, value) -> bool:
        value = value.lower()
        if (tag.album_type or None) != (value or None):
            tag.album_type = value
            return True

    def _onChanged(self, widget):
        if self._editor_ctl.current_edit:
            tag = self._editor_ctl.current_edit.tag
            album_type = self.widget.get_active_text()
            if self.set(tag, album_type):
                tag.is_dirty = True
                self.emit("tag-changed")


class GenreEditorWidget(ComboBoxEditorWidget):
    def __init__(self, name, widget, deep_copy_widget, editor_ctl):
        self._on_change_active = False
        self._deep_copy_widget = deep_copy_widget
        super().__init__(name, widget, editor_ctl)

        self.widget.set_wrap_width(5)
        self.widget.set_entry_text_column(0)

        self.widget.remove_all()
        self.widget.append("-1", "")
        for genre in sorted(GENRES.iter()):
            self.widget.append(str(genre.id), genre.name)
        self.widget.set_active(0)
        self._on_change_active = True

    def init(self, tag):
        with self._onChangeInactive():
            if tag.genre is None:
                # No genre
                self.widget.set_active_id("-1")
            elif tag.genre.id is not None:
                # Standard genre
                self.widget.set_active_id(str(tag.genre.id))
            else:
                # Custom (non-std) genre
                try:
                    gid = str(GENRES.get(tag.genre.name).id)
                except KeyError:
                    genre = GENRES.add(tag.genre.name)
                    gid = str(genre.id)
                    self.widget.append(gid, genre.name)

                self.widget.set_active_id(gid)

    def set(self, tag, genre: Genre) -> bool:
        if (tag.genre or None) != (genre or None):
            tag.genre = genre
            return True

    def _onChanged(self, widget):
        if self._on_change_active and self._editor_ctl.current_edit:
            gid = self.widget.get_active_id()
            if gid is not None:
                try:
                    genre = GENRES.get(int(gid))
                except KeyError:
                    assert gid == "-1" or int(gid) > GENRES.GENRE_ID3V1_MAX
                    genre = None
            else:
                genre_text = self.widget.get_active_text()
                genre = Genre(genre_text, genre_map=GENRES) if genre_text else None

            tag = self._editor_ctl.current_edit.tag
            if self.set(tag, genre):
                tag.is_dirty = True
                self.emit("tag-changed")


class TagVersionEditorWidget(EditorWidget):

    def __init__(self, *args):
        super().__init__(*args)

        self.id3_versions = {
            ".".join([str(x) for x in v]): (v, f"ID3 {id3.versionToString(v)}")
            for v in (ID3_V2_4, ID3_V2_3, ID3_V1_1, ID3_V1_0)
        }

    def init(self, tag):
        with self._onChangeInactive():
            self.widget.remove_all()

            for vid, (version, version_str) in self.id3_versions.items():
                self.widget.append(vid, f"ID3 {id3.versionToString(version)}")
                if tag.version == version:
                    self.widget.set_active_id(vid)

    def _connect(self):
        self.widget.connect("changed", self._onChanged)

    def set(self, tag, value) -> bool:
        version = tuple([int(s) for s in value.split(".")])
        assert id3.isValidVersion(version)
        if version != tag.version:
            tag.version = version
            return True

    def get(self):
        return self.widget.get_active_id()

    def _onChanged(self, widget):
        version_id = self.widget.get_active_id()
        if not version_id:
            return

        if self._editor_ctl.current_edit:
            tag = self._editor_ctl.current_edit.tag
            if self.set(tag, version_id):
                tag.is_dirty = True
                self.emit("tag-changed")

    def _onDeepCopy(self, entry, icon_pos, button):
        pass


class EditorControl(GObject.GObject):
    COMMON_PAGE = 0
    EXTRAS_PAGE = 1
    IMAGES_PAGE = 2

    __gsignals__ = {
        "tag-changed": (GObject.SIGNAL_RUN_LAST, None, []),
    }

    def __init__(self, file_list_ctl, builder):
        super().__init__()

        self._file_list_ctl = file_list_ctl
        self._current_audio_file = None

        notebook = builder.get_object("editor_notebook")
        # XXX: Disable WIP notebook tabs
        #notebook.get_nth_page(self.EXTRAS_PAGE).hide()
        notebook.get_nth_page(self.IMAGES_PAGE).hide()

        self._editor_widgets = {}
        for widget_name in (
                "tag_title_entry", "tag_artist_entry", "tag_album_entry", "tag_comment_entry",
                "tag_track_num_entry", "tag_track_total_entry",
                "tag_disc_num_entry", "tag_disc_total_entry",
                "tag_release_date_entry", "tag_recording_date_entry",
                "tag_original_release_date_entry",
                "tag_album_type_combo", "tag_version_combo", "tag_genre_combo",
                # Extras
                "tag_albumArtist_entry", "tag_origArtist_entry", "tag_composer_entry",
                "tag_encodedBy_entry", "tag_publisher_entry", "tag_copyright_entry",
                "tag_url_entry",
        ):
            internal_name = f"current_edit_{widget_name}"
            widget = builder.get_object(internal_name)
            if widget is None:
                raise ValueError(f"Glade object not found: {internal_name}")

            # Make editor widgets
            if widget_name == "tag_album_type_combo":
                editor_widget = AlbumTypeEditorWidget(
                    widget_name, widget,
                    builder.get_object("current_edit_tag_album_type_deepcopy"),
                    self
                )

            elif widget_name == "tag_genre_combo":
                editor_widget = GenreEditorWidget(
                    widget_name, widget,
                    builder.get_object("current_edit_tag_genre_deepcopy"),
                    self
                )

            elif widget_name == "tag_version_combo":
                editor_widget = TagVersionEditorWidget(
                    widget_name, widget,
                    #builder.get_object("current_edit_tag_album_type_deepcopy"),
                    self
                )

            elif widget_name in ("tag_track_num_entry", "tag_track_total_entry",
                                 "tag_disc_num_entry", "tag_disc_total_entry"):
                editor_widget = NumTotalEditorWidget(widget_name, widget, self,
                                                     is_total="total" in widget_name)
            elif widget_name.endswith("_date_entry"):
                editor_widget = DateEditorWidget(widget_name, widget, self)
            elif widget_name.endswith("tag_comment_entry"):
                editor_widget = SimpleCommentEditorWidget(widget_name, widget, self)
            elif widget_name.endswith("tag_url_entry"):
                editor_widget = SimpleUrlEditorWidget(widget_name, widget, self)
            else:
                editor_widget = EntryEditorWidget(widget_name, widget, self)

            if editor_widget is not None:
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
            if editor_widget.set(audio_file.tag, copy_value):
                audio_file.tag.is_dirty = True
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
                if editor_widget.set(audio_file.tag, str(i)):
                    audio_file.tag.is_dirty = True
                    self._file_list_ctl.list_store.updateRow(audio_file)
                i += 1
        elif editor_widget == track_total_entry:
            # Track total -> len(audio_files) ...
            all_files = list(self._file_list_ctl.list_store.iterAudioFiles())
            file_count = len(all_files)
            for audio_file in self._file_list_ctl.list_store.iterAudioFiles():
                if editor_widget.set(audio_file.tag, str(file_count)):
                    audio_file.tag.is_dirty = True
                    self._file_list_ctl.list_store.updateRow(audio_file)

        # Update current edit
        self.edit(self.current_edit)

    def edit(self, audio_file):
        self._current_audio_file = audio_file

        tag = audio_file.tag if audio_file else None

        for widget in self._editor_widgets.values():
            try:
                widget.init(tag)
            except Exception as ex:
                log.exception(ex)

    @property
    def current_edit(self):
        return self._current_audio_file
