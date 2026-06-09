"""SatX live capture and replay orchestrator."""

from __future__ import annotations

import time
from typing import Literal

import numpy as np
from rich.live import Live

from satx.apt.display import AptDisplay
from satx.apt.monitor import AptMonitor
from satx.app.shutdown import ShutdownCoordinator
from satx.config import SnifferConfig
from satx.ism.display import IsmDisplay
from satx.ism.monitor import IsmMonitor
from satx.log_writer import LogWriter
from satx.lrpt.display import LrptDisplay
from satx.lrpt.monitor import LrptMonitor
from satx.radio.receiver import RadioReceiver, make_receiver
from satx.radio.voice_monitor import VoiceMonitor
from satx.ui.image_preview import ImagePreview
from satx.ui.keyboard import drain_keys, restore_terminal, terminal_session
from satx.ui.radio_display import SatRadioDisplay

DashboardMode = Literal["apt", "lrpt", "ism", "sat_radio"]
PREVIEW_SYNC_INTERVAL = 0.25


class SatXSniffer:
    def __init__(self, config: SnifferConfig) -> None:
        self.config = config
        self._log_writer = LogWriter()
        self.apt_monitor = AptMonitor(
            config.apt_channels,
            radio_backend=config.radio.backend,
            log_writer=self._log_writer,
        )
        self.lrpt_monitor = LrptMonitor(
            config.lrpt_channels,
            radio_backend=config.radio.backend,
            log_writer=self._log_writer,
        )
        self.ism_monitor = IsmMonitor(
            config.ism_freq_mhz,
            radio=config.radio,
            log_writer=self._log_writer,
        )
        self.voice_monitor = VoiceMonitor(
            config.sat_radio_channels,
            radio_backend=config.radio.backend,
            log_writer=self._log_writer,
        )
        self.apt_display = AptDisplay(self.apt_monitor, config.radio)
        self.lrpt_display = LrptDisplay(self.lrpt_monitor, config.radio)
        self.ism_display = IsmDisplay(self.ism_monitor)
        self.radio_display = SatRadioDisplay(self.voice_monitor, config.radio)
        self.dashboard: DashboardMode = "apt"
        self.receiver: RadioReceiver = make_receiver(
            config.radio, freq_hz=self._tuned_frequency()
        )
        self._image_preview: ImagePreview | None = None
        self._last_preview_sync = 0.0

    def _image_dashboard(self) -> bool:
        return self.dashboard in ("apt", "lrpt")

    def _ensure_image_preview(self) -> ImagePreview:
        if self._image_preview is None:
            self._image_preview = ImagePreview("SatX — Live Image")
        if not self._image_preview.active:
            self._image_preview.start()
        return self._image_preview

    def _close_image_preview(self) -> None:
        if self._image_preview is not None:
            self._image_preview.close()
            self._image_preview = None

    def _sync_image_preview(self, *, force: bool = False) -> None:
        if not self._image_dashboard():
            self._close_image_preview()
            return
        now = time.time()
        if not force and now - self._last_preview_sync < PREVIEW_SYNC_INTERVAL:
            return

        if self.dashboard == "apt":
            channel = self.apt_monitor.selected_channel()
            dec = self.apt_monitor.decoder
            image = dec.current_image()
            if dec.holding_completed_image:
                status = f"APT · {channel.name} · complete · saved"
            else:
                status = (
                    f"APT · {channel.name} · {dec.line_count} lines · "
                    f"sync {dec.sync_count}"
                )
        else:
            channel = self.lrpt_monitor.selected_channel()
            image = self.lrpt_monitor.current_image()
            status = (
                f"LRPT waterfall · {channel.name} · "
                f"lvl {self.lrpt_monitor.signal_level:.3f}"
            )

        if image is None:
            return

        self._last_preview_sync = now
        preview = self._ensure_image_preview()
        preview.update(image, status=status)

    def _save_current_image(self) -> None:
        if self.dashboard == "apt":
            self.apt_monitor.save_image()
        elif self.dashboard == "lrpt":
            self.lrpt_monitor.save_image()
        self._sync_image_preview()

    def _tuned_frequency(self) -> int:
        if self.dashboard == "sat_radio":
            return self.voice_monitor.selected_channel().freq_hz
        if self.dashboard == "lrpt":
            return self.lrpt_monitor.selected_channel().freq_hz
        if self.dashboard == "apt":
            return self.apt_monitor.selected_channel().freq_hz
        return self.apt_monitor.selected_channel().freq_hz

    def _uses_iq_receiver(self) -> bool:
        return self.dashboard != "ism"

    def _active_console(self):
        if self.dashboard == "lrpt":
            return self.lrpt_display.console
        if self.dashboard == "ism":
            return self.ism_display.console
        if self.dashboard == "sat_radio":
            return self.radio_display.console
        return self.apt_display.console

    def _apply_tuning(self) -> None:
        if not self._uses_iq_receiver():
            return
        self.receiver.set_frequency(self._tuned_frequency())

    def _stop_rf_sources(self, *, fast: bool = False) -> None:
        if self.receiver.running:
            self.receiver.stop(fast=fast)
        if self.ism_monitor.running:
            self.ism_monitor.stop(fast=fast)

    def _teardown_live(self) -> None:
        self._close_image_preview()
        self.voice_monitor.shutdown()
        self._stop_rf_sources(fast=True)
        self._log_writer.close()

    def set_dashboard(self, mode: DashboardMode) -> None:
        if self.dashboard == mode:
            return
        previous = self.dashboard
        self.dashboard = mode
        if mode not in ("apt", "lrpt"):
            self._close_image_preview()
        if previous == "ism":
            self.ism_monitor.stop()
        if mode == "ism":
            if self.receiver.running:
                self.receiver.stop()
            self.ism_monitor.start()
        else:
            if mode != previous and self.ism_monitor.running:
                self.ism_monitor.stop()
            self._apply_tuning()
            if not self.receiver.running:
                self.receiver.start()

    def _render(self, now: float):
        _ = now
        if self.dashboard == "lrpt":
            return self.lrpt_display.render()
        if self.dashboard == "ism":
            return self.ism_display.render()
        if self.dashboard == "sat_radio":
            return self.radio_display.render()
        return self.apt_display.render()

    def _handle_channel_keys(self, key: str) -> None:
        if self.dashboard == "apt":
            monitor = self.apt_monitor
        elif self.dashboard == "lrpt":
            monitor = self.lrpt_monitor
        elif self.dashboard == "sat_radio":
            monitor = self.voice_monitor
        else:
            return
        if key == "channel_up":
            monitor.channel_up()
            self._apply_tuning()
        elif key == "channel_down":
            monitor.channel_down()
            self._apply_tuning()
        elif key == "first":
            monitor.channel_page_up()
        elif key == "last":
            monitor.channel_page_down()
        elif key == "prev" and self.dashboard == "sat_radio":
            self.voice_monitor.squelch_down()
        elif key == "next" and self.dashboard == "sat_radio":
            self.voice_monitor.squelch_up()
        elif key == "volume_up" and self.dashboard == "sat_radio":
            self.voice_monitor.volume_up()
        elif key == "volume_down" and self.dashboard == "sat_radio":
            self.voice_monitor.volume_down()
        elif key == "save_image" and self.dashboard in ("apt", "lrpt"):
            self._save_current_image()
            self._sync_image_preview(force=True)

    def _handle_keys(self, live: Live, last_render: float) -> tuple[bool, float]:
        for key in drain_keys():
            if key == "quit":
                return False, last_render
            if key == "dashboard_apt":
                self.set_dashboard("apt")
                self._last_preview_sync = 0.0
            elif key == "dashboard_lrpt":
                self.set_dashboard("lrpt")
                self._last_preview_sync = 0.0
            elif key == "dashboard_ism":
                self.set_dashboard("ism")
            elif key == "dashboard_sat_radio":
                self.set_dashboard("sat_radio")
            else:
                self._handle_channel_keys(key)
            now = time.time()
            live.update(self._render(now))
            last_render = now
        return True, last_render

    def run_live(self) -> None:
        if self._uses_iq_receiver():
            self.receiver.start()
        shutdown = ShutdownCoordinator()
        shutdown.on_exit(self._teardown_live)
        shutdown.install()
        last_render = 0.0
        console = self._active_console()
        try:
            with terminal_session():
                with Live(
                    self._render(time.time()),
                    console=console,
                    refresh_per_second=self.config.refresh_hz,
                    screen=True,
                    transient=False,
                ) as live:
                    while shutdown.running:
                        now = time.time()
                        shutdown.running, last_render = self._handle_keys(live, last_render)
                        if not shutdown.running:
                            break
                        if self.dashboard == "ism":
                            self.ism_monitor.poll()
                        else:
                            chunk = self.receiver.read_chunk(
                                timeout=0.0 if not shutdown.running else 0.05
                            )
                            if chunk:
                                if self.dashboard == "apt":
                                    self.apt_monitor.process_iq(chunk, now=now)
                                elif self.dashboard == "lrpt":
                                    self.lrpt_monitor.process_iq(chunk, now=now)
                                else:
                                    self.voice_monitor.process_iq(chunk, now=now)
                            elif self.receiver.exited:
                                detail = self.receiver.exit_error()
                                raise RuntimeError(
                                    detail
                                    or "Radio receiver exited unexpectedly. "
                                    "Check SDR USB connection."
                                )
                        if now - last_render >= 1.0 / self.config.refresh_hz:
                            if (
                                self._image_preview is not None
                                and self._image_preview.poll_save()
                            ):
                                self._save_current_image()
                            if self._image_dashboard():
                                self._sync_image_preview()
                            live.update(self._render(now))
                            last_render = now
        finally:
            shutdown.cleanup()
            restore_terminal()

    def run_file(self, path: str) -> None:
        try:
            with open(path, "rb") as fh:
                data = fh.read()
            now = time.time()
            self.apt_monitor.process_iq(data, now=now)
            self.lrpt_monitor.process_iq(data, now=now)
            self.apt_display.console.print(self.apt_display.render())
            self.lrpt_display.console.print(self.lrpt_display.render())
        finally:
            self._log_writer.close()
