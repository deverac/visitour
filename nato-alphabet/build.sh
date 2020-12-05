#!/bin/bash
# nato-alphabet.svg was created in Inkscape (https://inkscape.org/)

set -e

rm -f nato-alphabet.html
python3 ../visitour.py nato-alphabet.ast
