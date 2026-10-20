"""Extension points for future official, approved API integrations.
Do not call restricted third-party endpoints without the necessary credentials,
user scopes, app review, contractual authorisation and current provider docs.

When an approved connector is implemented it should output `observations`
dictionaries with the fields accepted by db.save_observations and a source
such as 'instagram_official', 'tiktok_official' or 'trends_official'.
No integrations or API approvals are bundled with this MVP.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class ConnectionStatus:
    name: str
    state: str
    needed: str


CONNECTORS = [
    ConnectionStatus("Google News RSS", "Public feed - implemented", "Internet; public RSS endpoint (not an exhaustive API)"),
    ConnectionStatus("The Guardian Food RSS", "Public feed - implemented", "Internet; published RSS feed"),
    ConnectionStatus("Wikimedia Pageviews", "Public API - implemented", "Internet; descriptive User-Agent, preferably with operator contact"),
    ConnectionStatus("Google Trends", "CSV import - implemented", "Export 'Interest over time' from Google Trends; official API requires restricted access"),
    ConnectionStatus("Instagram", "CSV import - implemented", "Authorised professional account + Meta app permissions/review for later official Graph API connector"),
    ConnectionStatus("TikTok", "CSV import - implemented", "Developer app, user authorisation and approved scopes for account Display API; research access separately restricted"),
    ConnectionStatus("Restaurant / industry", "CSV import - implemented", "Licensed/public statistics and source metadata; no live menu-provider API in MVP"),
]
