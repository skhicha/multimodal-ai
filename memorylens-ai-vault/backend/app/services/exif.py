"""EXIF metadata extraction for photos (GPS, timestamp, camera model)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from PIL import Image
from PIL.ExifTags import GPSTAGS, TAGS


@dataclass
class ExifResult:
    camera_model: Optional[str] = None
    taken_at: Optional[str] = None
    gps_lat: Optional[float] = None
    gps_lon: Optional[float] = None
    width: Optional[int] = None
    height: Optional[int] = None


def _to_degrees(value) -> float:
    d, m, s = value
    return float(d) + float(m) / 60.0 + float(s) / 3600.0


def extract_exif(image_path: str) -> ExifResult:
    """Best-effort EXIF read. Never raises: missing/garbled EXIF just means
    fewer fields get filled in, which is normal for screenshots, downloaded
    images, or anything already stripped of metadata."""
    result = ExifResult()
    try:
        with Image.open(image_path) as img:
            result.width, result.height = img.size
            raw_exif = img.getexif()
            if not raw_exif:
                return result

            tags = {TAGS.get(k, k): v for k, v in raw_exif.items()}
            result.camera_model = tags.get("Model")
            if isinstance(result.camera_model, bytes):
                result.camera_model = result.camera_model.decode(errors="ignore")
            if result.camera_model:
                result.camera_model = result.camera_model.strip()

            date_str = tags.get("DateTimeOriginal") or tags.get("DateTime")
            if date_str:
                try:
                    if isinstance(date_str, bytes):
                        date_str = date_str.decode(errors="ignore")
                    dt = datetime.strptime(date_str, "%Y:%m:%d %H:%M:%S")
                    result.taken_at = dt.isoformat()
                except ValueError:
                    pass

            gps_ifd = raw_exif.get_ifd(0x8825) if hasattr(raw_exif, "get_ifd") else None
            if gps_ifd:
                gps = {GPSTAGS.get(k, k): v for k, v in gps_ifd.items()}
                lat = gps.get("GPSLatitude")
                lat_ref = gps.get("GPSLatitudeRef")
                lon = gps.get("GPSLongitude")
                lon_ref = gps.get("GPSLongitudeRef")
                if lat and lon and lat_ref and lon_ref:
                    lat_deg = _to_degrees(lat)
                    lon_deg = _to_degrees(lon)
                    if lat_ref in ("S", b"S"):
                        lat_deg = -lat_deg
                    if lon_ref in ("W", b"W"):
                        lon_deg = -lon_deg
                    result.gps_lat = lat_deg
                    result.gps_lon = lon_deg
    except Exception:
        # Corrupt/unsupported file: fall through with whatever was gathered.
        pass
    return result
