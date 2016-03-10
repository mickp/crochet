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
    nRounds = 2
    for i in xrange(nChains):
        p.chain()
    mult = 2
    p.workInto(SlipStitch, 0)
    start = p.lastWorked    
    p.chain()
    p.chain()
    joinAt = p.lastWorked
    
    for i in xrange(nRounds):
        for j in xrange((mult-1) * nChains):
            if j == 0:
                p.workInto(DCStitch, start)
            else:
                p.workIntoNext(DCStitch)
            for m in xrange(mult-1):
                p.workIntoSame(DCStitch)
        p.workInto(SlipStitch, joinAt)
        start = p.lastWorked
        p.chain()
        p.chain()
        joinAt = p.lastWorked
        mult *= 2

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
    def __init__(self, position=None, prevNode=None):
        ## Declarations
        # A list of stitches this node forms the head of.
        self.headOf= set()
        # A list of stitches this node forms the root of.
        self.rootOf = set()
        # The position of this node.
        self.position = None
        # Links to other nodes.
        self.adjoins = []
        ## Initializations
        self.position = position
        if prevNode:
            self.adjoins.append(prevNode)
            prevNode.adjoins.append(self)
        self.mobile = True
        self.active = False


    def activate(self):
        self.active = True
        self.position = self.guessPosition()


    def guessPosition(self):
        position = Vector(0,0)
        js = [j for j in self.adjoins if j.active]    
        if len(js) == 1:
            position = js[0].position + Vector(*[random.uniform(-1, 1) for i in [0,1]])
        elif len(js) > 1:
            for j in js:
                position += j.position
            position /= len(js)
        return position


    def join(self, other):
        self.adjoins.append(other)
        other.adjoins.append(self)


    def force(self):
        force = Vector(0.,0.)
        if not self.mobile:
            return force
        for j in self.adjoins:
            delta = self.position - j.position
            if abs(delta) > 0:
                force += delta.unit() * (1 - abs(delta))
        for s in self.headOf.union(self.rootOf):
            if s.root:
                delta = self.position - s.root.position
                if abs(delta) > 0:
                    force += delta.unit() * (1 - (abs(delta) / s.length))**2
        # Inflation
        #force += self.position * 0.0001
        return force


class Stitch(object):
    """A stitch."""
    # The stitch length.
    length = None
    # A stitch connecting one root to one head.
    def __init__(self, into, head):
        # A node that acts as a stitch's root.
        if isinstance(into, Stitch):
            self.root = into.head
        elif isinstance(into, Node):
            self.root = into
        else:
            raise Exception("2nd argument must be instance of Node or Stitch, not %s." % type(prev))
        self.root.rootOf.add(self)
        self.head = head
        self.head.headOf.add(self)


class ChainStitch(Stitch):
    length = 1
    abbrev = 'CS'
    """A chain stitch."""
    length = 1
    def __init__(self, head):
        self.head = head
        self.root = None


