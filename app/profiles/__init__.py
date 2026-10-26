from app.profiles.base import Chunk, Profile, UnavailableProfile
from app.profiles.long import LongDocumentProfile
from app.profiles.report import ReportProfile
from app.profiles.standard import StandardProfile
from app.profiles.visual import VisualProfile

DEFAULT_MODE = "standard"


def default_profiles() -> dict[str, Profile]:
    """Every mode the app knows about, in display order.

    All four modes are implemented. (`UnavailableProfile` stays for registering a
    mode that is planned but not built.)
    """
    profiles: list[Profile] = [
        StandardProfile(),
        ReportProfile(),
        LongDocumentProfile(),
        VisualProfile(),
    ]
    return {p.id: p for p in profiles}


__all__ = [
    "Chunk",
    "Profile",
    "UnavailableProfile",
    "StandardProfile",
    "ReportProfile",
    "LongDocumentProfile",
    "VisualProfile",
    "DEFAULT_MODE",
    "default_profiles",
]
