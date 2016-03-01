from math import sin, cos

class Stitch(object):
    # A stitch connecting one root to one head.
    def __init__(self, root, length):
        # Another head to act as this stitch's root.
        self.root = root
        # The stitch length.
        self.length = length


class Head(object):
    # The head of one or more stitches.
    def __init__(self, prev=None, width=1, dTheta=0):
        # The previous head.
        self.prev = prev
        # The length of the head - usually 1, but can be 0 for slip stitch.
        self.length = 1
        # Stitches into this head.
        self.stitches = []
        # The width of the stitch.
        self.width = width
        # The orientation of the stitch.
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


class Chain(Head):
    # A chain stitch.
    def __init__(self, prev=None, dTheta=0):
        super(Chain, self).__init__(prev, width=1, dTheta=dTheta)


class Pattern(object):
    def __init__(self):
        self.start = Chain()
        self.prev = self.start


    def crochet(self, into, tog=False, dTheta=0):
        if tog:
            head = self.prev
        else:
            head = Head(self.prev, width=1, dTheta=dTheta)
        head.stitches.append(Stitch(into, length=1))
        self.prev = head


    def chain(self, dTheta=0):
        head = Chain(self.prev, dTheta=dTheta)
        self.prev = head



