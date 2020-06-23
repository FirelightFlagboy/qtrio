import contextlib
import os
import typing

import async_generator
import attr
from qtpy import QtCore
from qtpy import QtWidgets
import trio

import qtrio._qt


@attr.s(auto_attribs=True)
class IntegerDialog:
    parent: QtWidgets.QWidget
    dialog: typing.Optional[QtWidgets.QInputDialog] = None
    edit_widget: typing.Optional[QtWidgets.QWidget] = None
    ok_button: typing.Optional[QtWidgets.QPushButton] = None
    cancel_button: typing.Optional[QtWidgets.QPushButton] = None
    attempt: typing.Optional[int] = None
    result: typing.Optional[int] = None

    shown = qtrio._qt.Signal(QtWidgets.QInputDialog)
    hidden = qtrio._qt.Signal()

    @classmethod
    def build(cls, parent: QtCore.QObject = None,) -> "IntegerDialog":
        return cls(parent=parent)

    def setup(self):
        self.dialog = QtWidgets.QInputDialog(self.parent)

        # TODO: find a better way to trigger population of widgets
        self.dialog.show()

        for widget in self.dialog.findChildren(QtWidgets.QWidget):
            if isinstance(widget, QtWidgets.QLineEdit):
                self.edit_widget = widget
            elif isinstance(widget, QtWidgets.QPushButton):
                if widget.text() == self.dialog.okButtonText():
                    self.ok_button = widget
                elif widget.text() == self.dialog.cancelButtonText():
                    self.cancel_button = widget

            widgets = {self.edit_widget, self.ok_button, self.cancel_button}
            if None not in widgets:
                break
        else:
            raise qtrio._qt.QTrioException("not all widgets found")

        if self.attempt is None:
            self.attempt = 0
        else:
            self.attempt += 1

        self.shown.emit(self.dialog)

    def teardown(self):
        self.edit_widget = None
        self.ok_button = None
        self.cancel_button = None

        if self.dialog is not None:
            self.dialog.hide()
            self.dialog = None
            self.hidden.emit()

    @contextlib.contextmanager
    def manager(self):
        try:
            self.setup()
            yield
        finally:
            self.teardown()

    async def wait(self) -> int:
        while True:
            with self.manager():
                [result] = await qtrio._core.wait_signal(self.dialog.finished)

                if result == QtWidgets.QDialog.Rejected:
                    raise qtrio.UserCancelledError()

                try:
                    self.result = int(self.dialog.textValue())
                except ValueError:
                    continue

            return self.result


@attr.s(auto_attribs=True)
class TextInputDialog:
    title: typing.Optional[str] = None
    label: typing.Optional[str] = None
    parent: typing.Optional[QtCore.QObject] = None

    dialog: typing.Optional[QtWidgets.QInputDialog] = None
    accept_button: typing.Optional[QtWidgets.QPushButton] = None
    reject_button: typing.Optional[QtWidgets.QPushButton] = None
    line_edit: typing.Optional[QtWidgets.QLineEdit] = None
    result: typing.Optional[trio.Path] = None

    shown = qtrio._qt.Signal(QtWidgets.QFileDialog)

    def setup(self):
        self.result = None

        self.dialog = QtWidgets.QInputDialog(parent=self.parent)
        if self.label is not None:
            self.dialog.setLabelText(self.label)
        if self.title is not None:
            self.dialog.setWindowTitle(self.title)

        self.dialog.show()

        buttons = dialog_button_box_buttons_by_role(dialog=self.dialog)
        self.accept_button = buttons[QtWidgets.QDialogButtonBox.AcceptRole]
        self.reject_button = buttons[QtWidgets.QDialogButtonBox.RejectRole]

        [self.line_edit] = self.dialog.findChildren(QtWidgets.QLineEdit)

        self.shown.emit(self.dialog)

    def teardown(self):
        if self.dialog is not None:
            self.dialog.close()
        self.dialog = None
        self.accept_button = None
        self.reject_button = None

    @contextlib.contextmanager
    def manage(self):
        try:
            self.setup()
            yield self
        finally:
            self.teardown()

    async def wait(self):
        with self.manage():
            [result] = await qtrio._core.wait_signal(self.dialog.finished)

            if result == QtWidgets.QDialog.Rejected:
                raise qtrio.UserCancelledError()

            self.result = self.dialog.textValue()

            return self.result


def create_text_input_dialog(
    title: typing.Optional[str] = None,
    label: typing.Optional[str] = None,
    parent: typing.Optional[QtCore.QObject] = None,
):
    return TextInputDialog(title=title, label=label, parent=parent)


def dialog_button_box_buttons_by_role(
    dialog: QtWidgets.QDialog,
) -> typing.Mapping[QtWidgets.QDialogButtonBox.ButtonRole, QtWidgets.QAbstractButton]:
    hits = dialog.findChildren(QtWidgets.QDialogButtonBox)

    if len(hits) == 0:
        return {}

    [button_box] = hits
    return {button_box.buttonRole(button): button for button in button_box.buttons()}


