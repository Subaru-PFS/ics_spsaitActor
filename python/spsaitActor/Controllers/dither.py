import logging

from actorcore.QThread import QThread
from spsaitActor.utils import CmdSeq

class dither(QThread):
    def __init__(self, actor, name, loglevel=logging.DEBUG):
        """This sets up the connections to/from the hub, the logger, and the twisted reactor.

        :param actor: spsaitActor
        :param name: controller name
        """
        QThread.__init__(self, actor, name, timeout=2)
        self.logger = logging.getLogger(self.name)
        self.logger.setLevel(loglevel)

    def dithering(self, x, y, z, u, v, w, shift, nbImage, exptime, arm, duplicate, attenCmd):
        spsait = self.actor.name

        sequence = duplicate * [
            CmdSeq(spsait, "expose flat exptime=%.2f %s %s" % (exptime, attenCmd, arm), timeLim=exptime + 500,
                   doRetry=True)]

        for i in range(nbImage):
            sequence += [CmdSeq('enu', "slit dither pix=-%.5f" % shift)]
            sequence += duplicate * [
                CmdSeq(spsait, "expose flat exptime=%.2f %s" % (exptime, arm), timeLim=exptime + 500, doRetry=True)]

        sequence += [CmdSeq('enu', "slit move absolute x=%.5f y=%.5f z=%.5f u=%.5f v=%.5f w=%.5f" % (x, y, z, u, v, w))]

        for i in range(nbImage):
            sequence += [CmdSeq('enu', "slit dither pix=%.5f " % shift)]
            sequence += duplicate * [
                CmdSeq(spsait, "expose flat exptime=%.2f %s" % (exptime, arm), timeLim=exptime + 500, doRetry=True)]

        sequence += [CmdSeq('enu', "slit move absolute x=%.5f y=%.5f z=%.5f u=%.5f v=%.5f w=%.5f" % (x, y, z, u, v, w))]
        sequence += duplicate * [
            CmdSeq(spsait, "expose flat exptime=%.2f %s" % (exptime, arm), timeLim=exptime + 500, doRetry=True)]

        return sequence

    def handleTimeout(self):
        """| Is called when the thread is idle
        """
        pass