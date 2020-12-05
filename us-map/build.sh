#!/bin/bash
# Source of us-map.svg: https://commons.wikimedia.org/wiki/File:Blank_US_Map_(states_only).svg

set -e

rm -f us-map.html
python3 ../visitour.py us-map.ast
