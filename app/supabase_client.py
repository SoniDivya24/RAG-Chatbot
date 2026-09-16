from supabase import Client, create_client

from app import config

_client: Client | None = None


def get_supabase() -> Client:
    """Lazily create the Supabase client.

    Lazy on purpose: constructing it at import time would throw before
    app.main's own startup checks get a chance to run (Phase 1 only requires
    GOOGLE_API_KEY at import time; Supabase is only needed once a route that
    actually touches storage/retrieval is hit).
    """
    global _client
    if _client is None:
        config.require("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY")
        # service_role key bypasses row-level security - this client must only
        # ever run server-side, never sent to the browser.
        _client = create_client(config.SUPABASE_URL, config.SUPABASE_SERVICE_ROLE_KEY)
    return _client
