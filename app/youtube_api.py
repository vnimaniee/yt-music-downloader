from ytmusicapi import YTMusic
from ytmusicapi.exceptions import YTMusicUserError

from .utils import get_system_locale

supported_lang = ['zh_TW', 'tr', 'hi', 'es', 'ar', 'de', 'fr', 'it', 'nl', 'ja', 'ur', 'ko', 'zh_CN', 'pt', 'en', 'ru']

def get_ytmusicapi_lang(language: str) -> str:

    if language in supported_lang:
        return language
    elif language.split('_')[0] in supported_lang:
        return language.split('_')[0]
    else:
        raise YTMusicUserError("Unsupported Language")

class YouTubeMusicClient:
    def __init__(self, language=get_ytmusicapi_lang(get_system_locale())):
        self.ytmusic = YTMusic(language=language)

    def set_language(self, language):
        self.ytmusic = YTMusic(language=language)

    def search_albums(self, query):
        """Searches for albums with the given query."""
        if not query:
            return []
        return self.ytmusic.search(query, filter="albums", limit=50)

    def get_album_details(self, browse_id):
        """Gets the details of an album by its browseId."""
        if not browse_id:
            return None
        try:
            return self.ytmusic.get_album(browseId=browse_id)
        except Exception as e:
            print(e)
            return None
