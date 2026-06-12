"""HTTP media delivery helpers — range-aware file responses.

The pinned Starlette version ships a FileResponse WITHOUT HTTP Range support:
it always replies 200 with the full body. That breaks/slows real-world video
delivery — mobile browsers and download managers expect 206 partial content to
resume interrupted downloads and to seek inside previews. This helper serves
both cases:

  * no Range header  -> 200 + Accept-Ranges (resume supported)
  * Range: bytes=a-b -> 206 + Content-Range, streaming only that window
"""
from __future__ import annotations

import os
import re
from typing import AsyncIterator, Optional

import aiofiles
from fastapi import Request
from fastapi.responses import FileResponse, StreamingResponse

_RANGE_RE = re.compile(r"bytes=(\d*)-(\d*)$")
_CHUNK = 1024 * 1024  # 1 MB read window


def _parse_range(header: str, file_size: int) -> Optional[tuple[int, int]]:
    m = _RANGE_RE.match(header.strip())
    if not m:
        return None
    start_s, end_s = m.groups()
    if start_s == "" and end_s == "":
        return None
    if start_s == "":
        # suffix range: last N bytes
        length = int(end_s)
        if length <= 0:
            return None
        start = max(0, file_size - length)
        end = file_size - 1
    else:
        start = int(start_s)
        end = int(end_s) if end_s else file_size - 1
    if start >= file_size:
        return None
    return start, min(end, file_size - 1)


async def _file_window(path: str, start: int, end: int) -> AsyncIterator[bytes]:
    remaining = end - start + 1
    async with aiofiles.open(path, "rb") as fh:
        await fh.seek(start)
        while remaining > 0:
            chunk = await fh.read(min(_CHUNK, remaining))
            if not chunk:
                break
            remaining -= len(chunk)
            yield chunk


def ranged_file_response(
    path: str,
    request: Request,
    media_type: str = "video/mp4",
    filename: Optional[str] = None,
):
    """FileResponse drop-in that honours HTTP Range requests."""
    file_size = os.path.getsize(path)
    disposition = (
        {"Content-Disposition": f'attachment; filename="{filename}"'} if filename else {}
    )

    range_header = request.headers.get("range")
    byte_range = _parse_range(range_header, file_size) if range_header else None
    if byte_range is None:
        return FileResponse(
            path,
            media_type=media_type,
            filename=filename,
            headers={"Accept-Ranges": "bytes", "Cache-Control": "private, max-age=0"},
        )

    start, end = byte_range
    return StreamingResponse(
        _file_window(path, start, end),
        status_code=206,
        media_type=media_type,
        headers={
            "Accept-Ranges": "bytes",
            "Content-Range": f"bytes {start}-{end}/{file_size}",
            "Content-Length": str(end - start + 1),
            "Cache-Control": "private, max-age=0",
            **disposition,
        },
    )
