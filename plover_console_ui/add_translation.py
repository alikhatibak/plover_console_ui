# some of this code is derivative of code in plover core
# for full source of that, visit: https://github.com/openstenoproject/plover

from prompt_toolkit.buffer import Buffer
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout.containers import HSplit
from prompt_toolkit.widgets import TextArea
from prompt_toolkit.application import get_app

from plover.steno import sort_steno_strokes
from plover.translation import escape_translation
from plover.formatting import RetroFormatter


def dictionary_filter(key, value):
    # Allow undo...
    if value == "=undo":
        return False
    # ...and translations with special entries. Do this by looking for
    # braces but take into account escaped braces and slashes.
    escaped = value.replace("\\\\", "").replace("\\{", "")
    special = "{#" in escaped or "{PLOVER:" in escaped
    return not special


def format_label(fmt, strokes, translation):
    if strokes:
        strokes = ", ".join("/".join(s) for s in sort_steno_strokes(strokes))
    if translation:
        translation = escape_translation(translation)

    return fmt.format(strokes=strokes, translation=translation)


class AddTranslation:
    def __init__(self, engine, on_output, on_exit):
        self.engine = engine
        self.on_exit = on_exit
        self.on_output = on_output
        self.outcome = ""

        self.strokes_info = ""
        self.translation_info = ""
        # we start in the strokes field
        self.engine.add_dictionary_filter(dictionary_filter)

        self.strokes_field = TextArea(
            prompt="Strokes: ",
            height=1,
            multiline=False,
            wrap_lines=False,
            accept_handler=self.accept,
            style="class:normal",
        )

        self.strokes_field.buffer.on_text_changed += self.strokes_changed
        self.translation_field = TextArea(
            prompt="Output: ",
            height=1,
            multiline=False,
            wrap_lines=False,
            accept_handler=self.accept,
            style="class:normal",
        )

        self.translation_field.buffer.on_text_changed += self.translation_changed

        last_translations = engine.translator_state.translations
        retro_formatter = RetroFormatter(last_translations)
        last_words = retro_formatter.last_words(1)

        if last_words:
            self.translation_field.text = last_words[0]

        kb = KeyBindings()

        @kb.add("escape", eager=True)
        def _(event):
            layout = get_app().layout
            if layout.has_focus(self.strokes_field):
                self.engine.remove_dictionary_filter(dictionary_filter)
            self.outcome = "Add translation abandoned"
            self.update_output()
            on_exit()

        @kb.add("tab")
        def _(event):
            self.cycle_focus()

        self.container = HSplit(
            [self.strokes_field, self.translation_field],
            key_bindings=kb,
        )

    def strokes(self):
        return tuple(self.strokes_field.text.strip().split())

    def cycle_focus(self):
        layout = get_app().layout
        if layout.has_focus(self.strokes_field):
            self.engine.remove_dictionary_filter(dictionary_filter)
        else:
            self.engine.add_dictionary_filter(dictionary_filter)
        layout.focus_next()

    def accept(self, _):
        if self.strokes() and self.translation_field.text:
            self.engine.add_translation(self.strokes(), self.translation_field.text)
            self.outcome = "Translation added"
            self.update_output()
            self.on_exit()
        else:
            self.outcome = "Invalid"
            self.update_output()

    def strokes_changed(self, buff: Buffer):
        strokes = self.strokes()
        if strokes:
            translation = self.engine.raw_lookup(strokes)
            if translation is not None:
                fmt = "{strokes} maps to {translation}"
            else:
                fmt = "{strokes} is not in the dictionary"
            info = format_label(fmt, (strokes,), translation)
        else:
            info = ""
        self.strokes_info = info
        self.update_output()

    def translation_changed(self, buff: Buffer):
        translation = buff.text
        if translation:
            strokes = self.engine.reverse_lookup(translation)
            if strokes:
                fmt = "{translation} is mapped to: {strokes}"
            else:
                fmt = "{translation} is not in the dictionary"
            info = format_label(fmt, strokes, translation)
        else:
            info = ""
        self.translation_info = info
        self.update_output()

    def update_output(self):
        self.on_output(
            "Add translation\n"
            "---------------\n"
            f"{self.strokes_info}\n"
            f"{self.translation_info}\n"
            "---------------\n"
            f"{self.outcome if self.outcome else None}"
        )
