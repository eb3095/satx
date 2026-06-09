"""Rich terminal dashboard for NOAA APT decoding."""

from __future__ import annotations

from rich import box
from rich.align import Align
from rich.console import Console, Group, RenderableType
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from satx import __app_name__
from satx.apt.monitor import AptMonitor
from satx.config import RadioConfig
from satx.ui.bars import FullWidthBar
from satx.ui.image_braille import braille_lines


def _dim_text(content: str) -> Text:
    return Text.from_markup(f"[dim]{content}[/]")


class AptDisplay:
    def __init__(self, monitor: AptMonitor, radio: RadioConfig) -> None:
        self.console = Console()
        self.monitor = monitor
        self.radio = radio

    def render(self) -> Group:
        channel = self.monitor.selected_channel()
        return Group(
            FullWidthBar(f" {__app_name__} — NOAA APT Weather "),
            self._status_line(channel),
            self._channel_panel(),
            self._metrics_panel(channel),
            self._events_panel(),
            self._footer(),
        )

    def _status_line(self, channel) -> Text:
        dec = self.monitor.decoder
        text = Text()
        text.append(f"{channel.freq_mhz:.4f} MHz", style="bold cyan")
        text.append("  │  ")
        text.append(channel.name, style="bold yellow")
        text.append("  │  ")
        if dec.holding_completed_image:
            status = "complete · saved"
            style = "bold green"
        elif self.monitor.sync_hint:
            status = "pass detected"
            style = "bold green"
        else:
            status = "listening (noise)"
            style = "dim"
        text.append(status, style=style)
        text.append("  │  ")
        text.append(f"lines {dec.line_count}", style="bold green")
        text.append("  │  ")
        text.append(f"sync {dec.sync_count}", style="cyan")
        return text

    def _channel_panel(self) -> Panel:
        table = Table(
            box=box.SIMPLE_HEAVY, show_header=True, header_style="bold", expand=True
        )
        table.add_column("", width=2, justify="center")
        table.add_column("MHz", width=10, justify="right")
        table.add_column("Satellite", width=16)
        table.add_column("Description", ratio=1)
        page_start = self.monitor.page_index * self.monitor.channel_page_size
        page_rows = self.monitor.page_channels()
        if not page_rows:
            table.add_row("", "—", "—", _dim_text("No APT channels configured"))
        else:
            for offset, channel in enumerate(page_rows):
                idx = page_start + offset
                marker = "▶" if idx == self.monitor.selected_index else ""
                row_style = (
                    "bold white on blue" if idx == self.monitor.selected_index else ""
                )
                table.add_row(
                    marker,
                    f"{channel.freq_mhz:.4f}",
                    channel.name,
                    channel.description,
                    style=row_style,
                )
        title = (
            "[bold]APT Channels[/bold] · "
            f"page {self.monitor.page_index + 1}/{self.monitor.page_count} "
            f"({self.monitor.page_range_label()})"
        )
        return Panel(
            table, title=title, border_style="cyan", padding=(0, 0), style="none"
        )

    def _metrics_panel(self, channel) -> Panel:
        dec = self.monitor.decoder
        body = Text()
        body.append("SNR vs noise floor: ", style="dim")
        body.append(f"{self.monitor.signal_level:.1f} dB\n")
        body.append("Peak/mean ratio: ", style="dim")
        body.append(f"{self.monitor.digital_energy:.1f}\n")
        body.append("Audio RMS: ", style="dim")
        body.append(f"{dec.signal_level:.3f}\n")
        body.append("Decode: ", style="dim")
        if dec.holding_completed_image:
            body.append("image complete — held until next pass\n", style="green")
        elif self.monitor.sync_hint and dec.line_count:
            body.append(
                f"lines building ({dec.line_count}) · sync {dec.sync_count}\n",
                style="green",
            )
        elif self.monitor.sync_hint:
            body.append("pass energy — waiting for APT line sync\n", style="yellow")
        else:
            body.append("noise only — normal between satellite passes\n", style="dim")

        image = dec.current_image()
        spectrum = self.monitor.spectrum_image()
        preview = image if image is not None else spectrum
        if preview is not None:
            body.append("\n")
            label = "APT image" if image is not None else "spectrum waterfall"
            for line in braille_lines(preview, rows=6):
                body.append_text(line)
                body.append("\n")
            body.append_text(_dim_text(f"{label} · Preview.app · press s to save"))
        else:
            body.append_text(
                _dim_text(f"Channel {channel.name} · {channel.freq_mhz:.4f} MHz")
            )
        return Panel(
            body,
            title="[bold]APT Metrics[/bold]",
            border_style="magenta",
            padding=(0, 1),
            style="none",
        )

    def _events_panel(self) -> Panel:
        events = list(self.monitor.events)[:12]
        if not events:
            body = _dim_text(
                "Pass events appear when APT SNR crosses threshold or line sync "
                "starts. Image auto-saves when a pass completes."
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
        text.append("g", style="bold cyan")
        text.append(" ")
        text.append("G", style="bold cyan")
        text.append(" pages", style="dim")
        text.append("  ·  ")
        text.append("s", style="bold cyan")
        text.append(" save PNG", style="dim")
        text.append("  ·  ")
        text.append("L", style="bold cyan")
        text.append(" LRPT", style="dim")
        text.append("  ·  ")
        text.append("I", style="bold cyan")
        text.append(" ISM", style="dim")
        text.append("  ·  ")
        text.append("R", style="bold cyan")
        text.append(" Radio", style="dim")
        text.append("  ·  ")
        text.append_text(_dim_text("Ctrl+C stop"))
        return Align.center(text)
