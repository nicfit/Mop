import logging
from functools import partial
from eyed3 import core
from eyed3.id3 import (
    ID3_V1_0, ID3_V1_1, ID3_V2_2, ID3_V2_3, ID3_V2_4, versionToString, Genre
)

from eyed3.id3.tag import (
    ID3_V1_MAX_TEXTLEN, ID3_V1_COMMENT_DESC, DEFAULT_LANG
)
from gi.repository import Gtk, Gdk
from ..core import GENRES
from .abc import EditorWidget

log = logging.getLogger(__name__)

# Genre models. A static ID3 v1 and dynamic v2, for quick swapping
_id3_v1_genre_model = Gtk.ListStore(str, str)
_id3_v1_genre_model.append(["", "-1"])
_id3_v2_genre_model = Gtk.ListStore(str, str)
_id3_v2_genre_model.append(["", "-1"])
for genre in sorted(GENRES.iter()):
    _id3_v2_genre_model.append([genre.name, str(genre.id)])
    if genre.id is not None and genre.id <= GENRES.WINAMP_GENRE_MAX:
        _id3_v1_genre_model.append([genre.name, str(genre.id)])

ENTRY_ICON_PRIMARY = Gtk.EntryIconPosition.PRIMARY
ENTRY_ICON_SECONDARY = Gtk.EntryIconPosition.SECONDARY
MOUSE_BUTTON1_MASK = Gdk.ModifierType.BUTTON1_MASK


class EntryEditorWidget(EditorWidget):
    def init(self, audio_file):
        tag = audio_file.selected_tag

        with self._onChangeInactive():
            if tag.isV1():
                # ID3 v1 length limits
                self.widget.set_max_length(ID3_V1_MAX_TEXTLEN)
            else:
                self.widget.set_max_length(0)

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
            if button.state & MOUSE_BUTTON1_MASK:
                self.emit("tag-value-copy", self.get())


class SimpleAccessorEditorWidgetABC(EntryEditorWidget):
    def init(self, audio_file):
        tag = audio_file.selected_tag

        if tag.isV1():
            # ID3 v1 length limits
            limit = ID3_V1_MAX_TEXTLEN
            if tag.isV1():
                # v1.1 stores uses last two bytes of comment to store track
                limit -= 2
            self.widget.set_max_length(limit)
        else:
            self.widget.set_max_length(0)

        with self._onChangeInactive():
            if tag:
                getter, _ = self._getAccessors(tag)
                text_frame = getter()
                self.widget.set_text(text_frame.text if text_frame else "")
            else:
                self.widget.set_text("")


class SimpleCommentEditorWidget(SimpleAccessorEditorWidgetABC):
    def init(self, audio_file):
        tag = audio_file.selected_tag

        retval = super().init(audio_file)

        if tag.isV1():
            # ID3 v1 length limits
            limit = ID3_V1_MAX_TEXTLEN
            if tag.version[1] == 1:
                # v1.1 stores uses last two bytes of comment to store track
                limit -= 2
            self.widget.set_max_length(limit)
        else:
            self.widget.set_max_length(0)

        return retval

    def _getAccessors(self, tag, prop=None):
        desc = "" if tag.isV2() else ID3_V1_COMMENT_DESC
        lang = DEFAULT_LANG

        def setter(val):
            tag.comments.set(val, desc, lang=lang)

        return partial(tag.comments.get, desc, lang=lang), setter


