"""Feature pages registered into the main window stack."""

from .apply import ApplyPage
from .backup import BackupPage
from .base import Page
from .blocked import SAFETY_DOCS_URL, BlockedPage
from .check import CheckPage
from .connect import ConnectPage
from .done import DonePage
from .review import ReviewPage
from .setup import ANDROID_SDK_TERMS_URL, SetupPage
from .welcome import WelcomePage

__all__ = [
    "ANDROID_SDK_TERMS_URL",
    "SAFETY_DOCS_URL",
    "ApplyPage",
    "BackupPage",
    "BlockedPage",
    "CheckPage",
    "ConnectPage",
    "DonePage",
    "Page",
    "ReviewPage",
    "SetupPage",
    "WelcomePage",
]
