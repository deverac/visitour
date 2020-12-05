#!/bin/bash
# Source of world-map.svg: https://commons.wikimedia.org/wiki/File:BlankMap-World.svg

set -e

rm -f world-map.html
rm -f world-map.ast

if [ ! -f world-map.ast ]; then
    FILES='_world_africa.ast _world_asia.ast _world_europe.ast _world_isle.ast _world_namer.ast _world_samer.ast'
    for fil in $FILES
    do
        python3 ../visitour.py $fil    # Generate *_neighbors and *_centers (and *.html) files.
    done

    python3 merge-ast.py -c _connect.ast $FILES    # Generate world-map.ast
fi

python3 ../visitour.py world-map.ast
