Visitour - Navigate amongst SVG elements embeded in an HTML file.

Visitour is a Python3 script that extracts paths from an SVG file and embeds
them in an HTML file along with their associated names and some Javascript code.
The Javascript code enables the user to 'navigate' among the embedded SVG
elements by entering their associated name.

## Config Panel

There are three config options which control navigation.

  * __Connect__ - Navigation will only succeed if the name of the entered
  element is a 'neighbor' of the current element.

  * __Follow__ - Navitour will highlight an SVG element. The user must supply
  the name of the highlighted element.

  * __Hide__ - All SVG elements are hidden.

Additional config options.

  * __Show Counter__ - Show the number of visited SVG elements and the
  total number of SVG elements.

  * __Show Timer__ - Show a timer. The timer will start after the first name has
  been entered. The timer will stop after all SVG elements have been visited.

  * __Show Spot__ - Show a small circle, marking the current SVG element.

  * __Full Name__ - The full name of the SVG element must be entered before
  navigation will succeed. Normally, only enough of a name must be entered
  to uniquely identify it.

The config options are stored as a Cookie.

## Query Parameters

Config options are normally set via the config panel, but they can also be set
by specifying any of the following query parameters in the URL.

| Parameter | Description                                                  |
|-----------|--------------------------------------------------------------|
| connect   | Entered name must be a 'neighbor' of the current SVG element |
| counter   | Show counter                                                 |
| follow    | The name of the highlighted SVG element must be entered      |
| fullname  | Complete name must be entered                                |
| hide      | Hide SVG elements                                            |
| spot      | Show spot                                                    |
| timer     | Show timer                                                   |
| auto      | For debugging. Automatically enter names                     |
| debug     | For debugging. Show debug info                               |

All values are boolean. 'true', 'yes' or '1' evaluate to True; all other values
are False. Case is ignored.

e.g. `shapes.html?spot=1&timer=0`

Config values set via query parameters override the config values set via the
configuration panel.


## HTML Samples

Pre-generated HTML files may be downloaded and run in your browser:

  * [NATO Alphabet](nato-alphabet/nato-alphabet.html)
  * [US Map](us-map/us-map.html)
  * [World Map](world-map/world-map.html)

## Keys

When entering names, the following keys are recognized:

| Key   | Action                                                         |
|-------|----------------------------------------------------------------|
| =     | Toggle help                                                    |
| .     | Show names of neighbors                                        |
| ,     | Show completions for name (at least two chars must be entered) |
| /     | Toggle configuration panel                                     |
| Enter | Toggle zoom                                                    |

When entering a name, it is sometimes necessary to end the name with a space
in order to distinguish it from other names. This is only necessary when one
name is a substring of another name. (e.g. 'Niger' and 'Nigeria')

## Files

In order to generate an HTML file, Visitour requires an `.SVG` file and an `.AST` file.

#### SVG File

The`.SVG` must conform to a strict format. Both The `width` and `height`
attributes in the root `svg` element must be floats or integers; units
(e.g. `8.342in`) are not allowed. The `viewbox` attribute of the `svg` element
must be `0 0 [value of width] [value of height]`. Visitour will only extract
`path` elements. Extracted `path` elements must have an `id` (a.k.a. SvgId) and
a `d` property. All other elements (e.g. `ellipse`, `rect`, `text`, `defs`) are
ignored. Attributes like `transform` are also ignored. Paths should not overlap
because their visibility depends on the order they are drawn.

Each vector editor has their own way of creating such a file. In Inkscape: The
`viewbox` values can be set via `File` -> `Document Properties` -> `Viewbox`.
To convert all elements (e.g. `rect`) to `path` elements, select all elements,
then `Path` -> `Object to path`. To remove `transform` attributes, choose
`Edit` -> `Preferences` -> `Behavior` -> `Transforms` and ensure 'Optimized'
is selected, then select all objects and move them up, then move them back
down. Save the file.


#### AST File

