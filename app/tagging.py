from pathlib import Path
import base64, mutagen
from mutagen.id3 import ID3, APIC, TALB, TPE1, TPE2, TIT2, TRCK, TDRC
from mutagen.flac import Picture
from mutagen.mp4 import MP4Cover

def tag_audio(
    file_path,
    tags=None,
    cover_path=None,   # JPEG or PNG
    make_v23=False     # For MP3: write ID3 v2.3 + v1
):
    """
    Generic tag-writer that works on MP3, FLAC, Ogg Vorbis/Opus, and MP4/M4A.

    file_path  : Path to the audio file
    tags       : Dictionary of tags to apply (optional)
    cover_path : Path to cover image (str or Path, optional)
    make_v23   : Write MP3 tags as ID3 v2.3 + v1 if True
    """
    audio = mutagen.File(file_path, easy=False)
    if audio is None:
        raise ValueError("Unsupported or corrupted file.")

    if tags is None:
        tags = {}

    # ── MP3 ──────────────────────────────────────────────────────────────
    if audio.mime[0] in ("audio/mpeg", "audio/mp3"):                     # Safer than isinstance
        if not isinstance(audio.tags, ID3):
            audio.add_tags()                              # Create ID3 if missing

        # Clear existing text tags before adding new ones
        for key in ['TIT2', 'TPE1', 'TALB', 'TPE2', 'TRCK', 'TDRC']:
            audio.tags.delall(key)

        if tags.get('title'): audio.tags.add(TIT2(encoding=3, text=tags['title']))
        if tags.get('artist'): audio.tags.add(TPE1(encoding=3, text=tags['artist']))
        if tags.get('album'): audio.tags.add(TALB(encoding=3, text=tags['album']))
        if tags.get('album_artist'): audio.tags.add(TPE2(encoding=3, text=tags['album_artist']))
        if tags.get('track_number'):
            track_text = str(tags['track_number'])
            audio.tags.add(TRCK(encoding=3, text=track_text))
        if tags.get('year'): audio.tags.add(TDRC(encoding=3, text=str(tags['year'])))

        if cover_path:
            audio.tags.delall("APIC")                     # Remove old artwork
            audio.tags.add(
                APIC(
                    encoding=3,                           # UTF-8
                    mime=_mime(cover_path),               # image/jpeg or image/png
                    type=3,                               # 3 = front cover
                    desc="Cover",
                    data=Path(cover_path).read_bytes()
                )
            )

        if make_v23:
            audio.update_to_v23()                         # Downgrade frames
            audio.save(v1=2, v2_version=3)                # Write v1+v2.3
        else:
            audio.save()

    # ── FLAC ─────────────────────────────────────────────────────────────
    elif audio.mime[0] == "audio/flac":
        # For FLAC, it's easier to clear and rewrite Vorbis comments
        audio.delete()
        if tags.get('title'): audio['title'] = tags['title']
        if tags.get('artist'): audio['artist'] = tags['artist']
        if tags.get('album'): audio['album'] = tags['album']
        if tags.get('album_artist'): audio['albumartist'] = tags['album_artist']
        if tags.get('track_number'): audio['tracknumber'] = str(tags['track_number'])
        if tags.get('year'): audio['date'] = str(tags['year'])

        if cover_path:
            audio.clear_pictures()                        # Remove existing art
            audio.add_picture(_flac_picture(cover_path))
        audio.save()

    # ── Ogg Vorbis / Opus ────────────────────────────────────────────────
    elif audio.mime[0] in ("audio/vorbis", "audio/opus", "audio/ogg"):
        # Also uses Vorbis comments
        audio.delete()
        if tags.get('title'): audio['title'] = tags['title']
        if tags.get('artist'): audio['artist'] = tags['artist']
        if tags.get('album'): audio['album'] = tags['album']
        if tags.get('album_artist'): audio['albumartist'] = tags['album_artist']
        if tags.get('track_number'): audio['tracknumber'] = str(tags['track_number'])
        if tags.get('year'): audio['date'] = str(tags['year'])

        if cover_path:
            encoded = base64.b64encode(
                _flac_picture(cover_path).write()
            ).decode("ascii")
            audio["metadata_block_picture"] = [encoded]   # Standard field
        audio.save()

    # ── MP4 / M4A ────────────────────────────────────────────────────────
    elif audio.mime[0] == "audio/mp4":
        audio.delete() # Clear existing tags
        if tags.get('title'): audio["\xa9nam"] = [tags['title']]
        if tags.get('artist'): audio["\xa9ART"] = [tags['artist']]
        if tags.get('album'): audio["\xa9alb"] = [tags['album']]
        if tags.get('album_artist'): audio["aART"] = [tags['album_artist']]
        if tags.get('track_number'):
            audio["trkn"] = [(int(tags['track_number']), 0)]
        if tags.get('year'): audio["\xa9day"] = [str(tags['year'])]

        if cover_path:
            img = Path(cover_path).read_bytes()
            audio["covr"] = [
                MP4Cover(img, imageformat=_mp4_format(cover_path))
            ]
        audio.save()

    else:
        raise NotImplementedError(
            f"MIME type {audio.mime[0]} is not handled."
        )

# ── Helper functions ────────────────────────────────────────────────────
def _mime(path):
    """Return proper MIME for a given image path."""
    return "image/png" if str(path).lower().endswith(".png") else "image/jpeg"

def _flac_picture(path):
    """Build a mutagen.flac.Picture object from an image file."""
    pic = Picture()
    pic.type = 3                                  # Front cover
    pic.mime = _mime(path)
    pic.desc = "Cover"
    pic.data = Path(path).read_bytes()
    return pic

def _mp4_format(path):
    """Return MP4Cover format constant matching file extension."""
    return (
        MP4Cover.FORMAT_PNG
        if str(path).lower().endswith(".png")
        else MP4Cover.FORMAT_JPEG
    )