class SlipStitch(Stitch):
    length = 1
    abbrev = 'SS'
    def __init__(self, into, head):
        self.head = head
        self.root = None


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
        # A list of all stitches.
        self.stitches = []
        # A list of all nodes.
        self.nodes = []
        # The current propagation direction: forward (1) or backward (-1).
        self.direction = 1
        # The last worked node index.
        self.lastWorked = 0
        self.hookAt = 0
        self.numActive = 2
        self.addNode()
        self.nodes[0].mobile = False


    def addNode(self):
        if len(self.nodes) == 0:
            # This is the first node.
            node = Node()
        elif len(self.nodes[-1].adjoins) == 0:
            # There is only one preceding node.
            direction = Vector(1., 0.)
            position = self.nodes[-1].position + direction
            node = Node(position, self.nodes[-1])       
        else:
            direction = (self.nodes[-1].position - self.nodes[-1].adjoins[0].position).unit()
            position = self.nodes[-1].position + direction
            node = Node(position, self.nodes[-1])       
        self.nodes.append(node)
        if len(self.nodes) <= self.numActive:
            node.activate()
        return self.nodes[-1]


    def chain(self):
        self.lastWorked = len(self.nodes) - 1
        self.stitches.append(ChainStitch(self.addNode()))
        self.hookAt = len(self.nodes) - 1


    def workInto(self, stitchType, nodeIndex, tog=False, **kwargs):
        if stitchType is SlipStitch:
            self.nodes[-1].join(self.nodes[nodeIndex])
        elif not tog:
            self.addNode()
            self.hookAt = len(self.nodes)
        self.stitches.append(stitchType(self.nodes[nodeIndex], self.nodes[-1]), **kwargs)
        self.lastWorked = nodeIndex


    def workIntoNext(self, stitchType, **kwargs):
        self.workInto(stitchType, self.lastWorked + self.direction)


    def workIntoSame(self, stitchType, **kwargs):
        self.workInto(stitchType, self.lastWorked)


    def turn(self):
        self.direction *= -1


    def relax(self):
        for node in self.nodes[0:self.numActive]:
            if not node.mobile:
                continue
            ## Non-specific forces
            nonSpecific = Vector(0, 0)
            others = set(self.nodes[0:self.numActive])
            others.discard(node)
            for other in others:
                delta = node.position - other.position
                if abs(delta) > 0:
                    nonSpecific += delta.unit() * (1 /  abs(delta)**2) * .01
                nonSpecific += Vector(*[random.uniform(-0.01, 0.01) for i in [0,1]])
            ## Specific forces       
            specific = Vector(0.,0.)
            # From adjoining nodes.
            for j in node.adjoins:
                if not j.active:
                    continue
                delta = node.position - j.position
                if abs(delta) > 0:
                    specific += delta.unit() * (1 - abs(delta)) * 0.01
            # From stitches.
            for s in node.headOf:
                if s.root:
                    if s.root.active:
                        delta = node.position - s.root.position
                        if abs(delta) > 0:
                            specific += (delta.unit() * (1 - (abs(delta) / s.length))**2 ) / -100
            node.position += (nonSpecific + specific) * F_FACTOR


    def forward(self, n=1):
        upper = min(len(self.nodes), self.numActive+n)
        for node in self.nodes[self.numActive:upper]:
            #node.activate()
            node.active = True
            pos = node.guessPosition()
            node.position = node.guessPosition()
        self.numActive = upper


    def backward(self, n=1):
        lower = max(0, self.numActive-n)
        for node in self.nodes[lower:self.numActive]:
            node.active = False
        self.numActive = lower


    def energy(self, positions=None):
        energy = 0
        nodes = self.nodes
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
        positions = np.array([[node.position.x, node.position.y] for node in self.nodes])
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
        elif key in (QtCore.Qt.Key_Greater, QtCore.Qt.Key_N):
            self.pattern.forward(1)
        elif key in (QtCore.Qt.Key_Less, QtCore.Qt.Key_P):
            self.pattern.backward(1)
        elif key in (QtCore.Qt.Key_W,):
            self.pattern.nodes[self.pattern.numActive-1].position += Vector(0., 0.2)
        elif key in (QtCore.Qt.Key_S,):
            self.pattern.nodes[self.pattern.numActive-1].position += Vector(0., -.2)
        elif key in (QtCore.Qt.Key_D,):
            self.pattern.nodes[self.pattern.numActive-1].position += Vector(0.2, 0)
        elif key in (QtCore.Qt.Key_A,):
            self.pattern.nodes[self.pattern.numActive-1].position += Vector(-.2, 0)
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
        node = self.pattern.nodes[0]
        gl.glPointSize(6.)
        gl.glColor3f(1,1,1)
        gl.glBegin(gl.GL_POINTS)
        gl.glVertex2f(*node.position.pos)
        gl.glEnd()
        gl.glPointSize(4.)
        r = 0.1
        gl.glLineWidth(3)
        for node in self.pattern.nodes:
            if not node.active:
                continue
            gl.glBegin(gl.GL_LINES)
            for other in set(node.adjoins):
                if not other.active:
                    continue
                gl.glColor3f(r, 0, 0)
                gl.glVertex2f(*node.position.pos)
                gl.glVertex2f(*other.position.pos)
                r *= 1.1
            gl.glEnd()
            gl.glColor3f(1,1,1)
            gl.glBegin(gl.GL_POINTS)
            gl.glVertex2f(*node.position.pos)
            gl.glEnd()
        gl.glLineWidth(2)
        gl.glBegin(gl.GL_LINES)
        for stitch in self.pattern.stitches:
            gl.glColor3f(0,0,1)
            if stitch.root and stitch.head:
                if not (stitch.root.active and stitch.head.active):
                    continue
                gl.glVertex2f(*stitch.root.position.pos)
                gl.glVertex2f(*stitch.head.position.pos)
            gl.glColor3f(1, 0, 0)
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
