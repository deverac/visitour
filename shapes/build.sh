#!/bin/bash

set -e

rm -f shapes.html
python3 ../visitour.py shapes.ast