class SimpleUrlEditorWidget(SimpleAccessorEditorWidgetABC):
    def _getAccessors(self, tag, prop=None):
        desc = ""

        def setter(val):
            tag.user_url_frames.set(val, desc)

        return partial(tag.user_url_frames.get, desc), setter

    def init(self, audio_file):
        tag = audio_file.selected_tag

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

    def set(self, audio_file, value) -> bool:
        changed = False

        for tag in (t for t in (audio_file.tag, audio_file.second_v1_tag) if t):
            getter, setter = self._getAccessors(tag)
            curr = getter()
            value = int(value) if value else None
            new_value = (curr[0], value) if self._is_total else (value, curr[1])
            if new_value != curr:
                setter(new_value)
                changed = True

        return changed

    def _onDeepCopy(self, entry, icon_pos, button):
        if button.state & MOUSE_BUTTON1_MASK:
            if icon_pos == ENTRY_ICON_PRIMARY:
                self.emit("tag-value-incr")
            elif icon_pos == ENTRY_ICON_SECONDARY:
                super()._onDeepCopy(entry, icon_pos, button)

    def init(self, audio_file):
        tag = audio_file.selected_tag

        major, minor = tag.version[:2]
        if self._name.startswith("tag_track_") and major == 1:
            if self._name.startswith("tag_track_num"):
                self._setSensitive(
                    minor != 0,
                    self._default_tooltip if minor != 0 else "Track number requires ID3 v1.1"
                )
            else:
                self._setSensitive(False, "Track total requires ID3 v2.x")
        elif self._name.startswith("tag_disc_") and tag.isV1():
            # No disc number support for ID3 v1
            self._setSensitive(False, "Disc number requires ID3 v2.x")
        else:
            self._setSensitive(True, self._default_tooltip)

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

    def init(self, audio_file):
        tag = audio_file.selected_tag

        retval = super().init(audio_file)

        if tag.version < ID3_V2_4 and self._name == "tag_original_release_date_entry":
            # Original release date is only supported in ID3 2.4
            self._setSensitive(False, "Original release date requires ID3 v2.4")
        elif tag.isV1() and self._name == "tag_recording_date_entry":
            # Recording date is only supported in ID3 2
            self._setSensitive(False, "Recording date requires ID3 v2.x")
        else:
            # ID3 v1 is only a year
            self.widget.set_max_length(4 if tag.isV1() else 0)
            self._setSensitive(True, self._default_tooltip)

        return retval

    def set(self, audio_file, value) -> bool:
        changed = False

        for tag in (t for t in (audio_file.tag, audio_file.second_v1_tag) if t):
            getter, setter = self._getAccessors(tag)
            try:
                date = core.Date.parse(value) if value else None
            except ValueError:
                self.widget.modify_fg(Gtk.StateFlags.NORMAL, Gdk.color_parse("red"))
            else:
                if getter() != date:
                    setter(date)
                    self.widget.modify_fg(Gtk.StateFlags.NORMAL, Gdk.color_parse("black"))
                    changed = True

        return changed


class ComboBoxEditorWidget(EditorWidget):

    def get(self):
        return self.widget.get_active_text()

    def _connect(self):
        self.widget.connect("changed", self._onChanged)
        self._deep_copy_widget.connect("clicked", self._onDeepCopy)

    def _onDeepCopy(self, widget):
        # This is a real button, not icon so no need to check mouse button
        self.emit("tag-value-copy", self.get())


class AlbumTypeEditorWidget(ComboBoxEditorWidget):
    def __init__(self, name, widget, deep_copy_widget, editor_ctl):
        self._deep_copy_widget = deep_copy_widget
        super().__init__(name, widget, editor_ctl)

        with self._onChangeInactive():
            self.widget.remove_all()
            for t in [""] + core.ALBUM_TYPE_IDS:
                self.widget.append(t, t.upper())

    def init(self, audio_file):
        tag = audio_file.selected_tag

        with self._onChangeInactive():
            for i, titer in enumerate(self.widget.get_model()):
                if (titer[0].lower() or None) == (tag.album_type or None):
                    self.widget.set_active(i)
                    break

        # User text frames are ID3 v2 only
        if tag.isV1():
            self._setSensitive(False, "Album type requires ID3 v2.x")
        else:
            self._setSensitive(True, self._default_tooltip)

    def set(self, audio_file, value) -> bool:
        changed = False
        for tag in (t for t in (audio_file.tag, audio_file.second_v1_tag) if t):
            value = value.lower()
            if (tag.album_type or None) != (value or None):
                tag.album_type = value
                changed = True
        return changed

    def _onChanged(self, widget):
        if self._on_change_active and self._editor_ctl.current_edit:
            album_type = self.widget.get_active_text()
            if self.set(self._editor_ctl.current_edit, album_type):
                log.debug("Setting tag_dirty5")
                self._editor_ctl.current_edit.is_dirty = True
                self.emit("tag-changed")


