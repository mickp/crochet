import collections
import numpy as np
import operator
import random
import glUtil
import OpenGL.GL as gl
import OpenGL.arrays.vbo as glvbo
import scipy.optimize as opt
from PyQt4 import QtGui, QtCore
from math import sin, cos

F_FACTOR = 0.9

"""Stitch types:
    Class   English            US                 Length
    SC      double             single             1
    EXSC    extended double    extended single    2
    HDC     half treble        half double        2
    DC      treble             double             3
    TR      double treble      treble             4
    DTR     triple treble      double treble      5
"""

def test():
    p = Pattern()
    nChains = 6
    nStitches = 12
    for i in xrange(nChains):
        p.chain()
    p.workInto(SlipStitch, p.firstStitch)
    mult = 1
    for i in xrange(nStitches):
        if i > 0 and i % nChains == 0:
            into = p.lastStitch
            for j in xrange(nChains-1):
                into = into.prev
            p.workInto(SlipStitch, into)
            p.chain()
            p.workInto(DCStitch, into)
            mult *= 2
        else:
            p.workIntoNext(DCStitch)
            for m in xrange(mult-1):
                p.workIntoNext(DCStitch, tog=True)

    return p


class Vector(object):
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.pos = (x, y)


    def unit(self):
        l = abs(self)
        return self / l


    def __arithmetic__(self, op, operand):
        if isinstance(operand, Vector):
            # Add Vector to Vector
            x1 = operand.x
            y1 = operand.y
        elif isinstance(operand, collections.Iterable):
            # Add tuple or list to Vector
            if len(operand) != 2:
                raise Exception("__add__ operand must be Vector, scalar or 2-element container.")
            x1 = operand[0]
            y1 = operand[1]
        else:
            # Add scalar to Vector.
            x1 = operand
            y1 = operand
        x = op(self.x, x1)
        y = op(self.y, y1)
        return Vector(x, y)


    def __add__(self, operand):
        return self.__arithmetic__(operator.__add__, operand)

    
    def __div__(self, operand):
        return self.__arithmetic__(operator.__div__, operand)


    def __mul__(self, operand):
        return self.__arithmetic__(operator.__mul__, operand)


    def __sub__(self, operand):
        return self.__arithmetic__(operator.__sub__, operand)


    def __repr__(self):
        return u'Vector: (%f, %f).' % self.pos


    def __abs__(self):
        return (self.x**2 + self.y**2)**0.5


class Node(object):
    """A node where stitches meet."""
    def __init__(self, stitch, prevStitch):
        ## Declarations
        # A list of stitches this node forms the head of.
        self.headOf= []
        # A list of stitches this node forms the root of.
        self.rootOf = []
        # The node preceding this node.
        self.prevNode = None
        # The node following this node.
        self.nextNode = None
        # The position of this node.
        self.position = None
        ## Initializations
        if stitch:
            self.headOf.append(stitch)
        if prevStitch is None:
            # This is the first stitch.
            self.prevNode = None
            self.position = Vector(0., 0.)
        else:
            self.prevNode = prevStitch.head
            self.prevNode.nextNode = self
            # Estimate the position.
            if not self.prevNode.prevNode:
                # There is only one preceding stitch
                direction = Vector(1., 0.)
            elif self.prevNode == stitch.root:
                # This node was created by a chain stitch.
                direction = (self.prevNode.prevNode.position - self.prevNode.position).unit()
            else:
                direction = (self.prevNode.prevNode.position - self.prevNode.position).unit()
                # Do something with the root node?
            self.position = self.prevNode.position + direction# + Vector(*[random.uniform(-0.01, 0.01) for i in [0,1]])


    def force(self):
        force = Vector(0.,0.)
        neighbours = set((self.prevNode, self.nextNode))
        neighbours.discard(None)
        for n in neighbours:
            delta = self.position - n.position
            if abs(delta) > 0:
                force += delta.unit() * (1 - abs(delta))
        for s in self.headOf + self.rootOf:
            if s.root:
                delta = self.position - s.root.position
                if abs(delta) > 0:
                    force += delta.unit() * (1 - (abs(delta) / s.length))
        # Noise
        force += Vector(*[random.uniform(-0.001, 0.001) for i in [0,1]])
        # Inflation
        force += self.position * 0.001
        return force


class Stitch(object):
    """A stitch."""
    # The stitch length.
    length = None
    # A stitch connecting one root to one head.
    def __init__(self, into, prev, tog=False):
        # A node that acts as a stitch's root.
        if isinstance(into, Stitch):
            self.root = into.head
        elif isinstance(into, Node):
            self.root = into
        elif into is None:
            self.root = Node(self, None)
        else:
            raise Exception("2nd argument must be instance of Node or Stitch, not %s." % type(prev))
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
    def __init__(self, prev=None):
        # The previous stitch and root are the same for a chain stitch.
        super(ChainStitch, self).__init__(prev, prev, tog=False)


class SlipStitch(Stitch):
    length = 1
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


