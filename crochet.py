from math import sin, cos

"""Stitch types:
    Class   English            US                 Length
    SC      double             single             1
    EXSC    extended double    extended single    2
    HDC     half treble        half double        2
    DC      treble             double             3
    TR      double treble      treble             4
    DTR     triple treble      double treble      5
"""


class Node(object):
    """A node where stitches meet."""
    def __init__(self, stitch, prevStitch):
        # A list of stitches this node forms the head of.
        self.headOf= []
        self.nextNode = None
        if stitch:
            self.headOf.append(stitch)
        # A list of stitches this node forms the root of.
        self.rootOf = []
        # The node preceding this node.
        if prevStitch is None:
            # This is the first stitch.
            self.prevNode = None
        else:
            self.prevNode = prevStitch.head
            self.prevNode.nextNode = self

        
class Stitch(object):
    """A stitch."""
    # The stitch length.
    length = None
    # A stitch connecting one root to one head.
    def __init__(self, into, prev, tog=False, dTheta=0):
        # A node that acts as a stitch's root.
        if isinstance(into, Stitch):
            self.root = into.head
        elif isinstance(into, Node):
            self.root = into
        elif into is None:
            self.root = None
        else:
            raise Exception("2nd argument must be instance of Node or Stitch.")
        if self.root:
            self.root.rootOf.append(self)
        # Previous stitch
        self.prev = prev
        if tog:
            self.head = prev.head
        else:
            self.head = Node(self, prev)


class ChainStitch(Stitch):
    length = 1
    abbrev = 'CS'
    """A chain stitch."""
    length = 1
    def __init__(self, prev=None, dTheta=0):
        # The previous stitch and root are the same for a chain stitch.
        super(ChainStitch, self).__init__(prev, prev, tog=False, dTheta=dTheta)


class SlipStitch(Stitch):
    length = 0
    abbrev = 'SS'


class SCStitch(Stitch):
    length = 1
    abbrev = 'SC'


class EXSCStitch(Stitch):
    length = 2
    abbrev = 'EXSC'


class HDCStitch(Stitch):
    length = 2
    abbrev = 'HDC'


class DCStitch(Stitch):
    length = 3
    abbrev = 'DC'


class TRStitch(Stitch):
    length = 4
    ABBREV = 'TR'


class DTRStitch(Stitch):
    length = 5
    abbrev = 'DTR'


class Head(object):
    # The head of one or more stitches.
    def __init__(self, prev=None, width=1, dTheta=0):
        # The previous head.
        self.prev = prev
        # The length of the head - usually 1, but can be 0 for slip stitch.
        self.length = 1
        # Stitches into this head.
        self.stitches = []
        # The width of the head.
        self.width = width
        # The orientation of the head.
        self.theta = None
        # The position of the head.
        self.pos = (None, None)
        if self.prev is None:
            self.theta = dTheta
            self.pos = (0.,0.)
        else:
            self.theta = prev.theta + dTheta
            x, y = self.prev.pos
            x += 0.5 * self.prev.width * cos(self.prev.theta)
            y -= 0.5 * self.prev.width * sin(self.prev.theta)
            x += 0.5 * self.width * cos(self.theta)
            y -= 0.5 * self.width * sin(self.theta)
            self.pos = (x, y)


class Pattern(object):
    def __init__(self):
        self.start = ChainStitch()
        self.lastStitch = self.start
        self.lastRoot = None


    def chain(self, dTheta=0):
        self.lastStitch = ChainStitch(self.lastStitch, dTheta)
        self.lastRoot = self.lastStitch.prev.head


    def workInto(self, stitchType, nodeOrStitch, **kwargs):
        if isinstance(nodeOrStitch, Stitch):
            self.lastRoot = nodeOrStitch.head
        elif isinstance(nodeOrStitch, Node):
            self.lastRoot = nodeOrStitch
        else:
            raise Exception('2nd argument must be a node or stitch.')
        self.lastStitch = stitchType(self.lastRoot, self.lastStitch, **kwargs)


    def workIntoNext(self, stitchType, **kwargs):
        self.workInto(stitchType, self.lastRoot.nextNode)
    

    def workIntoSame(self, stitchType, **kwargs):
        self.workInto(stitchType, self.lastRoot)


    def getAllNodes(self):
        nodes = set()
        stitch = self.lastStitch
        while stitch:
            nodes.add(stitch.head)
            stitch = stitch.prev
        return nodes


    def forwardIter(self):
        node = self.start.head
        while node:
            for stitch in node.headOf:
                yield stitch
            node = node.nextNode


    def backwardIter(self):
        node = self.lastStitch.head
        while node:
            for stitch in node.headOf:
                yield stitch
            node = node.prevNode