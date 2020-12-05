# This script reads an '.ast' file (which must be supplied as the only parameter),
# computes and caches the 'neighbors' and the 'centers' of each node element.
# It will then write an HTML file containing an embedded SVG file and
# Javascript code which can be used to navigate amongst the nodes in the SVG.

import xml.etree.ElementTree as ElementTree
from PIL import Image, ImageDraw
from cairosvg import svg2png
import io
import os
import ast
import math
import sys
import errno


# Options for debugging.
class Options:
    save_neighbor_png = False
    save_center_png = False



class Colors:
    RED = (255, 0, 0)
    BLACK = (0,0,0)
    WHITE = (255, 255, 255)



# A helper class for handling *.ast files.
class Astree:

    def __init__(self, name):
        self.name = name
        self._astdat = self._read(name)


    def _read(self, filename):
        dat = {}
        if os.path.isfile(filename):
            fil = open(filename, 'r')
            contents = fil.read()
            fil.close()
            if len(contents) > 0:
                dat = ast.literal_eval(contents)
        return dat

    def _astVal(self, key, default):
        if key in self._astdat:
            return self._astdat[key]
        return default

    def asDict(self):
        return self._astdat

    def getSvgname(self):
        return  self._astVal('svgname', [])

    def getNodes(self):
        return self._astVal('nodes', [])

    def getExtra(self):
        return self._astVal('extra', [])

    def getJoin(self):
        return self._astVal('join', [])

    def getSnip(self):
        return self._astVal('snip', [])

    def getColors(self):
        return self._astVal('colors', [])

    def getSvgcolors(self):
        return self._astVal('svgcolors', {})

    def write(self, dat):
        fil = open(self.name, 'w')
        fil.write(prettyPrint(dat))
        fil.close()



# Handle SVG data.
class Svg:

    def __init__(self, name, nodes):
        self._root = ElementTree.parse(name).getroot()
        self.width = float(self._root.attrib['width'])
        self.height = float(self._root.attrib['height'])
        self.dat = self._populateDat(nodes)


    def getId(self, id):
        return self._root.findall(".//*[@id='"+id+"']")


    def getDatVal(self, key):
        return self.dat[key]


    def getDatKeys(self):
        return self.dat.keys()


    def _extractPaths(self, pathIds):
        paths = []
        for pathId in pathIds:
            for child in self.getId(pathId):
                if 'd' in child.attrib:
                    paths.append({'pathId': pathId, 'd': child.attrib['d'] })
                else:
                    print('Missing data for path id '+ pathId)
        return paths


    def _populateDat(self, nodes):
        dct = {}
        for node in nodes:
            nodeId  = node[0]
            name    = node[1]
            pathIds = node[2]
            paths = self._extractPaths(pathIds)
            dct[nodeId] = { 'nodeId': nodeId, 'name': name, 'paths': paths }
        return dct



# A collection of methods for calculating nodes that are neighbors. The only
# method that should be called is 'compute()'; all the other methods are
# private, support methods.
class Neighbors:

    def __init__(self, tmpdir):
        self.stack = []
        self.changed = []
        self.tmpdir = tmpdir if tmpdir else 'tmp'


    def compute(self, svg, join, snip, pngPrefix):
        astree = Astree(self._neighborsCacheFilename(pngPrefix))
        cachedNeighbors = astree.asDict()

        nbors = self._computeNeighbors(svg, cachedNeighbors, pngPrefix)

        for tuple in join:
            self._addTransit(nbors, tuple[0], tuple[1])

        for tuple in snip:
            self._delTransit(nbors, tuple[0], tuple[1])

        astree.write(nbors)

        return nbors


    def _floodfill(self, pixels, wid, hgt):
        while self.stack:
            (x, y) = self.stack.pop()
            if pixels[x, y] == Colors.BLACK:
                pixels[x, y] = Colors.RED
                self.changed.append((x, y))
                # flood fill surrounding cells:
                if (x+1 < wid):
                    self.stack.append((x+1, y))
                if (x-1 >= 0):
                    self.stack.append((x-1, y))
                if (y+1 < hgt):
                    self.stack.append((x, y+1))
                if (y-1 >= 0):
                    self.stack.append((x, y-1))


    def _isVerticalLine(self, pixels, x, hgt):
        for y in range(0, hgt):
            if pixels[x, y] == Colors.WHITE:
                return False
        return True


    def _canDrawVerticalLine(self, pixels, wid, hgt):
        for x in range(0, wid):
            if self._isVerticalLine(pixels, x, hgt):
                return True
        return False


    def _isHorizontalLine(self, pixels, y, wid):
        for x in range(0, wid):
            if pixels[x, y] == Colors.WHITE:
                return False
        return True


    def _canDrawHorizontalLine(self, pixels, wid, hgt):
        for y in range(0, hgt):
            if self._isHorizontalLine(pixels, y, wid):
                return True
        return False


    def _canFloodFillTopToBottom(self, pixels, ww, hh):
        self.stack = []
        self.changed = []

        for w in range(0, ww):
           if pixels[w, 0] == Colors.BLACK:
               self.stack.append((w, 0))
               self._floodfill(pixels, ww, hh)
        # check
        for w in range(0, ww):
           if pixels[w, hh-1] == Colors.RED:
               return True
        return False


    def _canFloodFillLeftToRight(self, pixels, ww, hh):
        self.stack = []
        self.changed = []

        for h in range(0, hh):
            if pixels[0, h] == Colors.BLACK:
                self.stack.append((0, h))
                self._floodfill(pixels, ww, hh)
        # check
        for h in range(0, hh):
            if pixels[ww-1, h] == Colors.RED:
                return True
        return False


    def _resetChangedPixels(self, pixels):
        # Reset changed pixels (change RED to BLACK)
        while self.changed:
            (x, y) = self.changed.pop()
            pixels[x, y] = Colors.BLACK


    def _isSeparated(self, img):
        pixels = img.load()
        (ww, hh) = img.size

        # Use of canDrawHorizontalLine() and canDrawVerticalLine() are
        # optimizations that make detection about five times faster.
        # Use of self.changed is an optimization that keeps track of which
        # pixels were altered during floodfill so that they can be reverted.
        # None of the optimizations are actually required.

        if self._canDrawVerticalLine(pixels, ww, hh):
            return True

        if self._canDrawHorizontalLine(pixels, ww, hh):
            return True

        if self._canFloodFillTopToBottom(pixels, ww, hh):
            return True

        self._resetChangedPixels(pixels)

        if self._canFloodFillLeftToRight(pixels, ww, hh):
            return True

        return False


    def _generateNeighborsSvg(self, nodeA, nodeB, svgWidth, svgHeight):
        # Enlarging small SVG images gives more accurate results, but requires
        # more processing time.
        displayWidth = 1200.0 # Arbitrary
        if svgWidth > displayWidth:
            displayWidth = svgWidth

        scale = svgWidth / displayWidth
        scaledWid = svgWidth / scale
        scaledHgt = svgHeight / scale

        lines = []
        lines.append('<?xml version="1.0" encoding="UTF-8"?>')
        lines.append('<svg width="{}" height="{}" id="svgimg" viewBox="0 0  {} {}" xmlns="http://www.w3.org/2000/svg">'.format(scaledWid, scaledHgt, svgWidth, svgHeight))
        for node in [nodeA, nodeB]:
            lines.append('    <g id="g_{0}" class="g_{0}">'.format(node['nodeId']))
            for path in node['paths']:
                lines.append('        <path id="{}" stroke-width="1" stroke="white" fill="white" d="{}" />'.format(path['pathId'], path['d']))
            lines.append('    </g>')
        lines.append('</svg>\n')
        return '\n'.join(lines)


    def _neighborsPngFilename(self, nodeId1, nodeId2, prefix):
        return os.path.join(self.tmpdir, '{}_pair_{}_{}.png'.format(prefix, nodeId1, nodeId2))


    def _neighborsCacheFilename(self, pngPrefix):
        return os.path.join(self.tmpdir, '{}_neighbors.cache'.format(pngPrefix))


    def _areNeighbors(self, svg, nodeId1, nodeId2, pngPrefix):
        nodeA = svg.getDatVal(nodeId1)
        nodeB = svg.getDatVal(nodeId2)
        img = convertSvgToImg(self._generateNeighborsSvg(nodeA, nodeB, svg.width, svg.height))
        if Options.save_neighbor_png:
            img.save(self._neighborsPngFilename(nodeId1, nodeId2, pngPrefix))
        return not self._isSeparated(img)


    def _computeNeighbors(self, svg, cachedNeighbors, pngPrefix):
        neighbors = {}
        nids_todo = []
        nids_done = []
        sortedNodeIds = sorted(svg.dat.keys())
        togo = 0

        for nodeId in sortedNodeIds:
            if nodeId in cachedNeighbors:
                neighbors[nodeId] = cachedNeighbors[nodeId]
                nids_done.append(nodeId)
            else:
               nids_todo.append(nodeId)
               togo += len(sortedNodeIds) - len(nids_todo)

        nids_all = nids_todo + nids_done
        for i, nodeId1 in enumerate(nids_todo):
            for nodeId2 in nids_all[i+1:]:
                print('Checking {}  {}    {}'.format(nodeId1, nodeId2, togo))
                if (self._areNeighbors(svg, nodeId1, nodeId2, pngPrefix)):
                    print ('     neighbors')
                    self._addTransit(neighbors, nodeId1, nodeId2)
                togo -= 1

        for nodeId in sortedNodeIds:
           if nodeId not in neighbors:
               neighbors[nodeId] = []

        return neighbors

    # Make 'a' and 'b' neighbors.
    def _addTransit(self, nbors, a, b):
        if a not in nbors:
            nbors[a] = []
        if b not in nbors:
            nbors[b] = []

        if b not in nbors[a]:
            nbors[a].append(b)
        if a not in nbors[b]:
            nbors[b].append(a)


    # Sever the neighbor connection between 'a' and 'b'.
    def _delTransit(self, nbors, a, b):
        if a in nbors:
            if b in nbors[a]:
                nbors[a].remove(b)
        if b in nbors:
            if a in nbors[b]:
                nbors[b].remove(a)



