import typing

import attr
import qtrio
from qtpy import QtWidgets
import trio
import trio_typing


@attr.s(auto_attribs=True, eq=False)
class Widget:
    widget: QtWidgets.QWidget = attr.ib(factory=QtWidgets.QWidget)
    layout: QtWidgets.QLayout = attr.ib(factory=QtWidgets.QVBoxLayout)
    button: QtWidgets.QPushButton = attr.ib(factory=QtWidgets.QPushButton)
    label: QtWidgets.QWidget = attr.ib(factory=QtWidgets.QLabel)

    text_changed = qtrio.Signal(str)

    def setup(self, message: str) -> None:
        self.button.setText("More")

        # start big enough to fit the whole message
        self.set_text(message)

        self.layout.addWidget(self.button)
        self.layout.addWidget(self.label)
        self.widget.setLayout(self.layout)

    def show(self) -> None:
        self.widget.show()
        self.set_text("")

    def set_text(self, text: str) -> None:
        self.label.setText(text)
        self.text_changed.emit(text)

    async def run(
        self,
        message: str,
        *,
        task_status: trio_typing.TaskStatus[None] = trio.TASK_STATUS_IGNORED,
    ):
        async with qtrio.enter_emissions_channel(
            signals=[self.button.clicked]
        ) as emissions:
            i = 1
            task_status.started(self)

            async for _ in emissions.channel:  # pragma: no branch
                self.set_text(message[:i])
                i += 1

                if i > len(message):
                    break

            # wait for another click to finish
            await emissions.channel.receive()

    @classmethod
    async def start(
        cls,
        message: str = "Hello world.",
        *,
        task_status: trio_typing.TaskStatus[None] = trio.TASK_STATUS_IGNORED,
    ) -> None:
        self = cls()
        self.setup(message=message)
        self.show()
        async with trio.open_nursery() as nursery:
            await nursery.start(self.run, message)
            task_status.started(self)


if __name__ == "__main__":  # pragma: no cover
    qtrio.run(Widget.start)
