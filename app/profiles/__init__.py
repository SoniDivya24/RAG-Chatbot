from app.profiles.base import Chunk, Profile, UnavailableProfile
from app.profiles.report import ReportProfile
from app.profiles.standard import StandardProfile
from app.profiles.visual import VisualProfile

DEFAULT_MODE = "standard"


def default_profiles() -> dict[str, Profile]:
    """Every mode the app knows about, in display order.

    Standard, Report and Visual document are implemented; Long document is
    registered so the UI and API can list it, but stays unavailable until its
    pipeline is ported in.
    """
    profiles: list[Profile] = [
        StandardProfile(),
        ReportProfile(),
        UnavailableProfile(
            "long",
            "Long document",
            "Long structured documents: section-aware retrieval with managed context.",
            upload_hint="Long PDFs organised into chapters and sections (100+ pages).",
            example_questions=(
                "What is the growth outlook for South Asia in this report?",
                "What does Chapter 3 say about sovereign debt in developing economies?",
                "According to the executive summary, what are the main risks to the global outlook?",
            ),
        ),
        VisualProfile(),
    ]
    return {p.id: p for p in profiles}


__all__ = [
    "Chunk",
    "Profile",
    "UnavailableProfile",
    "StandardProfile",
    "ReportProfile",
    "VisualProfile",
    "DEFAULT_MODE",
    "default_profiles",
]