# A collection of methods for calculating centers of nodes. The only
# method that should be called is 'compute()'; all the other methods are
# private, support methods.
class Centers:

    def __init__(self, tmpdir):
        self.tmpdir = tmpdir if tmpdir else 'tmp'


    def compute(self, svg, pngPrefix):
        astree = Astree(self._centersCacheFilename(pngPrefix))
        cachedCenters = astree.asDict()

        centers = self._computeCenters(svg, cachedCenters, pngPrefix)

        astree.write(centers)

        return centers


    def _computeCenters(self, svg, cachedCenters, pngPrefix):
        centers = {}
        togo = len(svg.dat.keys())

        for nodeId in sorted(svg.dat.keys()):
            if nodeId in cachedCenters:
                centers[nodeId] = cachedCenters[nodeId]
                continue
            print('Processing {}    {}'.format(nodeId, togo))
            node = svg.getDatVal(nodeId)

            img = convertSvgToImg(self._generateCenterSvg(node, svg.width, svg.height))

            (x_pct, y_pct) = self._computeCenterPercent(img)

            centers[nodeId] = { 'xc': x_pct,  'yc': y_pct }

            if Options.save_center_png:
                img.save(self._centersPngFilename(nodeId, pngPrefix))
            togo -= 1

        return centers;


    def _generateCenterSvg(self, node, wid, hgt):
        svgWidth = float(wid)
        svgHeight = float(hgt)

        # Enlarging small SVG images gives more accurate results, but requires
        # more processing time.
        displayWidth = 1200.0 # Arbitrary
        if svgWidth > displayWidth:
            displayWidth = svgWidth

        scale = svgWidth / displayWidth
        scaledWid = svgWidth / scale
        scaledHgt = svgHeight / scale

        lines = [];
        lines.append('<?xml version="1.0" encoding="UTF-8" ?>')
        lines.append('<svg width="{}" height="{}" viewBox="0 0  {} {}" xmlns="http://www.w3.org/2000/svg">'.format( scaledWid, scaledHgt, svgWidth, svgHeight ))
        lines.append('    <g>')
        for path in node['paths']:
            lines.append('        <path stroke-width="1" stroke="white" fill="white" d="{}" />'.format(path['d']))
        lines.append('    </g>')
        lines.append('</svg>')
        return '\n'.join(lines)


    def _markCenterPoint(self, img, x, y, rad):
        # Center
        img.putpixel((x, y), Colors.RED)

        # Make center point a bit larger
        img.putpixel((x+1, y  ), Colors.RED)
        img.putpixel((x-1, y  ), Colors.RED)
        img.putpixel((x,   y+1), Colors.RED)
        img.putpixel((x,   y-1), Colors.RED)

        # Mark points on surrounding 'circle'
        r = rad - 1
        p = int(r / math.sqrt(2))

        img.putpixel((x+r, y  ), Colors.RED)
        img.putpixel((x-r, y  ), Colors.RED)
        img.putpixel((x,   y+r), Colors.RED)
        img.putpixel((x,   y-r), Colors.RED)

        img.putpixel((x+p, y+p), Colors.RED)
        img.putpixel((x+p, y-p), Colors.RED)
        img.putpixel((x-p, y+p), Colors.RED)
        img.putpixel((x-p, y-p), Colors.RED)


    # Find the radius of the largest circle (more accurately an 8-pointed star)
    # where all points are white. This gives a cheap/fast approximation of the
    # 'center' of a shape. This can return 'bad' (but valid) results when the
    # shape is not solid (e.g. islands).
    def _circle(self, im, x0, y0, maxr):
        r = maxr


        while True:
            if r > x0 or r > y0 or (x0 + r) >= im.width or (y0 + r) >= im.height:
                r -= 1
                break

            p = int(r / math.sqrt(2))
            if (    im.getpixel( (x0+r, y0  ) ) == Colors.WHITE
                and im.getpixel( (x0-r, y0  ) ) == Colors.WHITE
                and im.getpixel( (x0,   y0+r) ) == Colors.WHITE
                and im.getpixel( (x0,   y0-r) ) == Colors.WHITE

                and im.getpixel( (x0+p, y0+p) ) == Colors.WHITE
                and im.getpixel( (x0+p, y0-p) ) == Colors.WHITE
                and im.getpixel( (x0-p, y0+p) ) == Colors.WHITE
                and im.getpixel( (x0-p, y0-p) ) == Colors.WHITE
                ):
                r += 1
            else:
                break
        return r

    # A simple check to help ensure the center point is not a 'bad' location.
    def _isSolidWhite(self, im, x0, y0, radius):
        for r in range(1, radius):
            if (   im.getpixel( (x0+r, y0  ) ) != Colors.WHITE
                or im.getpixel( (x0-r, y0  ) ) != Colors.WHITE
                or im.getpixel( (x0,   y0+r) ) != Colors.WHITE
                or im.getpixel( (x0,   y0-r) ) != Colors.WHITE
                ):
                return False
        return True

    # If img contains clumps/islands of white pixels, they may affect the
    # computed center point.
    def _computeCenterPercent(self, img):
        (wid, hgt) = img.size
        center_point = None
        max_radius = 1
        for x in range(0, wid):
            for y in range(0, hgt):
                if img.getpixel((x, y)) == Colors.WHITE:
                    radius = self._circle(img, x, y, max_radius)
                    if radius > max_radius and self._isSolidWhite(img, x, y, radius):
                        max_radius = radius
                        center_point = (x, y)
        if not center_point:
            print('No center point found. Using default')
            center_point = (int(wid/2), int(hgt/2))
        (ctr_x, ctr_y) = center_point
        self._markCenterPoint(img, ctr_x, ctr_y, max_radius)
        return ( ctr_x/wid, ctr_y/hgt )


    def _centersPngFilename(self, nodeId, prefix):
        return os.path.join(self.tmpdir, '{}_center_{}.png'.format(prefix, nodeId))


    def _centersCacheFilename(self, prefix):
        return os.path.join(self.tmpdir, '{}_centers.cache'.format(prefix))



