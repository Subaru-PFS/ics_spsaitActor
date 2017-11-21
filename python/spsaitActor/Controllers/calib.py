import logging

from actorcore.QThread import QThread

from spsaitActor.utils import CmdSeq


class calib(QThread):
    def __init__(self, actor, name, loglevel=logging.DEBUG):
        """This sets up the connections to/from the hub, the logger, and the twisted reactor.

        :param actor: spsaitActor
        :param name: controller name
        """
        QThread.__init__(self, actor, name, timeout=2)
        self.logger = logging.getLogger(self.name)
        self.logger.setLevel(loglevel)

    def background(self, exptime, nb, arm):
        spsait = self.actor.name
        return nb * [CmdSeq(spsait, "expose exptime=%.2f %s" % (exptime, arm), timeLim=exptime + 500, doRetry=True)]

    def noLight(self):
        return 2 * [CmdSeq('dcb', "labsphere attenuator=0")]

    def bias(self, ccd, nbias):
        return [CmdSeq(ccd, "expose nbias=%i" % nbias, timeLim=500, doRetry=True)]

    def dark(self, ccd, exptime, ndarks):
        return ndarks * [CmdSeq(ccd, "expose darks=%.2f" % exptime, timeLim=exptime + 500, doRetry=True)]

    def calibration(self, ccd, nbias, ndarks, exptime):
        sequence = self.bias(ccd, nbias)
        sequence += self.dark(ccd, exptime, ndarks)

        return sequence

    def imstability(self, exptime, nb, delay, arc, arm, duplicate, attenCmd):
        spsait = self.actor.name
        sequence = [CmdSeq('dcb', "%s on %s" % (arc, attenCmd), doRetry=True)] if arc is not None else []

        acquisition = (duplicate - 1) * [CmdSeq(spsait,
                                                "expose arc exptime=%.2f %s" % (exptime, arm),
                                                timeLim=500 + exptime,
                                                doRetry=True)]
        acquisition += [CmdSeq(spsait,
                               "expose arc exptime=%.2f %s" % (exptime, arm),
                               timeLim=500 + exptime,
                               doRetry=True,
                               tempo=delay)]

        sequence += nb * acquisition

        return sequence

    def arcs(self, exptime, arc, arm, duplicate, attenCmd):
        spsait = self.actor.name

        sequence = [CmdSeq('dcb', "%s on %s" % (arc, attenCmd), doRetry=True)] if arc is not None else []
        sequence += duplicate * [CmdSeq(spsait,
                                        "expose arc exptime=%.2f %s" % (exptime, arm),
                                        timeLim=500 + exptime,
                                        doRetry=True)]

        return sequence

    def expose(self, exptime, arm, duplicate):
        spsait = self.actor.name

        sequence = duplicate * [CmdSeq(spsait,
                                       "expose exptime=%.2f %s" % (exptime, arm),
                                       timeLim=500 + exptime,
                                       doRetry=True)]
        return sequence

    def handleTimeout(self):
        """| Is called when the thread is idle
        """
        pass
