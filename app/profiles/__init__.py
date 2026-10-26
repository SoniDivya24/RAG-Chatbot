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
        ),
        UnavailableProfile(
            "long",
            "Long document",
            "Long structured documents: section-aware retrieval with managed context.",
        ),
        UnavailableProfile(
            "visual",
            "Visual document",
            "Documents whose facts live in tables, charts and footnotes.",
        ),
    ]
    return {p.id: p for p in profiles}


__all__ = ["Chunk", "Profile", "UnavailableProfile", "StandardProfile", "DEFAULT_MODE", "default_profiles"]