The `.AST` file is nothing more than a (plaintext) Python dictionary containing
the following keys.

| Key      | Type                       |
|----------|----------------------------|
|svgname   | String                     |
|nodes     | List of NodeInfo           |
|extra     | List of SvgIds             |
|colors    | List of HTML Colors        |
|join      | List of NodeIdTuples       |
|snip      | List of NodeIdTuples       |
|svgcolors | Dictionary of class colors |


`svgname` - The name of the SVG file to read. If it is not specified, the name
will be generated by replacing the extension of the '.AST' file with '.svg'.

`nodes` - Specifies the NodeIds and the SvgIds to include in the generated HTML file.

        NodeInfo is a list of three required items.
          1. NodeId (string)
          2. Name of node (string)
          3. List of SvgIds (strings)

`extra` - Additional SvgIds to include in the generated HTML file. These
elements will be visible, but will not participate in navigation. Unlike
NodeIds (which have only their `id` and `d` attributes extracted), SvgIds all
their attributes extracted and embedded in the generated HTML file.)

`colors` - Specifies the colors to use to color the map. Visitour will try to
use as few colors as possible. If no colors are specified, default colors will
be used.

`join` - Specifies which NodeIds should be neighbors. This can be used to force
two NodeIds to be neighbors.

`snip` - Specifies which NodeIds should not be neighbors. This can be used to
force two NodeIds to not be neighbors.

`svgcolors` - Specifies class names and the fill-color to apply to the class.
This is typically used to specify colors for the `extra` SvgIds. (Note: Any
inline styles will override these colors.)

All keys are optional, but if no `nodes` are specified, the generated HTML file
will not contain any SVG elements.

A NodeIdTuple is a list containing exactly two NodeIds. (e.g. `[ 'id1', 'id2' ]`)

Visitour will automatically detect which NodeIds are neighbors, but its
detection method is not perfect. The 'join' and 'snip' keys can be used to
correct neighbor info. The neighbor relation is commutative, so when using
`join` and `snip`, the relation only needs to be specified once. i.e. No need
for both `[ 'id1', 'id2' ]` and `[ 'id2', 'id1' ]`.


## Sample Files

These files are taken from the `shapes` directory.