@attr.s(auto_attribs=True)
class FileDialog:
    file_mode: QtWidgets.QFileDialog.FileMode
    accept_mode: QtWidgets.QFileDialog.AcceptMode
    dialog: typing.Optional[QtWidgets.QFileDialog] = None
    parent: typing.Optional[QtCore.QObject] = None
    default_path: typing.Optional[trio.Path] = None
    options: QtWidgets.QFileDialog.Options = QtWidgets.QFileDialog.Options()
    accept_button: typing.Optional[QtWidgets.QPushButton] = None
    reject_button: typing.Optional[QtWidgets.QPushButton] = None
    result: typing.Optional[trio.Path] = None

    shown = qtrio._qt.Signal(QtWidgets.QFileDialog)

    def setup(self):
        self.result = None

        self.dialog = QtWidgets.QFileDialog(parent=self.parent)
        self.dialog.setFileMode(self.file_mode)
        self.dialog.setAcceptMode(self.accept_mode)
        if self.default_path is not None:
            self.dialog.selectFile(os.fspath(self.default_path))

        self.dialog.show()

        buttons = dialog_button_box_buttons_by_role(dialog=self.dialog)
        self.accept_button = buttons.get(QtWidgets.QDialogButtonBox.AcceptRole)
        self.reject_button = buttons.get(QtWidgets.QDialogButtonBox.RejectRole)

        self.shown.emit(self.dialog)

    def teardown(self):
        if self.dialog is not None:
            self.dialog.close()
        self.dialog = None
        self.accept_button = None
        self.reject_button = None

    @contextlib.contextmanager
    def manage(self):
        try:
            self.setup()
            yield self
        finally:
            self.teardown()

    async def wait(self):
        with self.manage():
            [result] = await qtrio._core.wait_signal(self.dialog.finished)

            if result == QtWidgets.QDialog.Rejected:
                raise qtrio.UserCancelledError()

            [path_string] = self.dialog.selectedFiles()
            self.result = trio.Path(path_string)

            return self.result


def create_file_save_dialog(
    parent: typing.Optional[QtCore.QObject] = None,
    default_path: typing.Optional[trio.Path] = None,
    options: QtWidgets.QFileDialog.Options = QtWidgets.QFileDialog.Options(),
):
    return FileDialog(
        parent=parent,
        default_path=default_path,
        options=options,
        file_mode=QtWidgets.QFileDialog.AnyFile,
        accept_mode=QtWidgets.QFileDialog.AcceptSave,
    )


@attr.s(auto_attribs=True)
class MessageBox:
    icon: QtWidgets.QMessageBox.Icon
    title: str
    text: str
    buttons: QtWidgets.QMessageBox.StandardButtons

    parent: typing.Optional[QtCore.QObject] = None

    dialog: typing.Optional[QtWidgets.QMessageBox] = None
    accept_button: typing.Optional[QtWidgets.QPushButton] = None
    result: typing.Optional[trio.Path] = None

    shown = qtrio._qt.Signal(QtWidgets.QMessageBox)

    def setup(self):
        self.result = None

        self.dialog = QtWidgets.QMessageBox(
            self.icon, self.title, self.text, self.buttons, self.parent
        )

        self.dialog.show()

        buttons = dialog_button_box_buttons_by_role(dialog=self.dialog)
        self.accept_button = buttons[QtWidgets.QDialogButtonBox.AcceptRole]

        self.shown.emit(self.dialog)

    def teardown(self):
        if self.dialog is not None:
            self.dialog.close()
        self.dialog = None
        self.accept_button = None

    @contextlib.contextmanager
    def manage(self):
        try:
            self.setup()
            yield self
        finally:
            self.teardown()

    async def wait(self):
        with self.manage():
            [result] = await qtrio._core.wait_signal(self.dialog.finished)

            if result == QtWidgets.QDialog.Rejected:
                raise qtrio.UserCancelledError()


def create_information_message_box(
    icon: QtWidgets.QMessageBox.Icon,
    title: str,
    text: str,
    buttons: QtWidgets.QMessageBox.StandardButtons = QtWidgets.QMessageBox.Ok,
    parent: typing.Optional[QtCore.QObject] = None,
):
    return MessageBox(icon=icon, title=title, text=text, buttons=buttons, parent=parent)


@async_generator.asynccontextmanager
async def manage_progress_dialog(
    title: str,
    label: str,
    minimum: int = 0,
    maximum: int = 0,
    cancel_button_text: str = "Cancel",
    parent: QtCore.QObject = None,
):
    dialog = QtWidgets.QProgressDialog(
        label, cancel_button_text, minimum, maximum, parent
    )
    try:
        dialog.setWindowTitle(title)
        yield dialog
    finally:
        dialog.close()
