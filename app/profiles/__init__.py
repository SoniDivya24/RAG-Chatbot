from app.profiles.base import Chunk, Profile, UnavailableProfile
from app.profiles.standard import StandardProfile

DEFAULT_MODE = "standard"


def default_profiles() -> dict[str, Profile]:
    """Every mode the app knows about, in display order.

    The three scenario modes are registered now so the UI and API can list
    them, but stay unavailable until their pipelines are ported in.
    """
    profiles: list[Profile] = [
        StandardProfile(),
        UnavailableProfile(
            "report",
            "Report",
            "Plain-text reports: page-aware answers with page citations.",
            upload_hint="PDF reports written in running text, such as an annual report.",
            example_questions=(
                "How many depository libraries did GPO staff visit in FY 2018?",
                "What new digital system replaced FDsys, and when was it fully deployed?",
                "How much did GPO procure in printing and information products in FY 2018 on behalf of federal agencies?",
            ),
        ),
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


__all__ = ["Chunk", "Profile", "UnavailableProfile", "StandardProfile", "DEFAULT_MODE", "default_profiles"]