A sample `.SVG` file. If this is saved as `shapes.svg`, it can be used with the `.AST` file, below.

    <?xml version="1.0" encoding="UTF-8"?>
    <svg
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 210 175"
        height="175"
        width="210" >
        <path
            id="background"
            d="M 0,0 210,0 210,175 0,175 Z"
            style="fill:#bbbbbb"
            />
        <path
            id="triangle"
            d="M 182.80682,148.6959 131.36491,97.979117 199.08573,76.748629 Z"
            style="fill:#0000ff"
            />
        <path
            id="square"
            d="m 87.710665,110.71349 57.083035,0.0412 -0.0417,59.69552 -57.083043,-0.0412 z"
            style="fill:#ffff00"
            />
        <path
            id="star"
            d="M 51.946247,72.097215 34.141826,56.515243 11.77393,63.019687 20.442849,40.496624 7.6154172,20.259883 30.77752,21.921817 45.217629,2.9103615 50.863681,26.46061 72.615594,34.947601 52.942946,47.840512 Z"
            style="fill:#00ff00"
            />
        <path
            id="hexagon"
            d="m 79.752575,130.81759 -33.947397,4.16397 -20.421982,-28.66281 13.52542,-32.826817 33.947402,-4.16396 20.421977,28.662859 z"
            style="fill:#ff0000"
            />
        <path
            id="yangswirl"
            d="m 127.43331,7.5660141 a 28.289675,29.584394 0 0 0 -1.01929,59.1159329 14.144837,14.792196 0 0 1 1.01929,-29.530326 14.145426,14.792812 0 0 0 0,-29.5856069 z m -1.01929,59.1159329 a 14.144837,14.792196 0 0 0 1.01929,0.05298 28.289675,29.584394 0 0 1 -1.01929,-0.05298 z m 0.90981,-48.198032 a 3.7223251,3.8926828 0 0 1 3.72228,3.892682 3.7223251,3.8926828 0 0 1 -3.72228,3.892623 3.7223251,3.8926828 0 0 1 -3.72228,-3.892623 3.7223251,3.8926828 0 0 1 3.72228,-3.892682 z"
            style="fill:#ffffff"
            />
        <path
            id="yindot"
            d="m 131.0464,22.376832 a 3.7223252,3.892683 0 0 1 -3.72233,3.892682 3.7223252,3.892683 0 0 1 -3.72232,-3.892682 3.7223252,3.892683 0 0 1 3.72232,-3.892682 3.7223252,3.892683 0 0 1 3.72233,3.892682 z"
            />
        <path
            id="yinswirl"
            d="m 127.48239,7.542289 a 28.289675,29.584394 0 0 1 0.97209,0.052984 14.144842,14.792202 0 0 0 -0.97209,-0.052984 z m 0.97209,0.052984 a 14.144842,14.792202 0 0 1 -0.98153,29.532328 14.144838,14.792197 0 0 0 -0.01,29.583664 28.289675,29.584394 0 0 0 0.99097,-59.115992 z M 127.72777,48.5588 a 3.7223251,3.8926828 0 0 1 3.72228,3.892623 3.7223251,3.8926828 0 0 1 -3.72228,3.892623 3.7223251,3.8926828 0 0 1 -3.72228,-3.892623 3.7223251,3.8926828 0 0 1 3.72228,-3.892623 z"
            />
        <path
            id="yangdot"
            d="m 131.45004,52.346985 a 3.7223252,3.892683 0 0 1 -3.72233,3.892682 3.7223252,3.892683 0 0 1 -3.72232,-3.892682 3.7223252,3.892683 0 0 1 3.72232,-3.892681 3.7223252,3.892683 0 0 1 3.72233,3.892681 z"
            style="fill:#ffffff"
            />
    </svg>

A sample `.AST` file. If this is saved as `shapes.ast` it can be used with the
`.SVG` file, above.

    {
        'svgname': 'shapes.svg',
        'nodes': [
            [ 'yin',  'Yin',      [ 'yindot', 'yinswirl'   ]  ],
            [ 'yang', 'Yang',     [ 'yangdot', 'yangswirl' ]  ],
            [ 'star', 'Star',     [ 'star'     ]              ],
            [ 'tri',  'Triangle', [ 'triangle' ]              ],
            [ 'squ',  'Square',   [ 'square'   ]              ],
            [ 'hex',  'Hexagon',  [ 'hexagon'  ]              ],
        ],
        'colors': [ 'red', 'yellow' ],
        'extra': [ 'background' ],
        'join': [
            [ 'yin',  'yang' ],
            [ 'tri',  'yin'  ],
            [ 'yang', 'star' ],
        ],
    }


## Usage

Usage: `python3 visitour.py shapes.ast`

## Misc

Visitour computes the neighbors of a NodeId by comparing it to every other
NodeId. As the number of NodeIds increases, the time required to compute the
neighbors rises exponentially. This time can be dramatically reduced by
splitting the NodeIds into smaller groups, having Visitour compute the
neighbors of each group, and then re-joining. See `world-map/build.sh` for
an example of one way to accomplish this.

An alternate method would be to manually create a `.cache` file for the
neighbors which specifies that no NodeIds have any neighbors.
(e.g `{ 'id1': [], 'id2': [] }`) and then explicitly specify neighbors in the
`.AST` file with the 'join' key.

Computing neighbors and centers is time consuming, so once they are computed,
the results are cached in a `tmp` directory. If you make any modifications to
the SVG file, you should delete the `tmp` directory so that corrected values
can be recomputed. Alternatively, you can edit the cached data directly,
or selectively delete cached values; missing cached values will be recomputed.
