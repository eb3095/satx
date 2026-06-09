"""Satellite NBFM radio monitor dashboard."""

from __future__ import annotations

from typing import List

from rich import box
from rich.align import Align
from rich.console import Console, Group, RenderableType
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from satx import __app_name__
from satx.config import MAX_RADIO_TRANSCRIPTS, WAVEFORM_HEIGHT, RadioConfig
from satx.dsp.waveform import WaveformView
from satx.radio.voice_monitor import TranscriptLine, VoiceMonitor
from satx.ui.bars import FullWidthBar


def _dim_text(content: str) -> Text:
    return Text.from_markup(f"[dim]{content}[/]")


class SatRadioDisplay:
    def __init__(self, monitor: VoiceMonitor, radio: RadioConfig) -> None:
        self.console = Console()
        self.monitor = monitor
        self.radio = radio

    def render(self) -> Group:
        channel = self.monitor.selected_channel()
        return Group(
            FullWidthBar(f" {__app_name__} — Satellite Radio "),
            self._status_line(channel),
            self._channel_panel(),
            self._waveform_panel(),
            self._transcript_panel(channel),
            self._footer(),
        )

    def _status_line(self, channel) -> Text:
        text = Text()
        text.append(f"{channel.freq_mhz:.3f} MHz", style="bold cyan")
        text.append("  │  ")
        text.append(channel.name, style="bold yellow")
        text.append("  │  ")
        text.append(f"vol {self.monitor.volume:.1f}x", style="bold magenta")
        text.append("  │  ")
        squelch_style = "green" if self.monitor.gate_open else "dim"
        text.append(
            f"squelch {self.monitor.squelch.snr_db:.0f} dB", style=squelch_style
        )
        text.append("  │  ")
        level = self.monitor.squelch.last_rms
        text.append(f"lvl {level:.2f}", style="cyan" if level > 0.05 else "dim")
        text.append("  │  ")
        text.append(
            "audio on" if self.monitor.audio_available else "audio off",
            style="green" if self.monitor.audio_available else "yellow",
        )
        text.append("  │  ")
        stt = self.monitor.transcriber_status
        if self.monitor.stt_available:
            text.append(stt, style="green")
        elif stt == "loading":
            text.append("loading", style="dim")
        else:
            text.append("missing dependencies", style="yellow")
        return text

    def _channel_panel(self) -> Panel:
        table = Table(
            box=box.SIMPLE_HEAVY, show_header=True, header_style="bold", expand=True
        )
        table.add_column("", width=2, justify="center")
        table.add_column("MHz", width=9, justify="right")
        table.add_column("Satellite", width=20)
        table.add_column("Description", ratio=1)
        table.add_column("Msgs", width=5, justify="right")
        page_start = self.monitor.page_index * self.monitor.channel_page_size
        page_rows = self.monitor.page_channels()
        if not page_rows:
            table.add_row("", "—", "—", _dim_text("No channels configured"), "0")
        else:
            for offset, channel in enumerate(page_rows):
                idx = page_start + offset
                marker = "▶" if idx == self.monitor.selected_index else ""
                row_style = (
                    "bold white on blue" if idx == self.monitor.selected_index else ""
                )
                count = len(self.monitor.buffer_for(channel.channel_id))
                table.add_row(
                    marker,
                    f"{channel.freq_mhz:.3f}",
                    channel.name,
                    channel.description,
                    str(count),
                    style=row_style,
                )
        title = (
            "[bold]Satellite Channels[/bold] · "
            f"page {self.monitor.page_index + 1}/{self.monitor.page_count} "
            f"({self.monitor.page_range_label()})"
        )
        return Panel(
            table, title=title, border_style="cyan", padding=(0, 0), style="none"
        )

    def _waveform_panel(self) -> Panel:
        gate = "open" if self.monitor.gate_open else "closed"
        body = WaveformView(
            self.monitor.waveform,
            gate_open=self.monitor.gate_open,
            height=WAVEFORM_HEIGHT,
        )
        return Panel(
            body,
            title=f"[bold]Signal[/bold] — squelch {gate}",
            border_style="magenta",
            padding=(0, 0),
            style="none",
        )

    def _transcript_panel(self, channel) -> Panel:
        lines: List[TranscriptLine] = list(self.monitor.buffer_for(channel.channel_id))
        if not lines:
            body = _dim_text(
                f"Listening on {channel.freq_mhz:.3f} MHz — {channel.name}. "
                "Transmissions appear here."
            )
        else:
            parts: List[RenderableType] = []
            for line in reversed(lines):
                row = Text()
                row.append(line.timestamp, style="dim")
                row.append("  ")
                row.append(line.text)
                parts.append(row)
            body = Text("\n").join(parts)
        return Panel(
            body,
            title=(
                f"[bold]Live Transcript[/bold] — {channel.name} "
                f"({channel.freq_mhz:.3f} MHz) · last {MAX_RADIO_TRANSCRIPTS}"
            ),
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
        text.append("[", style="bold cyan")
        text.append(" ")
        text.append("]", style="bold cyan")
        text.append(" squelch", style="dim")
        text.append("  ·  ")
        text.append("-", style="bold cyan")
        text.append(" ")
        text.append("+", style="bold cyan")
        text.append(" volume", style="dim")
        text.append("  ·  ")
        text.append("A", style="bold cyan")
        text.append(" APT", style="dim")
        text.append("  ·  ")
        text.append("L", style="bold cyan")
        text.append(" LRPT", style="dim")
        text.append("  ·  ")
        text.append("I", style="bold cyan")
        text.append(" ISM", style="dim")
        text.append("  ·  ")
        text.append_text(_dim_text("Ctrl+C stop"))
        return Align.center(text)
