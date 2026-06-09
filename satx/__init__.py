"""SatX — terminal satellite and ISM monitoring for SDR backends."""

__version__ = "1.0.0"
__app_name__ = "SatX"

from satx.app.sniffer import SatXSniffer
from satx.config import SnifferConfig

__all__ = ["SatXSniffer", "SnifferConfig", "__app_name__", "__version__"]
