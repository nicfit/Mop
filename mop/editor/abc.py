import logging
from contextlib import contextmanager
from gi.repository import GObject

log = logging.getLogger(__name__)


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
        self._default_tooltip = self.widget.get_tooltip_text()

    def init(self, audio_file):
        raise NotImplementedError()

    def get(self):
        raise NotImplementedError()

    def set(self, audio_file, value) -> bool:
        changed = False
        for tag in (t for t in (audio_file.tag, audio_file.second_v1_tag) if t):
            getter, setter = self._getAccessors(tag)
            # Normalize "" to None
            if (value or None) != (getter() or None):
                log.debug(f"Set tag value: {value}")
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
            import pdb; pdb.set_trace()  # FIXME
            ...
            raise ValueError(f"Unsupported property name: {prop}")

    def _onChanged(self, widget):
        if self._on_change_active and self._editor_ctl.current_edit:
            tag = self._editor_ctl.current_edit.selected_tag

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

    def _setSensitive(self, state, tooltip_text):
        self.widget.set_sensitive(state)
        self.widget.set_tooltip_text(tooltip_text)
