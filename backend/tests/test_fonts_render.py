"""Tests polices: résolution repo + preuve de rendu réel (libass fontsdir)."""
import os
import shutil
import subprocess

import pytest

from app.autoedit_engine import fonts

FONTS_DIR = os.path.join(
    os.path.dirname(os.path.abspath(fonts.__file__)), "assets", "fonts")

_FFMPEG = shutil.which("ffmpeg")


def test_repo_fonts_are_vendored_with_license():
    """Les polices des styles sont EMBARQUÉES (build reproductible) + licence."""
    expected = ["Anton-Regular.ttf", "Bangers-Regular.ttf",
                "BebasNeue-Regular.ttf", "Caveat-Variable.ttf",
                "Montserrat-Variable.ttf", "Poppins-SemiBold.ttf",
                "OFL-LICENSE.txt"]
    present = set(os.listdir(FONTS_DIR))
    for name in expected:
        assert name in present, f"{name} manquant dans assets/fonts"


def test_find_font_file_resolves_from_repo_assets():
    for family in ("Anton", "Poppins", "Caveat", "Montserrat"):
        path = fonts._find_font_file(family)
        assert path is not None, f"{family} introuvable"
        assert os.path.exists(path)


def test_load_font_renders_french_accents():
    """La police chargée doit couvrir les caractères accentués français."""
    from PIL import Image, ImageDraw
    for family in ("Poppins", "Caveat", "Anton"):
        font = fonts.load_font(family, 48)
        img = Image.new("RGB", (600, 80), "white")
        d = ImageDraw.Draw(img)
        d.text((5, 5), "Éléphant à l'œuvre — ça décède", font=font, fill="black")
        # au moins quelques pixels dessinés (le texte n'est pas vide/tofu blanc)
        assert img.convert("L").getextrema()[0] < 200


@pytest.mark.skipif(_FFMPEG is None, reason="ffmpeg absent")
def test_burned_subtitles_use_requested_font(tmp_path):
    """Preuve de rendu: la même phrase brûlée avec fontsdir (Caveat) diffère
    du fallback sans-serif — la police demandée est réellement utilisée."""
    ass = tmp_path / "t.ass"
    ass.write_text(
        "[Script Info]\nScriptType: v4.00+\nPlayResX: 480\nPlayResY: 270\n\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
        "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, "
        "ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, "
        "MarginL, MarginR, MarginV, Encoding\n"
        "Style: T,Caveat,64,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,"
        "0,0,0,0,100,100,0,0,1,2,0,5,10,10,10,1\n\n"
        "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, "
        "MarginV, Effect, Text\n"
        "Dialogue: 0,0:00:00.00,0:00:01.00,T,,0,0,0,,Vidéo décès française\n",
        encoding="utf-8")

    def _render(with_fontsdir: bool) -> bytes:
        out = tmp_path / f"o{int(with_fontsdir)}.png"
        vf = f"ass={ass}"
        if with_fontsdir:
            vf += f":fontsdir={FONTS_DIR}"
        subprocess.run(
            [_FFMPEG, "-y", "-v", "error", "-f", "lavfi",
             "-i", "color=c=black:s=480x270:d=1",
             "-vf", vf, "-frames:v", "1", str(out)],
            check=True, timeout=120)
        return out.read_bytes()

    with_font = _render(True)
    # Le rendu avec la police embarquée doit produire des pixels non vides.
    assert len(with_font) > 1000
    # Si Caveat n'est PAS installée système, les deux rendus doivent différer
    # (fontsdir = seule source de la police). Si elle l'est, ils sont égaux —
    # dans les deux cas la police est disponible pour libass.
    without_font = _render(False)
    caveat_system = subprocess.run(
        ["fc-list", ":family=Caveat"], capture_output=True, text=True
    ).stdout.strip() if shutil.which("fc-list") else ""
    if not caveat_system:
        assert with_font != without_font, (
            "fontsdir n'a pas d'effet: la police embarquée n'est pas utilisée")