class Pattern(object):
    def __init__(self):
        self.firstStitch = ChainStitch()
        self.lastStitch = self.firstStitch
        self.lastRoot = None
        self.position = Vector(0.,0.)


    def chain(self):
        self.lastStitch = ChainStitch(self.lastStitch)
        self.lastRoot = self.lastStitch.prev.head


    def workInto(self, stitchType, nodeOrStitch, **kwargs):
        if isinstance(nodeOrStitch, Stitch):
            self.lastRoot = nodeOrStitch.head
        elif isinstance(nodeOrStitch, Node):
            self.lastRoot = nodeOrStitch
        else:
            raise Exception('2nd argument must be a node or stitch, not %s.' % type(nodeOrStitch))
        self.lastStitch = stitchType(self.lastRoot, self.lastStitch, **kwargs)


    def workIntoNext(self, stitchType, **kwargs):
        self.workInto(stitchType, self.lastRoot.nextNode)


    def workIntoSame(self, stitchType, **kwargs):
        self.workInto(stitchType, self.lastRoot)


    def getAllNodes(self):
        nodes = set()
        node = self.firstStitch.head
        while node:
            nodes.add(node)
            node = node.nextNode
        return nodes


    def forwardIter(self):
        node = self.firstStitch.head
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


    def relax(self):
        for i in xrange(10):
            for node in self.getAllNodes():
                node.position += node.force() * F_FACTOR


    def energy(self, positions=None):
        energy = 0
        nodes = self.getAllNodes()
        if positions is not None:
            for node, position in zip(nodes, positions):
                node.position = Vector(*position)
        for node in nodes:
            energy += abs(node.force())**2
        return energy


    def energyOpt(self, positionsAsVector):
        positions = positionsAsVector.reshape((-1, 2))
        return self.energy(positions)


    def optimize(self):
        positions = np.array([[node.position.x, node.position.y] for node in self.getAllNodes()])
        bounds = [[0,0], [0,0]] + [[None,None]] * 2*(len(positions)-1)
        opt.minimize(self.energyOpt, positions.ravel(),
                  method='L-BFGS-B',
                  bounds=bounds,
                  callback=self.updateDisplay)


    def updateDisplay(self, *args):
        if hasattr(self, 'widget'):
            self.widget.updateGL()


class MyGLPlotWidget(glUtil.GLPlotWidget):
    def __init__(self, *args, **kwargs):
        super(MyGLPlotWidget, self).__init__(*args, **kwargs)
        self.pattern = test()


    def keyPressEvent(self, event):
        key = event.key()
        handled = True

        directions = {QtCore.Qt.Key_Left: (-1, 0., 0.),
                      QtCore.Qt.Key_Right: (1, 0., 0.),
                      QtCore.Qt.Key_Up: (0, 1, 0.),
                      QtCore.Qt.Key_Down: (0, -1, 0.),}

        if key in (QtCore.Qt.Key_Plus,):
            gl.glMatrixMode(gl.GL_MODELVIEW)
            gl.glScalef(2.,2., 2.)
        elif key in (QtCore.Qt.Key_Minus,):
            gl.glMatrixMode(gl.GL_MODELVIEW)
            gl.glScalef(.5, .5, .5)
            pass
        elif key in (directions):
            gl.glMatrixMode(gl.GL_MODELVIEW)
            modelview = gl.glGetFloatv(gl.GL_MODELVIEW_MATRIX)
            translate = directions[key] / modelview.diagonal()[0:-1]
            translate *= 0.8
            gl.glTranslatef(*translate)
        elif key in (QtCore.Qt.Key_O, ):
            self.pattern.widget = self
            self.pattern.optimize()
        else:
            self.pattern.relax()

        if handled:
            self.updateGL()
        else:
            event.ignore()


    def initializeGL(self):
        """Initialize OpenGL, VBOs, upload data on the GPU, etc."""
        # background color
        gl.glClearColor(0, 0, 0, 0)


    def paintGL(self):
        gl.glClear(gl.GL_COLOR_BUFFER_BIT)
        gl.glBegin(gl.GL_POINTS)
        gl.glColor3f(1,1,1)
        for node in self.pattern.getAllNodes():
            gl.glVertex2f(*(node.position).pos)
        gl.glEnd()

        gl.glBegin(gl.GL_LINES)
        for stitch in self.pattern.forwardIter():
            gl.glColor3f(0,0,1)
            gl.glVertex2f(*(stitch.root.position).pos)
            gl.glVertex2f(*(stitch.head.position).pos)
            gl.glColor3f(1, 0, 0)
            if stitch.prev:
                gl.glVertex2f(*(stitch.head.position).pos)
                gl.glVertex2f(*(stitch.prev.head.position).pos)
        gl.glEnd()



if __name__ == '__main__':
    import sys
    # define a Qt window with an OpenGL widget inside it
    class CrochetWindow(QtGui.QMainWindow):
        def __init__(self):
            super(CrochetWindow, self).__init__()
            # initialize the GL widget
            self.widget = MyGLPlotWidget()
            # put the window at the screen position (100, 100)
            self.setGeometry(100, 100, self.widget.width, self.widget.height)
            self.setCentralWidget(self.widget)
            self.show()

    # show the window
    win = glUtil.create_window(CrochetWindow)
