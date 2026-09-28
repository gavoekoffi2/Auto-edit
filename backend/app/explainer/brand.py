"""Logo du client: détourage propre (jamais coupé) et encodage pour la page d'animation.

Règles apprises en production:
  * un logo n'est JAMAIS coupé: recadrage au contenu + marge, jamais de crop fixe;
  * fond uni (souvent blanc) → transparent par remplissage depuis les coins
    (les blancs INTERNES du logo restent intacts, contrairement à un seuil);
  * bord adouci d'1 px pour éviter l'escalier;
  * taille raisonnable (≤ 900 px de large) pour une page légère.
"""
from __future__ import annotations

import base64
import io
import logging
from collections import deque
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def _has_real_alpha(im) -> bool:
    if im.mode != "RGBA":
        return False
    a = im.getchannel("A")
    lo, hi = a.getextrema()
    return lo < 250


def detour(im, tol: int = 38):
    """Rend transparent le fond uni connecté aux 4 coins."""
    import numpy as np
    from PIL import Image, ImageFilter

    rgba = im.convert("RGBA")
    px = np.array(rgba).astype(int)
    h, w = px.shape[:2]
    corners = [px[0, 0, :3], px[0, w - 1, :3], px[h - 1, 0, :3], px[h - 1, w - 1, :3]]
    # fond uni seulement: les 4 coins doivent se ressembler
    if max(abs(corners[0] - c).sum() for c in corners[1:]) > tol * 1.5:
        return rgba
    bgc = corners[0]
    diff = np.abs(px[:, :, :3] - bgc).sum(axis=2) <= tol
    mask = np.zeros((h, w), bool)
    q = deque([(0, 0), (0, w - 1), (h - 1, 0), (h - 1, w - 1)])
    while q:
        y, x = q.popleft()
        if y < 0 or x < 0 or y >= h or x >= w or mask[y, x] or not diff[y, x]:
            continue
        mask[y, x] = True
        q.extend([(y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)])
    alpha = np.where(mask, 0, px[:, :, 3]).astype("uint8")
    al = Image.fromarray(alpha).filter(ImageFilter.GaussianBlur(0.8))
    rgba.putalpha(al)
    return rgba


def prepare_logo(path: Optional[str], max_w: int = 900) -> str:
    """Chemin d'image → data URL PNG détourée et rognée au contenu ('' si absent/illisible)."""
    if not path or not Path(path).exists():
        return ""
    try:
        from PIL import Image
        im = Image.open(path)
        im.load()
        if not _has_real_alpha(im):
            im = detour(im)
        else:
            im = im.convert("RGBA")
        bbox = im.getchannel("A").point(lambda v: 255 if v > 8 else 0).getbbox()
        if bbox:
            pad = max(4, int(0.02 * max(im.size)))
            x0, y0, x1, y1 = bbox
            im = im.crop((max(0, x0 - pad), max(0, y0 - pad), min(im.width, x1 + pad), min(im.height, y1 + pad)))
        if im.width > max_w:
            im = im.resize((max_w, round(im.height * max_w / im.width)), Image.LANCZOS)
        buf = io.BytesIO()
        im.save(buf, "PNG", optimize=True)
        return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
    except Exception as e:  # un logo illisible ne doit jamais bloquer le montage
        logger.warning("logo ignoré: %s", e)
        return ""
