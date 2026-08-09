"""Retro-styled Textual widget subclasses — ported from bi_python/forms.py.

In Textual 8.x, widget on_mount fires BEFORE App.on_mount, so any inline
styles set there get overwritten when self.dark=True triggers a CSS
re-evaluation. call_after_refresh() defers style application until after
that settles — a pattern discovered the hard way during bi_python's own
Textual conversion; carried over verbatim here.
"""

from textual.widgets import Input, OptionList, Static, Switch, TextArea


class RetroInput(Input):
    def on_mount(self) -> None:
        try:
            self.styles.border = ("none", "transparent")
        except Exception:
            pass
        self.app.call_after_refresh(self._init_color)

    def _init_color(self) -> None:
        self.styles.color = "white"

    def on_focus(self) -> None:
        self.styles.color = "#ffff55"

    def on_blur(self) -> None:
        self.styles.color = "white"


class RetroTextArea(TextArea):
    """Multi-line text area styled to match the retro theme."""

    def on_mount(self) -> None:
        try:
            self.styles.border = ("none", "transparent")
        except Exception:
            pass
        self.app.call_after_refresh(self._init_color)

    def _init_color(self) -> None:
        self.styles.color = "white"

    def on_focus(self) -> None:
        self.styles.color = "#ffff55"

    def on_blur(self) -> None:
        self.styles.color = "white"


class RetroSwitch(Switch):
    def on_mount(self) -> None:
        try:
            self.styles.border = ("none", "transparent")
        except Exception:
            pass


class _ImgCountWidget(Static):
    """Focusable widget showing image count; Enter opens the image manager."""

    can_focus = True

    def on_key(self, event) -> None:
        if event.key == "enter":
            event.stop()
            self.screen.action_manage_images(self.id)

    def on_focus(self) -> None:
        self.styles.color = "#ffff55"

    def on_blur(self) -> None:
        self.styles.color = "#55ffff"


class _ComboFilterInput(RetroInput):
    """Type-to-filter combo box's filter half — generalized from bi_python's
    bin-specific _BinFilterInput to work for any ComboFilterSelectField, not
    just the item form's Bin field. Must be constructed with
    id=f"combo_filter_{field_name}"; its paired _ComboOptionList must be
    id=f"combo_list_{field_name}" — the pairing is derived from these ids
    rather than a constructor param, since Textual widget __init__ signatures
    (positional *content, etc.) aren't safe to extend with extra args."""

    @property
    def _list_selector(self) -> str:
        field_name = self.id[len("combo_filter_") :]
        return f"#combo_list_{field_name}"

    def on_focus(self) -> None:
        super().on_focus()
        try:
            self.screen.query_one(self._list_selector, OptionList).display = True
        except Exception:
            pass

    def on_blur(self) -> None:
        super().on_blur()
        self.app.call_after_refresh(self.screen._maybe_close_combos)

    def on_key(self, event) -> None:
        if event.key == "down":
            event.stop()
            event.prevent_default()
            try:
                opt_list = self.screen.query_one(self._list_selector, OptionList)
                opt_list.display = True
                opt_list.focus()
            except Exception:
                pass


class _ComboOptionList(OptionList):
    """The combo box's list half: closes (collapses) when focus leaves the
    combo. See _ComboFilterInput's docstring for the id-pairing convention."""

    def on_blur(self) -> None:
        self.app.call_after_refresh(self.screen._maybe_close_combos)
