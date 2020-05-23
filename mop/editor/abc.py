import logging
from contextlib import contextmanager
from gi.repository import GObject
from eyed3.id3 import ID3_ANY_VERSION, versionToString

log = logging.getLogger(__name__)


class EditorWidget(GObject.GObject):
    __gsignals__ = {
        "tag-changed": (GObject.SIGNAL_RUN_LAST, None, []),
        # tag-value-copy(EditorWidget, new_value) -> None
        "tag-value-copy": (GObject.SIGNAL_RUN_LAST, None, (str,)),
        # tag-value-incr(EditorWidget) -> None
        "tag-value-incr": (GObject.SIGNAL_RUN_LAST, None, []),
    }

    def __init__(self, name, builder, editor_ctl, min_id3_version):
        super().__init__()

        self._name = name
        self._builder = builder
        self._editor_ctl = editor_ctl
        self._on_change_active = True
        self._min_id3_version = min_id3_version or ID3_ANY_VERSION

        self.widget = builder.get_object(self._getInternalName(name))
        if self.widget is None:
            raise ValueError(f"Glade object not found: {self._getInternalName(name)}")

        self._connect()
        self._default_tooltip = self.widget.get_tooltip_text()

    @staticmethod
    def _getInternalName(name) -> str:
        return f"current_edit_{name}"

    def init(self, audio_file, disable_change_signal=False):
        if not disable_change_signal:
            self._init(audio_file)
        else:
            with self._onChangeInactive():
                self._init(audio_file)

    def _init(self, audio_file) -> None:
        raise NotImplementedError()

    def get(self):
        raise NotImplementedError()

    def _iterTags(self, audio_file):
        for tag in (audio_file.tag, audio_file.second_v1_tag):
            if tag and self._checkVersion(tag.version):
                yield tag

    def set(self, audio_file, value) -> bool:
        changed = False

        for tag in self._iterTags(audio_file):
            getter, setter = self._getAccessors(tag)
            # Normalize "" to None
            if (value or None) != (getter() or None):
                log.info(f"Set [{self._name}] value, tag v{tag.version}: '{getter()}' -> '{value}'")
                setter(value)
                changed = True
        return changed

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

            if self.set(self._editor_ctl.current_edit, widget.get_text()):
                log.debug("Setting tag_dirty4")
                self._editor_ctl.current_edit.is_dirty = True
                self.emit("tag-changed")

    def _onDeepCopy(self, entry, icon_pos, button):
        raise NotImplementedError()

    @contextmanager
    def _onChangeInactive(self):
        """Context manager for deactivating on-change events."""
        self._on_change_active = False
        try:
            yield None
        finally:
            self._on_change_active = True

    def _setSensitive(self, state, tooltip_text=None):
        self.widget.set_sensitive(state)

        if not tooltip_text and bool(state) is False:
            tooltip_text = f"Requires ID3 {versionToString(self._min_id3_version)}"
        self.widget.set_tooltip_text(tooltip_text)

    def _checkVersion(self, v) -> bool:
        # Normalize None to 0 in version tuples when comparing
        retval = (self._min_id3_version == ID3_ANY_VERSION) \
                 or (v[:2] >= tuple([(n if n else 0) for n in self._min_id3_version[:2]]))
        log.debug(f"_checkVersion::{self._name} {v=} {self._min_id3_version=} {retval=}")

        return retval