class Tour:

    def __init__(self, astFilename, tmpdir='tmp'):
        self.name = self._basename(astFilename)
        self.ast = Astree(astFilename)
        self.svg = Svg(self._getSvgFilename(), self.ast.getNodes())

        self.tmpdir = tmpdir
        self.neighbors = None
        self.centers = None
        self._mkDir(tmpdir)


    def _getSvgFilename(self):
        val = self.ast.getSvgname()
        if val:
            return val
        return '{}.svg'.format(self.name)

    def _basename(self, nam):
        return os.path.splitext(nam)[0]


    def _mkDir(self, dirname):
        try:
            os.mkdir(dirname)
        except OSError as exc:
            if exc.errno == errno.EEXIST and os.path.isdir(self.tmpdir):
                pass
            else:
                raise


    def getNodeCount(self):
        return len(self.ast.getNodes())


    def getName(self):
        return self.name


    def generateSvg(self):
        lines = []
        lines.append('<svg width="{0}" height="{1}" id="svgimg" viewBox="0 0  {0} {1}" xmlns="http://www.w3.org/2000/svg">'.format(self.svg.width, self.svg.height))
        lines.extend(self._populateExtraSvgDat())
        for nodeId in self.svg.getDatKeys():
            node = self.svg.getDatVal(nodeId)
            lines.append('    <g id="g_{0}" class="g_{0}">'.format(node['nodeId']))
            lines.append('        <title>{}</title>'.format(node['name']))
            for path in node['paths']:
                lines.append('        <path id="{}" class="lander {}" d="{}" />'.format(path['pathId'], node['nodeId'], path['d']))
            lines.append('    </g>')
        lines.append('</svg>')
        return '\n'.join(lines)


    def _populateExtraSvgDat(self):
        lines = []

        for svgId in self.ast.getExtra():
            children = self.svg.getId(svgId)
            if len(children) == 1:
                child = children[0]
                ln = ['<path']
                for key in child.keys():
                    prop = '{}="{}"'.format(key, child.attrib[key])
                    ln.append(prop)
                ln.append('/>\n')
                lines.append(' '.join(ln))
            else:
                print('Element count for id was not 1 '+svgId)
        return lines


    def getNeighbors(self):
        if not self.neighbors:
            self.neighbors = Neighbors(self.tmpdir).compute(self.svg, self.ast.getJoin(), self.ast.getSnip(), self.name)
        return self.neighbors


    def getCenters(self):
        if not self.centers:
            self.centers = Centers(self.tmpdir).compute(self.svg, self.name)
        return self.centers


    def jsNameToNodeId(self):
        tmp = {}
        for nodeId, node in self.svg.dat.items():
            name = node['name'].lower()
            tmp[name] = 'g_{}'.format(nodeId)

        dct = {}
        for nm in sorted(tmp):
            dct[nm] = tmp[nm]
        return dct


    # A crude (arbitrary) approximation of how 'connected' a node is.
    def _countConnections(self, neighbors):
        nodeIds = neighbors.keys()

        connected = {}
        for nodeId in nodeIds:
            connected[nodeId] = 0

        for nodeId in nodeIds:
            nborIds = neighbors[nodeId]

            bag = []
            for nborId in nborIds:
                nids = neighbors[nborId]
                for nid in nids:
                    if nid not in bag:
                        bag.append(nid)
            connected[nodeId] = len(bag)

        return connected

    def _getAvailColor(self, nodeIds, painted):
        usedColors = []
        for nodeId in nodeIds:
            if nodeId in painted:
                usedColors.append(painted[nodeId])
        num = 0
        while True:
            if num not in usedColors:
                return num
            num += 1


    # A simple algorithm to compute the coloring of the map.
    # Although any 2-dimensional map can be colored with only four colors,
    # doing so requires hundreds of special cases. The SVG elements might not
    # even be connected in a 2-dimensional manner, so finding a perfect
    # 4-coloring would be impossible.
    def cssSvgColors(self):
        neighbors = self.getNeighbors()
        colorPool = self.ast.getColors()
        svgcolors = self.ast.getSvgcolors()

        if not colorPool:
            colorPool = [ '#fffd80', '#a2ff9a', '#e9b1fd', '#ffaba6', '#b0c0ff', '#20ffe3' ]
        poolLen = len(colorPool)
        lines = []

        painted = {}
        counts = self._countConnections(neighbors)

        maxcolr = 0
        for nodeId in sorted(counts, key=lambda x: counts[x], reverse=True):
            if nodeId in svgcolors:
                continue
            if nodeId not in painted:
                colr = self._getAvailColor(neighbors[nodeId], painted)
                if colr > maxcolr:
                    maxcolr = colr
                painted[nodeId] = colr
                lines.append('  .'+nodeId+' { fill: '+colorPool[colr % poolLen]+' }')

        for nodeId in svgcolors:
            lines.append('  .'+nodeId+' { fill: '+svgcolors[nodeId]+' }')

        return '\n'.join(sorted(lines))


# Accepts SVG as string, returns an Image.
# The SVG is converted to a PNG, the PNG is cropped as closely as possible
# (i.e. as much of the background is removed as possible), and then converted
# to a black-and-white image that has an RGB color-space.
def convertSvgToImg(svgstr):
    output = svg2png(bytestring=svgstr.encode('utf-8'))
    im = Image.open(io.BytesIO(output))
    im2 = im.crop(im.getbbox())
    im3 = im2.convert('1') # Convert to black and white, so background is black, not transparent
    im4 = im3.convert("RGB")
    return im4



