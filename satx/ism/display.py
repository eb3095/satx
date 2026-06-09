"""Rich terminal dashboard for ISM band rtl_433 decoding."""

from __future__ import annotations

from rich.align import Align
from rich.console import Console, Group, RenderableType
from rich.panel import Panel
from rich.text import Text

from satx import __app_name__
from satx.ism.monitor import IsmMonitor
from satx.ui.bars import FullWidthBar


def _dim_text(content: str) -> Text:
    return Text.from_markup(f"[dim]{content}[/]")


class IsmDisplay:
    def __init__(self, monitor: IsmMonitor) -> None:
        self.console = Console()
        self.monitor = monitor

    def render(self) -> Group:
        return Group(
            FullWidthBar(f" {__app_name__} — ISM 433 MHz Sensors "),
            self._status_line(),
            self._messages_panel(),
            self._footer(),
        )

    def _status_line(self) -> Text:
        text = Text()
        text.append(f"{self.monitor.freq_mhz:.3f} MHz", style="bold cyan")
        text.append("  │  ")
        source = "rtl_433 + RTL-SDR" if self.monitor.backend == "rtlsdr" else "rtl_433 + HackRF"
        text.append(source, style="bold yellow")
        text.append("  │  ")
        if not self.monitor.available:
            text.append("rtl_433 missing", style="bold red")
        elif self.monitor.pipe_alive:
            text.append("listening", style="bold green")
        elif self.monitor.running:
            text.append(
                (self.monitor.error or "reconnecting…")[:60],
                style="yellow",
            )
        elif self.monitor.error:
            text.append(self.monitor.error[:60], style="yellow")
        else:
            text.append("starting…", style="yellow")
        text.append("  │  ")
        text.append(f"msgs {len(self.monitor.messages)}", style="magenta")
        return text

    def _messages_panel(self) -> Panel:
        if not self.monitor.available:
            body = _dim_text(
                "rtl_433 is not installed. Install with: brew install rtl_433"
            )
        elif not self.monitor.messages:
            body = Text()
            body.append_text(
                _dim_text(
                    f"Listening on {self.monitor.freq_mhz:.3f} MHz for weather stations, "
                    "TPMS, and other ISM sensors."
                )
            )
            if self.monitor.error:
                body.append("\n")
                body.append(self.monitor.error, style="yellow")
        else:
            body = Text()
            for msg in list(self.monitor.messages)[:20]:
                body.append(msg.timestamp or "—", style="dim")
                body.append("  ")
                body.append(msg.summary())
                body.append("\n")
        return Panel(
            body,
            title="[bold]Decoded ISM Messages[/bold]",
            border_style="green",
            padding=(0, 1),
            style="none",
        )

    def _footer(self) -> RenderableType:
        text = Text()
        text.append("A", style="bold cyan")
        text.append(" APT", style="dim")
        text.append("  ·  ")
        text.append("L", style="bold cyan")
        text.append(" LRPT", style="dim")
        text.append("  ·  ")
        text.append("R", style="bold cyan")
        text.append(" Radio", style="dim")
        text.append("  ·  ")
        text.append_text(_dim_text("Ctrl+C stop"))
        return Align.center(text)
