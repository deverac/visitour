# Merges AST files and writes merged data to a new file. (WARNING: Also deletes
# all HTML files in the current directory.)
#
# Usage: python3 merge-ast.py [-c _connect.ast] _file1.ast _file2.ast ... _fileN.ast
#
#        The '-c' parameter currently has no special behavior.
#
# Input AST files can be named anything. The underscore prefix and the '.ast'
# extension is only a convention.
#
# The name of the file that is written is generated from the value of the
# 'svgname' property specified in the AST files.

import ast
import sys
import os


AST_DATA = {
    'connector': None,
    'fragments': [],
}


def getTempDirname():
    return 'tmp'


def getConnector():
    return AST_DATA['connector']


def setConnector(fnam):
    global AST_DATA
    AST_DATA['connector'] = fnam


def getFragments():
    return AST_DATA['fragments']


def addFragment(fnam):
    global AST_DATA
    AST_DATA['fragments'].append(fnam)


def parseArgs():
    cparm = False
    if len(sys.argv) > 3:
        for arg in sys.argv[1:]:
            if arg == '-c':
                cparm = True
                continue
            if cparm:
                setConnector(arg)
                cparm = False
            else:
                addFragment(arg)
    if cparm:
        raise Exception('Missing file')


def readAstFile(filename):
    dat = {}
    if os.path.isfile(filename):
        fil = open(filename, 'r')
        contents = fil.read()
        fil.close()
        if len(contents) > 0:
            dat = ast.literal_eval(contents)
        return dat
    print('{} is not a file.'.format(filename))
    return {}


def readAstFiles():
    dct = {}
    for fnam in getFragments():
        dct[fnam] = readAstFile(fnam)
    fnam = getConnector()
    if fnam:
        dct[fnam] = readAstFile(fnam)
    return dct


def basename(filename):
    return os.path.splitext(filename)[0]


def readBaseNames():
    ary = []
    for fnam in getFragments():
        ary.append(basename(fnam))
    return ary


def getFilename(ast):
    if 'svgname' in ast:
        return ast['svgname']
    return None


def getSvgName(astdat):
    name = None
    for fnam in astdat:
        nm = getFilename(astdat[fnam])
        if nm:
            if name:
                if name != nm:
                    raise Exception('Mismatch name {} {}:{}'.format(name, fnam, nm))
            else:
                name = nm
        else:
            raise Exception('No SVG filename specified in {}'.format(fnam))
    return name


def getNodes(astdat):
    ary = []
    for fnam in astdat:
        if 'nodes' in astdat[fnam]:
            ary.extend(astdat[fnam]['nodes'])
    return ary


def getJoin(astdat):
    ary = []
    for fnam in astdat:
        if 'join' in astdat[fnam]:
            ary.extend(astdat[fnam]['join'])
    return ary


def getSnip(astdat):
    ary = []
    for fnam in astdat:
        if 'snip' in astdat[fnam]:
            ary.extend(astdat[fnam]['snip'])
    return ary


def getSvgcolors(astdat):
    dct = {}
    for fnam in astdat:
        if 'svgcolors' in astdat[fnam]:
            dct.update(astdat[fnam]['svgcolors'])
    return dct


def getExtra(astdat):
    ary = []
    for fnam in astdat:
        if 'extra' in astdat[fnam]:
            val = astdat[fnam]['extra']
            if val not in ary:
                ary.extend(val)
    return ary


def getColors(astdat):
    ary = []
    for fnam in astdat:
        if 'colors' in astdat[fnam]:
            ary.extend(astdat[fnam]['colors'])
    return ary


def mergeAst(astdat, svgname):
    obj = {
        'svgname': svgname,
        'nodes': getNodes(astdat),
        'join': getJoin(astdat),
        'snip': getSnip(astdat),
        'extra': getExtra(astdat),
        'colors': getColors(astdat),
        'svgcolors': getSvgcolors(astdat)
    }
    return obj


# A crude pretty-printer.
def prettyPrint(obj, ind=2):
    lines = []
    if isinstance(obj, list):
        if len(obj) > 0:
            if isinstance(obj[0], list):
                lines.append('[')
                for i in sorted(obj):
                    lines.append("{}{},".format(' '*(ind+2), i))
                lines.append("{}{}".format(' '*ind, ']'))
            else:
                return str(sorted(obj))
        else:
            return str(sorted(obj))
    elif isinstance(obj, dict):
        lines.append('{')
        for (k, v) in sorted(obj.items()):
            if isinstance(v, dict):
                val = prettyPrint(v, ind+2)
            elif isinstance(v, list):
                val = prettyPrint(v, ind+2)
            elif isinstance(v, str):
                val = "'{}'".format(v)
            else:
                val = v
            lines.append("{}'{}': {},".format(' '*ind, k, val))
        lines.append('{}{}'.format(' '*(ind-2), '}'))
    else:
        lines.append(str(obj))
    return '\n'.join(lines);


def readCacheFile(basenames, suffix):
    dct = {}
    for name in basenames:
        filename = os.path.join(getTempDirname(), '{}_{}.cache'.format(name, suffix))
        dat = readAstFile(filename)
        dct.update(dat)
    return dct


def readNeighborFiles(basenames):
    return readCacheFile(basenames, 'neighbors')


def readCenterFiles(basenames):
    return readCacheFile(basenames, 'centers')


def writeMergedAstFile(astdat, svgname, prefix):
    astFilename = '{}.ast'.format(prefix)
    fil = open(astFilename, 'w')
    fil.write(prettyPrint(mergeAst(astdat, svgname)))
    fil.close()
    print('Wrote AST {}'.format(astFilename))


def writeNeighborCacheFile(basenames, prefix):
    cacheFile = os.path.join(getTempDirname(), '{}_neighbors.cache'.format(prefix))
    fil = open(cacheFile, 'w')
    fil.write(prettyPrint(readNeighborFiles(basenames)))
    fil.close()
    print('Wrote {}'.format(cacheFile))


def writeCenterCacheFile(basenames, prefix):
    cacheFile = os.path.join(getTempDirname(), '{}_centers.cache'.format(prefix))
    fil = open(cacheFile, 'w')
    fil.write(prettyPrint(readCenterFiles(basenames)))
    fil.close()
    print('Wrote {}'.format(cacheFile))


def removeHtmlFiles(names):
    for name in names:
        try:
            os.remove('{}.html'.format(name))
        except OSError:
            pass


parseArgs()

astData = readAstFiles()
baseNames = readBaseNames()
svgName = getSvgName(astData)
prefix = basename(svgName)

writeMergedAstFile(astData, svgName, prefix)
writeNeighborCacheFile(baseNames, prefix)
writeCenterCacheFile(baseNames, prefix)
removeHtmlFiles(baseNames)
