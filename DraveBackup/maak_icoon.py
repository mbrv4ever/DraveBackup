# -*- coding: utf-8 -*-
"""Maakt app.ico en logo.ico uit logo.png. Vereist Pillow (pip install pillow)."""
import os
import sys

try:
    from PIL import Image
except ImportError:
    print("Pillow ontbreekt. Installeer met: pip install pillow")
    sys.exit(1)

HIER = os.path.dirname(os.path.abspath(__file__))
bron = os.path.join(HIER, "logo.png")
if not os.path.exists(bron):
    print("logo.png niet gevonden naast dit script.")
    sys.exit(1)

img = Image.open(bron).convert("RGBA")
maten = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
for naam in ("app.ico", "logo.ico"):
    img.save(os.path.join(HIER, naam), sizes=maten)
    print("gemaakt:", naam)
print("Klaar.")