class GenreEditorWidget(ComboBoxEditorWidget):
    def __init__(self, name, widget, deep_copy_widget, editor_ctl):
        with self._onChangeInactive():
            self._deep_copy_widget = deep_copy_widget
            super().__init__(name, widget, editor_ctl)

            self.widget.set_wrap_width(5)
            self.widget.set_entry_text_column(0)

    def init(self, audio_file):
        tag = audio_file.selected_tag

        # ID3 v1 cannot edit/edit genres, v2 can
        entry = self.widget.get_child()
        entry.set_can_focus(True if tag.isV2() else False)
        entry.set_editable(True if tag.isV2() else False)

        with self._onChangeInactive():
            if tag.isV1():
                self.widget.set_model(_id3_v1_genre_model)
            else:
                self.widget.set_model(_id3_v2_genre_model)

            if tag.genre is None:
                # No genre
                self.widget.set_active_id("-1")
            elif tag.genre.id is not None:
                # Standard genre
                self.widget.set_active_id(str(tag.genre.id))
            else:
                if tag.isV2():
                    # Custom (non-std) genre
                    try:
                        gid = str(GENRES.get(tag.genre.name).id)
                    except KeyError:
                        genre = GENRES.add(tag.genre.name)
                        gid = str(genre.id)
                        self.widget.append(gid, genre.name)

                    self.widget.set_active_id(gid)
                else:
                    # No custom for v1.x
                    self.widget.set_active_id("-1")

    def set(self, audio_file, genre: Genre) -> bool:
        changed = False
        for tag in (t for t in (audio_file.tag, audio_file.second_v1_tag) if t):
            if (tag.genre or None) != (genre or None):
                tag.genre = genre
                changed = True
        return changed

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

            if self.set(self._editor_ctl.current_edit, genre):
                log.debug("Setting tag_dirty6")
                self._editor_ctl.current_edit.is_dirty = True
                self.emit("tag-changed")


class TagVersionChoiceWidget(EditorWidget):
    def __init__(self, *args):
        super().__init__(*args)

        self.id3_versions = {
            ".".join([str(x) for x in v]): (v, f"ID3 {versionToString(v)}")
            for v in (ID3_V2_4, ID3_V2_3, ID3_V2_2, ID3_V1_1, ID3_V1_0)
        }

    def init(self, audio_file):
        all_tags = {audio_file.tag, audio_file.second_v1_tag}
        all_tags.remove(audio_file.selected_tag)
        assert len(all_tags) == 1
        selected = audio_file.selected_tag
        other = all_tags.pop()

        with self._onChangeInactive():
            self.widget.remove_all()

            for vid, (version, version_str) in self.id3_versions.items():
                if selected.version == version or (other and other.version == version):
                    self.widget.append(vid, f"ID3 {versionToString(version)}")
                    if selected.version == version:
                        self.widget.set_active_id(vid)

            self.widget.set_sensitive(True if other else False)

    def _connect(self):
        self.widget.connect("changed", self._onChanged)

    def set(self, audio_file, value) -> bool:
        return False

    def get(self):
        return self.widget.get_active_id()

    def _onChanged(self, widget):
        if not self._on_change_active:
            return

        version_id = self.widget.get_active_id()
        log.debug(f"Current tag version changed: {version_id}")
        if not version_id:
            return
        curr_edit = self._editor_ctl.current_edit

        if curr_edit:
            curr_tag = curr_edit.tag if not version_id.startswith("1.") else curr_edit.second_v1_tag
            # Forcing edit of curr_tag with tag= argument. Otherwise the prefer checkbutton decides.
            self._editor_ctl.edit(self._editor_ctl.current_edit, tag=curr_tag)

    def _onDeepCopy(self, entry, icon_pos, button):
        raise NotImplementedError()