# A crude pretty-printer.
def prettyPrint(obj, ind=2):
    lines = []
    if isinstance(obj, list):
        return str(sorted(obj))
    elif isinstance(obj, dict):
        lines.append('{')
        for (k, v) in sorted(obj.items()):
            if isinstance(v, dict):
                val = prettyPrint(v, ind+2)
            elif isinstance(v, list):
                val = sorted(v)
            elif isinstance(v, str):
                val = "'{}'".format(v)
            else:
                val = v
            lines.append("{}'{}': {},".format(' '*ind, k, val))
        lines.append('{}{}'.format(' '*(ind-2), '}'))
    return '\n'.join(lines);



def cssHtmlStyles():
    return """
    body {
        margin: 0;
        padding:0;
        background: lightgray;
        font-family: sans-serif;
    }
    .lander {
        fill: #c0c0c0;
        stroke: #000000;
        stroke-width: 0.3;
        fill-rule: evenodd;
    }
    div span {
        font-size: 14pt;
    }
    #startBox {
        border: solid red 1px;
        position: absolute;
        z-index: 3;
        pointer-events: none;
        visibility: hidden;
    }
    #endBox {
        border: solid green 1px;
        position: absolute;
        z-index: 3;
        pointer-events: none;
        visibility: hidden;
    }
    #spotty {
        position: absolute;
        width: 10px;
        height: 10px;
        border-radius: 50%;
        transform: translate(-50%, -50%);
        background-color: black;
        z-index: 4;
        pointer-events: none;
        display: none;
    }
    #mapdisplay {
        width: 100%;
        margin-top: 25px;
        text-align: center;
    }
    #svgimg {
        width: 98%;
        height: auto;
        margin: auto auto;
    }
    #intext {
        font-size: 24pt;
        text-align: center;
    }
    #userpanel {
        text-align: center;
    }
    #counter {
        position: absolute;
        top: 0;
        left: 0;
    }
    #timer {
        position: absolute;
        top: 0;
        right: 0;
    }
    .stat {
        margin: 20px;
        font-size: 18pt;
        background-color: darkgray;
        color: black;
        display: inline-block;
        border-radius: 5px;
        padding: 3px;
        border: solid black 1px;
    }
    .lander.visited {
        fill: lightgray;
    }
    .lander.nextcc {
        fill: black;
    }
    .panel {
        position: absolute;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%);
        background-color: darkgray;
        z-index: 5;
        border-radius: 20px;
        border: solid black 5px;
        padding: 20px;
        display: none;
    }
"""

