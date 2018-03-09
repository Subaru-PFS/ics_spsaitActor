from __future__ import division
from builtins import range

import logging

from actorcore.QThread import QThread
from spsaitActor.utils import CmdSeq


class detalign(QThread):
    def __init__(self, actor, name, loglevel=logging.DEBUG):
        """This sets up the connections to/from the hub, the logger, and the twisted reactor.

        :param actor: spsaitActor
        :param name: controller name
        """
        QThread.__init__(self, actor, name, timeout=2)
        self.logger = logging.getLogger(self.name)
        self.logger.setLevel(loglevel)

    def buildThroughFocus(self, arc, attenCmd, nbImage, exptimes, lowBound, upBound, motor, startPosition, arms):
        step = ((upBound - lowBound)/ (nbImage - 1))
        xcus = [self.actor.arm2xcu[arm] for arm in arms]
        spsait = self.actor.name
        arm = '' if ('blue' in arms and 'red' in arms) else arms[0]

        sequence = [CmdSeq('dcb', "%s on %s" % (arc, attenCmd), doRetry=True)] if arc is not None else []
        # Number of microns must be an integer
        if startPosition is None:
            movAbs = [CmdSeq(xcu, "motors moveCcd %s=%i microns abs" % (motor, lowBound), doRetry=True) for xcu in xcus]
            sequence += movAbs
        else:
            posA, posB, posC = startPosition
            movAbs = [CmdSeq(xcu, "motors moveCcd a=%i b=%i c=%i microns abs" % (posA, posB, posC), doRetry=True) for
                      xcu in xcus]
            sequence += movAbs

        seq_expTime = [
            CmdSeq(spsait, "expose arc exptime=%.2f %s" % (expTime, arm), timeLim=500 + expTime, doRetry=True) for
            expTime in exptimes]
        movRel = [CmdSeq(xcu, "motors moveCcd %s=%i microns" % (motor, step)) for xcu in xcus]

        sequence += seq_expTime

        for i in range(nbImage - 1):
            sequence += movRel
            sequence += seq_expTime

        return sequence

    def handleTimeout(self):
        """| Is called when the thread is idle
        """
        pass
