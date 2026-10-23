"""Minimal, read-only Instagram Login connector. Tokens must stay server-side."""
import requests

API_ROOT = 'https://graph.instagram.com'

class InstagramError(Exception):
    pass

def get_instagram(path, token, fields, limit=None, session=None):
    if not token or not token.strip():
        raise InstagramError('No Instagram access token configured.')
    if not path.startswith('/me'):
        raise InstagramError('Only the authorised account endpoints are supported.')
    params = {'fields': fields}
    if limit is not None:
        params['limit'] = min(int(limit), 25)
    try:
        result = (session or requests).get(
            API_ROOT + path, headers={'Authorization': 'Bearer ' + token.strip()},
            params=params, timeout=18)
        result.raise_for_status()
        body = result.json()
    except requests.exceptions.RequestException as exc:
        status = getattr(getattr(exc, 'response', None), 'status_code', None)
        raise InstagramError('Meta API request failed' + (f' (HTTP {status})' if status else '') + '. Check account permissions and whether the token has expired.') from None
    except (ValueError, TypeError):
        raise InstagramError('Meta returned an unreadable response.') from None
    if not isinstance(body, dict) or 'error' in body:
        raise InstagramError('Meta rejected the request. Check the token and granted permissions.')
    return body


def profile(token, session=None):
    return get_instagram('/me', token, 'user_id,username,account_type', session=session)


def media(token, session=None):
    return get_instagram('/me/media', token, 'id,caption,media_type,permalink,timestamp,like_count,comments_count', limit=25, session=session).get('data', [])
