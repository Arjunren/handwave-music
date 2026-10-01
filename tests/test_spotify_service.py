from src.online.spotify_service import SpotifyService


def test_spotify_track_result_keeps_artist_and_spotify_link() -> None:
    result = SpotifyService._to_result(
        {
            "name": "Song",
            "artists": [{"name": "Artist One"}, {"name": "Artist Two"}],
            "external_urls": {"spotify": "https://open.spotify.com/track/123"},
        },
        "track",
    )
    assert result.name == "Song"
    assert result.subtitle == "Artist One, Artist Two"
    assert result.url == "https://open.spotify.com/track/123"
