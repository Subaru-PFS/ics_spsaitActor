import logging

import numpy as np
from actorcore.QThread import QThread
from spsaitActor.utils import CmdSeq


class defocus(QThread):
    def __init__(self, actor, name, loglevel=logging.DEBUG):
        """This sets up the connections to/from the hub, the logger, and the twisted reactor.

        :param actor: spsaitActor
        :param name: controller name
        """
        QThread.__init__(self, actor, name, timeout=2)
        self.logger = logging.getLogger(self.name)
        self.logger.setLevel(loglevel)

    def getExptime(self, exptime, focus):
        pmean = [4.30234804, 1.76488818, 1]
        return exptime * np.polyval(np.poly1d(pmean), focus)

    def defocus(self, exptime, arc, attenCmd, nbPosition, duplicate, lowBound, upBound, optArgs):
        spsait = self.actor.name

        sequence = [CmdSeq('dcb', "%s on %s" % (arc, attenCmd), doRetry=True)] if arc is not None else []

        step = (upBound - lowBound) / (nbPosition - 1)

        sequence += [
            CmdSeq('enu', "slit move absolute x=%.5f y=%.5f z=%.5f u=%.5f v=%.5f w=%.5f" % (lowBound, 0, 0, 0, 0, 0))]
        focus = lowBound

        cexptime = self.getExptime(exptime, focus)
        sequence += duplicate * [CmdSeq(spsait,
                                        "expose arc exptime=%.2f %s" % (cexptime, ' '.join(optArgs)),
                                        timeLim=500 + cexptime,
                                        doRetry=True)]

        for i in range(nbPosition / 2 - 1):
            sequence += [CmdSeq('enu', "slit focus pix=%.5f" % step)]

            focus += step
            cexptime = self.getExptime(exptime, focus)
            sequence += duplicate * [CmdSeq(spsait,
                                            "expose arc exptime=%.2f %s" % (cexptime, ' '.join(optArgs)),
                                            timeLim=500 + cexptime,
                                            doRetry=True)]

        sequence += [CmdSeq('enu', "slit move absolute x=%.5f y=%.5f z=%.5f u=%.5f v=%.5f w=%.5f" % (0, 0, 0, 0, 0, 0))]

        sequence += [CmdSeq(spsait,
                            'dither psf exptime=%.2f shift=0.5 pixels duplicate=%i %s' % (exptime,
                                                                                          duplicate,
                                                                                          ' '.join(optArgs)),
                            timeLim=(exptime + 200) * 9 * duplicate)]

        focus = 0 if nbPosition % 2 else focus
        sequence += [
            CmdSeq('enu', "slit move absolute x=%.5f y=%.5f z=%.5f u=%.5f v=%.5f w=%.5f" % (focus, 0, 0, 0, 0, 0))]

        for i in range(nbPosition / 2):
            sequence += [CmdSeq('enu', "slit focus pix=%.5f" % step)]

            focus += step
            cexptime = self.getExptime(exptime, focus)
            sequence += duplicate * [CmdSeq(spsait,
                                            "expose arc exptime=%.2f %s" % (cexptime, ' '.join(optArgs)),
                                            timeLim=500 + cexptime,
                                            doRetry=True)]

        return sequence

    def handleTimeout(self):
        """| Is called when the thread is idle
        """
        pass
