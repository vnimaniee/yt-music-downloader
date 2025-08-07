from pathlib import Path
import base64, mutagen
from mutagen.id3 import ID3, APIC
from mutagen.flac import Picture
from mutagen.mp4 import MP4Cover

def tag_audio(
    file_path,
    cover_path=None,   # JPEG or PNG
    make_v23=False     # For MP3: write ID3 v2.3 + v1
):
    """
    Generic tag-writer that works on MP3, FLAC, Ogg Vorbis/Opus, and MP4/M4A.

    file_path  : Path to the audio file
    cover_path : Path to cover image (str or Path, optional)
    make_v23   : Write MP3 tags as ID3 v2.3 + v1 if True
    """
    audio = mutagen.File(file_path, easy=False)
    if audio is None:
        raise ValueError("Unsupported or corrupted file.")

    # ── MP3 ──────────────────────────────────────────────────────────────
    if audio.mime[0] in ("audio/mpeg", "audio/mp3"):                     # Safer than isinstance
        if not isinstance(audio.tags, ID3):
            audio.add_tags()                              # Create ID3 if missing

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
        if cover_path:
            audio.clear_pictures()                        # Remove existing art
            audio.add_picture(_flac_picture(cover_path))
        audio.save()

    # ── Ogg Vorbis / Opus ────────────────────────────────────────────────
    elif audio.mime[0] in ("audio/vorbis", "audio/opus", "audio/ogg"):
        if cover_path:
            encoded = base64.b64encode(
                _flac_picture(cover_path).write()
            ).decode("ascii")
            audio["metadata_block_picture"] = [encoded]   # Standard field
        audio.save()

    # ── MP4 / M4A ────────────────────────────────────────────────────────
    elif audio.mime[0] == "audio/mp4":
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
