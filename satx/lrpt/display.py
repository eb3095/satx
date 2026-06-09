"""Rich terminal dashboard for METEOR LRPT monitoring."""

from __future__ import annotations

from rich import box
from rich.align import Align
from rich.console import Console, Group, RenderableType
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from satx import __app_name__
from satx.config import RadioConfig
from satx.lrpt.monitor import LrptMonitor
from satx.ui.bars import FullWidthBar
from satx.ui.image_braille import braille_lines


def _dim_text(content: str) -> Text:
    return Text.from_markup(f"[dim]{content}[/]")


class LrptDisplay:
    def __init__(self, monitor: LrptMonitor, radio: RadioConfig) -> None:
        self.console = Console()
        self.monitor = monitor
        self.radio = radio

    def render(self) -> Group:
        channel = self.monitor.selected_channel()
        return Group(
            FullWidthBar(f" {__app_name__} — METEOR LRPT Monitor "),
            self._status_line(channel),
            self._channel_panel(),
            self._metrics_panel(channel),
            self._events_panel(),
            self._footer(),
        )

    def _status_line(self, channel) -> Text:
        text = Text()
        text.append(f"{channel.freq_mhz:.3f} MHz", style="bold cyan")
        text.append("  │  ")
        text.append(channel.name, style="bold yellow")
        text.append("  │  ")
        status = "pass energy" if self.monitor.sync_hint else "listening (noise)"
        style = "bold green" if self.monitor.sync_hint else "dim"
        text.append(status, style=style)
        return text

    def _channel_panel(self) -> Panel:
        table = Table(
            box=box.SIMPLE_HEAVY, show_header=True, header_style="bold", expand=True
        )
        table.add_column("", width=2, justify="center")
        table.add_column("MHz", width=9, justify="right")
        table.add_column("Satellite", width=16)
        table.add_column("Description", ratio=1)
        page_start = self.monitor.page_index * self.monitor.channel_page_size
        for offset, channel in enumerate(self.monitor.page_channels()):
            idx = page_start + offset
            marker = "▶" if idx == self.monitor.selected_index else ""
            row_style = (
                "bold white on blue" if idx == self.monitor.selected_index else ""
            )
            table.add_row(
                marker,
                f"{channel.freq_mhz:.3f}",
                channel.name,
                channel.description,
                style=row_style,
            )
        title = (
            "[bold]LRPT Channels[/bold] · "
            f"page {self.monitor.page_index + 1}/{self.monitor.page_count} "
            f"({self.monitor.page_range_label()})"
        )
        return Panel(
            table, title=title, border_style="cyan", padding=(0, 0), style="none"
        )

    def _metrics_panel(self, channel) -> Panel:
        body = Text()
        body.append("SNR vs noise floor: ", style="dim")
        body.append(f"{self.monitor.signal_level:.1f} dB\n")
        body.append("Peak/mean ratio: ", style="dim")
        body.append(f"{self.monitor.digital_energy:.1f}\n")
        body.append("Spectrum: ", style="dim")
        if self.monitor.sync_hint:
            body.append(
                "structured pass energy — use satdump for images\n", style="green"
            )
        else:
            body.append(
                "noise only — static waterfall is normal without a pass\n", style="dim"
            )
        if self.monitor.satdump_available:
            body.append("satdump: installed\n", style="green")
        else:
            body.append(
                "satdump: not installed (brew install satdump)\n", style="yellow"
            )
        image = self.monitor.current_image()
        if image is not None:
            body.append("\n")
            for line in braille_lines(image, rows=6):
                body.append_text(line)
                body.append("\n")
            body.append_text(_dim_text("Preview.app · press s to save waterfall"))
        else:
            body.append_text(
                _dim_text(f"Channel {channel.name} · {channel.freq_mhz:.3f} MHz")
            )
        return Panel(
            body,
            title="[bold]LRPT Metrics[/bold]",
            border_style="magenta",
            padding=(0, 1),
            style="none",
        )

    def _events_panel(self) -> Panel:
        events = list(self.monitor.events)[:12]
        if not events:
            body = _dim_text(
                "Pass events appear when LRPT SNR crosses threshold. "
                "Image window opens only during a detected pass."
            )
        else:
            body = Text()
            for event in events:
                body.append(event.timestamp, style="dim")
                body.append("  ")
                body.append(event.message)
                body.append("\n")
        return Panel(
            body,
            title="[bold]Recent Events[/bold]",
            border_style="green",
            padding=(0, 1),
            style="none",
        )

    def _footer(self) -> RenderableType:
        text = Text()
        text.append("↑", style="bold cyan")
        text.append(" ")
        text.append("↓", style="bold cyan")
        text.append(" channel", style="dim")
        text.append("  ·  ")
        text.append("s", style="bold cyan")
        text.append(" save waterfall", style="dim")
        text.append("  ·  ")
        text.append("A", style="bold cyan")
        text.append(" APT", style="dim")
        text.append("  ·  ")
        text.append("I", style="bold cyan")
        text.append(" ISM", style="dim")
        text.append("  ·  ")
        text.append("R", style="bold cyan")
        text.append(" Radio", style="dim")
        text.append("  ·  ")
        text.append_text(_dim_text("Ctrl+C stop"))
        return Align.center(text)