def jsCode():
    return """
class Storage {

    readConfig() {
        try {
            return JSON.parse(localStorage.getItem('config'));
        } catch (err) {
            return {};
        }
    }

    saveConfig(cfg) {
        localStorage.setItem('config', JSON.stringify(cfg));
    }
}

class DOM {

    constructor() {
        this.isConfigPanelShowing = false;
        this.isHelpPanelShowing = false;
        this.isCompletedPanelShowing = false;
    }

    _getTimer() {
        return document.querySelector('#timer');
    }

    hideTimer() {
        this._getTimer().style.visibility = 'hidden';
    }

    showTimer() {
        this._getTimer().style.visibility = 'visible';
    }

    setTimerText(txt) {
        var elem = this._getTimer();
        if (elem) {
            elem.innerText = txt;
        }
    }

    setCompletedHtml(html) {
        var elem = this._getCompletedText();
        if (elem) {
            elem.innerHTML = html;
        }
    }


    _getCounter() {
        return document.querySelector('#counter');
    }

    hideCounter() {
        this._getCounter().style.visibility = 'hidden';
    }

    showCounter() {
        this._getCounter().style.visibility = 'visible';
    }

    updateCounter(txt) {
        var ele = this._getCounter();
        if (ele) {
            ele.innerText = txt;
        }
    }

    _getConfigPanel() {
        return document.querySelector('#configpanel');
    }

    openConfigPanel(cfg) {
        if (this.isHelpPanelShowing || this.isCompletedPanelShowing) {
            return;
        }
        this.isConfigPanelShowing = this._openPanel(this._getConfigPanel());
    }

    _getConfigPanelSettings() {
        return {
            connect:   document.querySelector('#cfgconnect').checked,
            follow:    document.querySelector('#cfgfollow').checked,
            hidden:    document.querySelector('#cfghidden').checked,
            counter:   document.querySelector('#cfgcounter').checked,
            timer:     document.querySelector('#cfgtimer').checked,
            spot:      document.querySelector('#cfgspot').checked,
            fullname:  document.querySelector('#cfgfullname').checked,
        };
    }

    closeConfigPanel() {
        var cfg = this._getConfigPanelSettings();
        this.isConfigPanelShowing = this._closePanel(this._getConfigPanel());
        return cfg;
    }

    _getSuggestElement() {
        return document.querySelector('#suggest');
    }

    showSuggestText(val) {
        var suggest = this._getSuggestElement();
        if (suggest) {
            suggest.innerText = val;
        }
    }

    _getHelpPanel() {
        return document.querySelector('#helppanel');
    }

    _getCompletedPanel() {
        return document.querySelector('#completedpanel');
    }

    _getCompletedText() {
        return document.querySelector('#completedtext');
    }

    _openPanel(elem) {
        if (elem) {
            elem.style.display = 'block';
            return true;
        }
        return false;
    }

    _closePanel(elem) {
        // Returns value indicates showing/hidden, not success/error.
        if (elem) {
            elem.style.display = 'none';
            return false;
        }
        return true;
    }

    openHelpPanel() {
        if (this.isConfigPanelShowing || this.isCompletedPanelShowing) {
            return;
        }
        this.isHelpPanelShowing = this._openPanel(this._getHelpPanel());
    }

    closeHelpPanel() {
        this.isHelpPanelShowing = this._closePanel(this._getHelpPanel());
    }

    toggleHelpPanel() {
        if (this.isHelpPanelShowing) {
            this.closeHelpPanel();
        } else {
            this.openHelpPanel();
        }
    }

    openCompletedPanel() {
        if (this.isHelpPanelShowing || this.isConfigPanelShowing) {
            return;
        }
        this.isCompletedPanelShowing = this._openPanel(this._getCompletedPanel());
    }

    closeCompletedPanel() {
        this.isCompletedPanelShowing = this._closePanel(this._getCompletedPanel());
    }

    _getInText() {
        return document.querySelector('#intext');
    }

    getUserInput() {
        var elem = this._getInText();
        if (elem) {
            return elem.value;
        }
        return '';
    }

    clearUserInput() {
        var elem = this._getInText();
        if (elem) {
            elem.value = '';
            this.userInputFocus();
        }
    }

    userInputFocus() {
        var elem = this._getInText();
        if (elem) {
            elem.focus();
        }
    }

    clearAllVisited() {
        this.removeClass('visited');
    }

    setVisited(cc) {
        this.addClass(cc, 'visited');
    }

    clearAllHighlight() {
        this.removeClass('nextcc');
    }

    setHighlight(cc) {
        this.addClass(cc, 'nextcc');
    }

    _getId(id) {
        return document.querySelector('#'+id);
    }

    hide(gcc) {
        var elem = this._getId(gcc);
        if (elem) {
            elem.style.visibility = 'hidden';
        }
    }

    hideAll(cc_ids) {
        for (let n in cc_ids) {
            var elem = this._getId('g_'+cc_ids[n]);
            if (elem) {
                elem.style.visibility = 'hidden';
            }
        }
    }

    unhide(gcc) {
        var elem = this._getId(gcc);
        if (elem) {
            elem.style.visibility = 'visible';
        }
    }

    unhideAll(cc_ids) {
        for (let n in cc_ids) {
            var elem = this._getId('g_'+cc_ids[n]);
            if (elem) {
                elem.style.visibility = 'visible';
            }
        }
    }

    removeClass(cls) {
        var elems = document.getElementsByClassName(cls);
        for (let i = elems.length-1; i >= 0; i--) {
            elems[i].classList.remove(cls);
        }
    }

    addClass(cc, cls) {
        var elems = document.getElementsByClassName(cc);
        for (let i = 0; i < elems.length; i++) {
            elems[i].classList.add(cls);
        }
    }

    _getSpot() {
        return document.querySelector('#spotty');
    }

    showSpot(left, top) {
        if (left >= 0 && top >= 0) {
            var spot = this._getSpot();
            spot.style.left = left;
            spot.style.top  = top;
            spot.style.display = 'block';
        }
    }

    hideSpot() {
        var spot = this._getSpot();
        spot.style.display = 'none';
    }

    _getIntext() {
        return this._getId('intext');
    }

    setTextOk() {
        var elem = this._getIntext();
        if (elem) {
            elem.style.backgroundColor = 'lightgreen';
        }
    }

    setTextBad() {
        var elem = this._getIntext();
        if (elem) {
            elem.style.backgroundColor = 'lightsalmon';
        }
    }

    setHelpKeys(keys) {
        var elem;
        elem = document.querySelector('#helpKeyComplete');
        if (elem) {
            elem.innerText = keys.COMPLETE;
        }
        elem = document.querySelector('#helpKeyConfig');
        if (elem) {
            elem.innerText = keys.CONFIG;
        }
        elem = document.querySelector('#helpKeyEnter');
        if (elem) {
            elem.innerText = keys.ENTER;
        }
        elem = document.querySelector('#helpKeyHelp');
        if (elem) {
            elem.innerText = keys.HELP;
        }
        elem = document.querySelector('#helpKeyNeighbor');
        if (elem) {
            elem.innerText = keys.NEIGHBORS;
        }
    }

}

var KEY = {
    COMPLETE: ',',
    CONFIG: '/',
    ENTER: 'Enter',
    HELP: '=',
    NEIGHBORS: '.',
};

var helpText = "Press '" + KEY.HELP + "' to show help.";

var config = null;
var timer = null;
var current_gcc = null;
var target_gcc = null;
var nextcc = null;

var num_incorrect = 0;
var num_correct = 0;

var isZoomedOut = true;
var isComplete = false;

var start_date = null;
var duration = 0;

var revit_keys = Object.keys(revit);
var gcc_to_name = {};
var visited = {};
var directed_graph = [];

var dom = new DOM();
var storage = new Storage();


function getSvgDims() {
    var svgimg = document.querySelector('#svgimg');
    return {
        'width': svgimg.getAttribute('width'),
        'height': svgimg.getAttribute('height'),
    };
}

function getSvgRect() {
    var svgimg = document.querySelector('#svgimg');
    return svgimg.getBoundingClientRect(); // Actual pixel size in browser
};

function getViewbox() {
    var svgimg = document.querySelector('#svgimg');
    var vbAry = svgimg.getAttribute('viewBox').split(/ +/g);
    var x = parseFloat(vbAry[0]);
    var y = parseFloat(vbAry[1]);
    var width = parseFloat(vbAry[2]);
    var height = parseFloat(vbAry[3]);
    return {'x': x, 'y': y, 'width': width, 'height': height };
}

function setViewbox(x, y, w, h) {
    var svgimg = document.querySelector('#svgimg');
    svgimg.setAttribute('viewBox', x + ' ' + y + ' '+ w + ' ' + h);
}

function getBoundingBoxOfElement(gcc) {
    var ele = document.getElementById(gcc);
    if (ele) {
        return ele.getBBox();
    }
    return { 'x': 0, 'y': 0, 'width': 0, 'height': 0 };
}

function closeHelp() {
    dom.closeHelpPanel();
    dom.userInputFocus();
}

function closeCompleted() {
    dom.closeCompletedPanel();
    dom.userInputFocus();
}

function restart() {
    location.reload()
}

function closeConfig() {
    var cfg = dom.closeConfigPanel();
    var connectedChanged = cfg.connect != config.connect;
    var followChanged    = cfg.follow  != config.follow;
    var hiddenChanged    = cfg.hidden  != config.hidden;

    config.counter   = cfg.counter;
    config.timer     = cfg.timer;
    config.spot      = cfg.spot;
    config.fullname  = cfg.fullname;
    config.connect   = cfg.connect;
    config.follow    = cfg.follow;
    config.hidden    = cfg.hidden;

    storage.saveConfig(config);
    if (connectedChanged || followChanged || hiddenChanged) {
        restart();
    }
    dom.userInputFocus();
}

function openConfig() {
    dom.openConfigPanel(config);
}

function drawSpot() {
    if (target_gcc) {
        var box = computeStartBox();

        var c2 = target_gcc.substring(2)
        var xcm = centers[c2]['xc'];
        var ycm = centers[c2]['yc'];

        var left = box.x + (box.width * xcm);
        var top  = box.y + (box.height * ycm);
        dom.showSpot(left, top)
    }
}

function drawStartBox() {
    var box = computeStartBox();
    var startbox = document.querySelector('#startBox');
    startbox.style.visibility = (config.debug ? 'visible' : 'hidden');
    startbox.style.left   = box.x;
    startbox.style.top    = box.y;
    startbox.style.width  = box.width;
    startbox.style.height = box.height;
}

function computeStartBox() {
    var svgRect = getSvgRect();
    var vb = getViewbox();
    var svgScale = svgRect.width / (vb.width );
    var n = getBoundingBoxOfElement(target_gcc);
    return {
        'x': svgRect.x + ((n.x - vb.x) * svgScale),
        'y': svgRect.y + ((n.y - vb.y) * svgScale),
        'width': n.width * svgScale,
        'height': n.height * svgScale,
    }
}

function drawEndBox() {
    var box = computeEndBox();
    var endbox = document.querySelector('#endBox');
    endbox.style.visibility = (config.debug ? 'visible' : 'hidden');
    endbox.style.left   = box.x;
    endbox.style.top    = box.y;
    endbox.style.width  = box.width;
    endbox.style.height = box.height;
}

function computeEndBox() {
    target_scale = 1.6;
    var svgRect = getSvgRect();
    var n = getBoundingBoxOfElement(target_gcc);

    return {
        'x': svgRect.x + (svgRect.width - (n.width * target_scale)) / 2,
        'y': svgRect.y + (svgRect.height - (n.height * target_scale)) / 2,
        'width': n.width * target_scale,
        'height': n.height * target_scale,
    }
}

function transitionTo() {
    var vbox = getViewbox();

    var newX = vbox.x;
    var newY = vbox.y;
    var newWidth = vbox.width;
    var newHeight = vbox.height;

    if (isZoomedOut) {

        if (Math.abs(newX) < 1) {
        } else if (newX > 0) {
            newX -= newX * 0.1;
            if (newX < 0) newX = 0;
        } else if (newX < 0) {
            newX -= newX * 0.1;
            if (newX > 0) newX = 0;
        }

        if (Math.abs(newY) < 1) {
        } else if (newY > 0) {
            newY -= newY * 0.1;
            if (newY < 0) ny = 0;
        } else if (newY < 0) {
            newY -= newY * 0.1;
            if (newY > 0) newY = 0;
        }
        var dims = getSvgDims();
        if (newWidth < dims.width) {
            newWidth += (dims.width - newWidth) * 0.1
        }
        if (newWidth > dims.width) {
            newWidth = dims.width;
        }
        if (newHeight < dims.height) {
            newHeight += (dims.height - newHeight) * 0.1
        }
        if (newHeight > dims.height) {
            newHeight = dims.height;
        }
    } else {
        var svgRect = getSvgRect();

        var sbox = computeStartBox();
        var ebox = computeEndBox();
        var bbox = getBoundingBoxOfElement(target_gcc);

        var srcX = vbox.x;
        var srcY = vbox.y;
        var srcWidth = vbox.width;
        var srcHeight = vbox.height;

        var diffScale = ebox.width / sbox.width;
        var tgtWidth = vbox.width / diffScale;
        var tgtHeight = vbox.height / diffScale;
        var tgtX = (bbox.x - tgtWidth/2  + bbox.width/2);
        var tgtY = (bbox.y - tgtHeight/2  + bbox.height/2);

        newWidth = srcWidth + (tgtWidth - srcWidth) * 0.1;
        newHeight = srcHeight + (tgtHeight - srcHeight) * 0.1;
        newX = srcX + (tgtX - srcX) * 0.1;
        newY = srcY + (tgtY - srcY) * 0.1;
    }
    setViewbox(newX, newY, newWidth, newHeight);
    if (config.debug) {
        drawStartBox();
        drawEndBox();
    }
    if (config.spot) {
        drawSpot();
    }
    if (! isComplete) {
        updateTimer();
    }
    timer = setTimeout(transitionTo, 50);
}


function boxit(gcc) {
    target_gcc = gcc;
    timer = setTimeout(transitionTo, 1);
}

function findMatches(val) {
    var lowerVal = val.toLowerCase();
    var exact = lowerVal.endsWith(' ') || config.fullname;
    lowerVal = lowerVal.trim();
    var matches = [];
    for (k in revit_keys) {
        if (exact && revit_keys[k] == lowerVal ) {
            matches.push(revit_keys[k]);
            break;
        } else if (revit_keys[k].startsWith(lowerVal) && ! exact) {
            matches.push(revit_keys[k]);
        }
    }
    return matches;
}

function isNeighbor(cur, tgt, isGroupIds) {
    if (cur == null) {
        return true;
    }
    if (isGroupIds) {
        // Remove 'g_' prefix from cur and tgt.
        return neighbors[cur.substring(2)].includes(tgt.substring(2));
    }
    return neighbors[cur].includes(tgt);
}

function handleTimerChange(ele) {
    if (ele.checked) {
        dom.showTimer();
    } else {
        dom.hideTimer();
    }
}

function handleSpotChange(ele) {
    config.spot = ele.checked
    if (ele.checked) {
        dom.showSpot(-1, -1);
    } else {
        dom.hideSpot();
    }
}

function handleHiddenChange(ele) {
    config.hidden = ele.checked;
    var keys = Object.keys(neighbors);
    if (ele.checked) {
        dom.hideAll(keys);
    } else {
        dom.unhideAll(keys);
    }
}

function handleCounterChange(ele) {
    if (ele.checked) {
        dom.showCounter();
    } else {
        dom.hideCounter();
    }
}

function handleKeyDown(evt) {
    var name = evt.key;
    if (name == KEY.ENTER) {
        var txt = dom.getUserInput();
        if (txt == '') {
            isZoomedOut = ! isZoomedOut;
            return;
        }

        var mat = findMatches(txt);
        if (mat.length == 1) {
            var moveToNext = false;
            // clearTimeout(timer);
            var gcc = revit[mat[0]];

            if (config.connect) {

                if (isNeighbor(current_gcc, gcc, true)) {
                    if (config.follow) {
                        if (nextcc == gcc.substring(2)) {
                            moveToNext = true;
                        }
                    } else {
                        moveToNext = true;
                    }
                }

            } else {

                if (config.follow) {
                    if (gcc.substring(2) == nextcc) {
                        moveToNext = true;
                    }
                } else {
                    moveToNext = true;
                }

            }
            if (moveToNext) {
                clearTimeout(timer);
                current_gcc = gcc;
                setAaVisited(gcc);
                num_correct++;

                dom.updateCounter(countVisitedCountries() + '/' + countTotalCountries());
                if (countVisitedCountries() == countTotalCountries()) {
                    if (! isComplete) {
                        var pct = (1 - num_incorrect/num_correct) * 100;
                        dom.setCompletedHtml('Incorrect: ' + num_incorrect + '<br>Correct: ' + num_correct + '<br>Ratio: ' + pct.toFixed(2) + '%<br>');
                        dom.openCompletedPanel();
                    }
                    dom.hideSpot();
                    isComplete = true;
                }

                if (config.follow) {
                    dom.clearAllHighlight(gcc.substring(2))
                    if (config.hidden) {
                        dom.hide(gcc);
                    }
                    nextcc = directed_graph.shift();
                    if (nextcc) {
                        if (config.hidden) {
                            dom.unhide('g_'+nextcc);
                        }
                        dom.setHighlight(nextcc);
                        boxit('g_'+nextcc);
                    }
                } else {
                    boxit(gcc);
                }
                dom.setTextOk();
                dom.clearUserInput();
                dom.userInputFocus();
            } else {
                dom.setTextBad();
                num_incorrect++;
            }
        } else {
            num_incorrect++;
            dom.setTextBad();
        }
        dom.showSuggestText(helpText);
    } else if (name == KEY.COMPLETE) {
        evt.preventDefault();
        showCompletions();
    } else if (name == KEY.NEIGHBORS) {
        evt.preventDefault();
        showNeighbors();
    } else if (name == KEY.CONFIG) {
        evt.preventDefault();
        if (dom.isConfigPanelShowing) {
            closeConfig();
        } else {
            openConfig();
        }
    } else if (name == KEY.HELP) {
        evt.preventDefault();
        dom.toggleHelpPanel();
    } else {
        dom.setTextOk();
        dom.showSuggestText(helpText);
    }
}


function setAaVisited(gNodeId) {
    var nodeId = gNodeId.substring(2);
    visited[nodeId] = 1;
    dom.setVisited(nodeId);
}

function isVisited(nodeId) {
    return visited[nodeId] == 1;
}

function countVisitedCountries() {
    var count = 0;
    for (nodeId in visited) {
        if (isVisited(nodeId)) {
            count++;
        }
    }
    return count;
}

function countTotalCountries() {
    return Object.keys(visited).length;
}


function zpad(n) {
    return (n < 10) ? '0' + n : n;
}

function updateTimer() {
    if (start_date) {
        var duration_secs = parseInt((Date.now() - start_date) / 1000);
        if (duration_secs != duration) {
            var seconds = Math.floor((duration_secs ) % 60);
            var minutes = Math.floor((duration_secs / ( 60)) % 60);
            var hours = Math.floor((duration_secs / ( 60 * 60)));

            duration = duration_secs;

            var txt = minutes;
            if (hours > 0) {
                txt = hours + ':' + zpad(minutes);
            }
            dom.setTimerText(txt + ':' + zpad(seconds));
        }
    } else {
        start_date = Date.now();
    }
}

function showNeighbors() {
    if (current_gcc) {
        var nbrs = neighbors[current_gcc.substring(2)];
        var names = [];
        for (let i=0; i<nbrs.length; i++) {
            names.push(gcc_to_name['g_'+nbrs[i]]);
        }
        dom.showSuggestText(names.join(', '));
    }
}

function showCompletions() {
    var val = dom.getUserInput();
    var v = val.trim();
    if (v.length > 1) {
        var mat = findMatches(v);
        dom.showSuggestText(mat.join(', '));
    }
}

function construct_gcc_to_name() {
    for (let key in revit) {
        var val = revit[key];
        gcc_to_name[val] = key;
    }
}

function construct_visited() {
    for (let key in neighbors) {
        visited[key] = 0;
    }
}

function shuffle_array(ary) {
    var j, tmp;
    var shuf = [];
    for (let i = 0; i < ary.length; i++) {
        shuf[i] = ary[i];
    }

    for (let i = shuf.length - 1; i > 0; i--) {
        j = Math.floor(Math.random() * (i + 1));
        tmp = shuf[i];
        shuf[i] = shuf[j];
        shuf[j] = tmp;
    }
    return shuf;
}

function construct_directed_graph() {
    var stack = [];
    var path = [];
    var vst = {};
    var nbrs = {};

    for (let key in neighbors) {
        vst[key] = 0;
    }

    for (let key in neighbors) {
        nbrs[key] = shuffle_array(neighbors[key]);
    }

    var neighborIds = Object.keys(nbrs);
    var neighborId = neighborIds[Math.floor(Math.random() * neighborIds.length)];

    vst[neighborId] = 0;
    stack.push(neighborId);
    path.push(neighborId);
    while (stack.length) {
        var cd = stack[stack.length - 1];
        var opts = nbrs[cd];
        var n = vst[cd];
        if (n >= opts.length) { // all visited
            stack.pop();
            if (stack.length) {
                path.push(stack[stack.length - 1]);
            }
            continue;
        } else {
            var newcd = opts[n];
            if (vst[newcd] == 0) { // not visited
                path.push(newcd);
                stack.push(newcd);
            }
            vst[cd]++;
        }
    }

    directed_graph = path;
}

function construct_random_graph() {
    directed_graph = shuffle_array(Object.keys(neighbors));
}

function start() {
    dom.setTextOk();
    dom.clearUserInput();
    dom.showSuggestText(helpText);
    dom.setHelpKeys(KEY);

    construct_gcc_to_name();
    construct_visited();
    dom.updateCounter(countVisitedCountries() + '/' + countTotalCountries());

    if (config.connect) {
        construct_directed_graph();
        shorten_path();
    } else {
        construct_random_graph();
    }

    if (config.hidden) {
        dom.hideAll(Object.keys(neighbors))
    }

    if (config.follow) {
        nextcc = directed_graph.shift();
        if (nextcc) {
            dom.unhide('g_'+nextcc);
            dom.setHighlight(nextcc);
            boxit('g_'+nextcc)
        }
    }

    if (config.auto) {
        setTimeout(autoMoveToNextTarget, 1000);
    }
}

function getDefaultConfig() {
    return {
        counter: true,
        timer: true,
        spot: true,
        fullname: false,

        connect: false,
        follow: false,
        hidden: false,
    };
}

function parseBool(str) {
    var val = str.toLowerCase();
    return (val == 'true' || val == 'yes' || val == '1');
}

function parseQueryString(qrystr) {
    if (qrystr) {
        var keyvals = qrystr.substring(1).split('&');
        for (i in keyvals) {
            var kv = keyvals[i].split('=');
            if (kv.length == 2) {
                var key = kv[0];
                var val = kv[1];
                if (key == 'debug') {
                    config.debug = parseBool(val);
                } else if (key == 'auto') {
                    config.auto = parseBool(val);
                } else if (key == 'counter') {
                    config.counter = parseBool(val);
                } else if (key == 'timer') {
                    config.timer = parseBool(val);
                } else if (key == 'spot') {
                    config.spot = parseBool(val);
                } else if (key == 'fullname') {
                    config.fullname = parseBool(val);
                } else if (key == 'connect') {
                    config.connect = parseBool(val);
                } else if (key == 'follow') {
                    config.follow = parseBool(val);
                } else if (key == 'hide') {
                    config.hidden = parseBool(val);
                }
            }
        }
    }
}

function init() {
    config = storage.readConfig();
    if (Object.keys(config).length == 0) {
        config = getDefaultConfig();
    }
    parseQueryString(location.search);
    start();
}


function typeName(nam) {
    document.querySelector('#intext').value = nam + ' ';
    handleKeyDown({ 'key': 'Enter' });
}

function autoMoveToNextTarget() {
    var cc = (config.follow ? nextcc : directed_graph.shift());
    if (cc) {
        var nam = gcc_to_name['g_'+cc];
        typeName(nam);
        setTimeout(autoMoveToNextTarget, 500);
    }
}


function reroute(a, m, z) {
    var rr = [];
    rr.push(a);
    for (var i=0; i<m.length; i++) {
        rr.push(m[i]);
    }
    rr.push(z);
    var kk = [];
    var highest = -1;
    for (var k=rr.length; k>=3; k--) {
        for (var n=0; n+k-1<rr.length; n++) {
            if (isNeighbor(rr[n], rr[n+k-1], false)) {
                if (n >= highest) {
                    highest = n+k-1;
                    kk.push(n);
                    kk.push((n+k-1));
                }
            }
        }
    }

    var cnt = 0;
    var zz = [];
    var finaln = 0;
    while (true) {
        if (cnt <= kk[0]) {
            zz.push(rr[cnt]);
        } else {
            if (kk.length) {
                kk.shift();
                cnt = kk.shift();
                finaln = cnt;
                cnt--;
            }
        }
        if (cnt >= rr.length) {
            break;
        }
        cnt++;
    }
    for (var i=finaln; i<rr.length; i++) {
        zz.push(rr[i]);
    }
    return zz.slice(1, zz.length-1);
}

function shorten_path() {
    var prevcc = null;
    var ulinks = [];
    var vlinks = [];
    var vst = {};
    var newpath = [];

    for (let key in neighbors) {
        vst[key] = 0;
    }

    for (let x in directed_graph) {
        var cc = directed_graph[x];
        if (vst[cc] == 0) {
            if (vlinks.length) {
                var rt = reroute(prevcc, vlinks, cc);
                newpath = newpath.concat(rt);
                prevcc = null;
                vlinks = [];
            }
            ulinks.push(cc);
        } else {
            if (ulinks.length) {
                prevcc = ulinks[ulinks.length - 1];
                newpath = newpath.concat(ulinks);
                ulinks = [];
            }
            vlinks.push(cc);
        }
        vst[cc]++;
    }
    directed_graph = newpath;
}
"""


