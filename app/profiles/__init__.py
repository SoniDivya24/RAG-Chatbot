from app.profiles.base import Chunk, Profile, UnavailableProfile
from app.profiles.report import ReportProfile
from app.profiles.standard import StandardProfile

DEFAULT_MODE = "standard"


def default_profiles() -> dict[str, Profile]:
    """Every mode the app knows about, in display order.

    Report is implemented; Long document and Visual document are registered so
    the UI and API can list them, but stay unavailable until their pipelines
    are ported in.
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
        UnavailableProfile(
            "visual",
            "Visual document",
            "Documents whose facts live in tables, charts and footnotes.",
            upload_hint="Short PDFs whose facts sit in tables, charts and footnotes.",
            example_questions=(
                "How much less energy does iMac use compared to the ENERGY STAR requirement?",
                "What is the total carbon footprint of the iMac, and how much of that comes from product use versus manufacturing?",
                "What material is the iMac stand made from, and what percentage of it is recycled?",
            ),
        ),
    ]
    return {p.id: p for p in profiles}


__all__ = [
    "Chunk",
    "Profile",
    "UnavailableProfile",
    "StandardProfile",
    "ReportProfile",
    "DEFAULT_MODE",
    "default_profiles",
]
