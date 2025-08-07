from ytmusicapi import YTMusic

class YouTubeMusicClient:
    def __init__(self):
        self.ytmusic = YTMusic()

    def search_albums(self, query):
        """Searches for albums with the given query."""
        if not query:
            return []
        return self.ytmusic.search(query, filter="albums", limit=50)

    def get_album_details(self, browse_id):
        """Gets the details of an album by its browseId."""
        if not browse_id:
            return None
        return self.ytmusic.get_album(browseId=browse_id)