def generateHtml(tour):
    lines = []

    lines.append('<html>')
    lines.append('<head>')
    lines.append('<meta charset="utf-8">')

    lines.append("<style type='text/css'>")
    lines.append(cssHtmlStyles())
    lines.append('')
    lines.append(tour.cssSvgColors())
    lines.append('</style>')

    lines.append('<script type="text/javascript">')
    lines.append('var revit = ' + prettyPrint(tour.jsNameToNodeId())+';')
    lines.append('')
    lines.append('var neighbors = '+prettyPrint(tour.getNeighbors())+';')
    lines.append('')
    lines.append("var centers = "+prettyPrint(tour.getCenters())+';')
    lines.append('')
    lines.append(jsCode())
    lines.append('</script>')

    lines.append('</head>')

    lines.append('<body onload="init()">')
    lines.append("<div id='endBox'>&nbsp;</div>")
    lines.append("<div id='startBox'>&nbsp;</div>")
    lines.append("<div id='spotty'>&nbsp;</div>")

    lines.append('<div id="mapdisplay">')
    lines.append(tour.generateSvg())
    lines.append('</div>')

    lines.append("<div id='counter' class='stat'>0/{}</div>".format(tour.getNodeCount()))
    lines.append("<div id='timer' class='stat'>0:00</div>")

    lines.append("<div id='userpanel'>")
    lines.append("    <div id='userinput'>")
    lines.append("        <input type='text' id='intext' onkeydown='handleKeyDown(event)' />")
    lines.append("    </div>")
    lines.append("    <div id='suggest'></div>")
    lines.append("</div>")

    lines.append('<div id="configpanel" class="panel">')
    lines.append('  <div style="text-align: center">')
    lines.append('  <span style="font-weight: bold">CONFIG</span>')
    lines.append('  </div>')
    lines.append("    <div><label for='cfgcounter'>")
    lines.append("    <input type='checkbox' class='cfg' id='cfgcounter' checked='checked' onchange='handleCounterChange(this)' /> Show Counter")
    lines.append("    </label></div>")
    lines.append("    <div><label for='cfgtimer'>")
    lines.append("    <input type='checkbox' class='cfg' id='cfgtimer' checked='checked' onchange='handleTimerChange(this)' /> Show Timer")
    lines.append("    </label></div>")
    lines.append("    <div><label for='cfgspot'>")
    lines.append("    <input type='checkbox' class='cfg' id='cfgspot' checked='checked' onchange='handleSpotChange(this)' /> Show Spot")
    lines.append("    </label></div>")
    lines.append("    <div><label for='cfgfullname'>")
    lines.append("    <input type='checkbox' class='cfg' id='cfgfullname' /> Full Name")
    lines.append("    </label></div>")
    lines.append('    <br>')
    lines.append("    <span id='changeNote'>Changing below options will restart</span><br>")
    lines.append("    <div><label for='cfgconnect'>")
    lines.append("    <input type='checkbox' class='cfg' id='cfgconnect' /> Connect")
    lines.append("    </label></div>")
    lines.append("    <div><label for='cfgfollow'>")
    lines.append("    <input type='checkbox' class='cfg' id='cfgfollow' /> Follow")
    lines.append("    </label></div>")
    lines.append("    <div><label for='cfghidden'>")
    lines.append("    <input type='checkbox' class='cfg' id='cfghidden' onchange='handleHiddenChange(this)' /> Hide")
    lines.append("    </label></div>")
    lines.append('    <br>')
    lines.append("    <div style='text-align: center'>")
    lines.append("        <input type='button' class='' id='cfgdone' onclick='closeConfig()' value='Done' />")
    lines.append("    </div>")
    lines.append("</div>")

    lines.append('<div id="helppanel" class="panel">')
    lines.append('  <div style="text-align: center">')
    lines.append('  <span style="font-weight: bold">HELP</span>')
    lines.append('  </div>')
    lines.append("    <p>")
    lines.append("    '<span id='helpKeyComplete'></span>' Show completions (at least two chars must be entered)<br>")
    lines.append("    '<span id='helpKeyNeighbor'></span>' Show neighbors<br>")
    lines.append("    '<span id='helpKeyConfig'  ></span>' Toggle config<br>")
    lines.append("    '<span id='helpKeyHelp'    ></span>' Toggle help<br>")
    lines.append("    '<span id='helpKeyEnter'   ></span>' Toggle zoom (input must be empty)<br>")
    lines.append("    </p>")
    lines.append("    <p>")
    lines.append("    On the <b>CONFIG</b> panel:<br>")
    lines.append("    <i>Fullname</i>: Complete name must be entered.<br>")
    lines.append("    <i>Connect</i>: Entered name must be a neighbor.<br>")
    lines.append("    <i>Follow</i>: The name the highlighted element must be entered.<br>")
    lines.append("    <i>Hide</i>: Hides all elements.<br>")
    lines.append("    <br>")
    lines.append("    If <i>Fullname</i> is unselected, partial names may be supplied, but must be long enough to be unambiguous. Mouse over an element to see its name.<br>")
    lines.append("    </p>")
    lines.append("    <p>")
    lines.append("    If both <i>Connect</i> and <i>Follow</i> are selected, a random path which visits all elements will be generated. The path that is generated may be inefficient. This inefficiency is intentional because efficient paths tend to be extremely similar.<br>")
    lines.append("    </p>")
    lines.append("    The following query parameters (with value 1 or 0) will override config settings: <i>counter</i>, <i>timer</i>, <i>spot</i>, <i>fullname</i>, <i>connect</i>, <i>follow</i>, <i>hide</i>, <i>debug</i>, <i>auto</i>. e.g. '?follow=1&hide=1&spot=0'. Reload page to restart.<br>")
    lines.append("    <br>")
    lines.append("    <div style='text-align: center'>")
    lines.append("        <input type='button' class='' id='cfgdone' onclick='closeHelp()' value='Done' />")
    lines.append("    </div>")
    lines.append("</div>")

    lines.append('<div id="completedpanel" class="panel">')
    lines.append('  <div style="text-align: center">')
    lines.append('  <span style="font-weight: bold">COMPLETE</span>')
    lines.append('  </div>')
    lines.append("    <p id='completedtext'>")
    lines.append("    </p>")
    lines.append("    <div style='text-align: center'>")
    lines.append("        <input type='button' class='' id='completeddone' onclick='closeCompleted()' value='OK' />")
    lines.append("        <input type='button' class='' id='completedrestart' onclick='restart()' value='Restart' />")
    lines.append("    </div>")
    lines.append("</div>")

    lines.append('</body>')
    lines.append('</html>')
    return '\n'.join(lines)


def main():
    astFilename = 'default.ast'
    if len(sys.argv) > 1:
        astFilename = sys.argv[1]
    print('Reading AST '+astFilename)
    tour = Tour(astFilename)
    html = generateHtml(tour)

    fil = open(tour.getName()+'.html', 'w')
    fil.write(html)
    fil.close()

main()
