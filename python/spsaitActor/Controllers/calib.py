import logging

from actorcore.QThread import QThread
from spsaitActor.sequencing import SubCmd


class calib(QThread):
    def __init__(self, actor, name, loglevel=logging.DEBUG):
        """This sets up the connections to/from the hub, the logger, and the twisted reactor.

        :param actor: spsaitActor
        :param name: controller name
        """
        QThread.__init__(self, actor, name, timeout=2)
        self.logger = logging.getLogger(self.name)
        self.logger.setLevel(loglevel)

    def biases(self, duplicate, cams):
        cams = 'cams=%s' % ','.join(cams) if cams else ''

        sequence = duplicate * [SubCmd(actor='spsait',
                                       cmdStr='single bias %s' % cams,
                                       timeLim=180,
                                       getVisit=True)]
        return sequence

    def darks(self, duplicate, exptime, cams):
        cams = 'cams=%s' % ','.join(cams) if cams else ''

        sequence = duplicate * [SubCmd(actor='spsait',
                                       cmdStr='single dark exptime=%.2f %s' % (exptime, cams),
                                       timeLim=exptime+180,
                                       getVisit=True)]
        return sequence

    def calibration(self, nbias, ndarks, exptime, cams):
        sequence = self.biases(duplicate=nbias, cams=cams)
        sequence += self.darks(duplicate=ndarks, exptime=exptime, cams=cams)

        return sequence

    def background(self, exptime, nb, arm):
        spsait = self.actor.name
        return nb * [SubCmd(spsait, "expose exptime=%.2f %s" % (exptime, arm), timeLim=exptime + 500, doRetry=True)]

    def noLight(self):
        return 2 * [SubCmd('dcb', "labsphere attenuator=0")]

    def imstability(self, exptime, nb, delay, arc, duplicate, attenCmd, optArgs):
        spsait = self.actor.name
        sequence = [SubCmd('dcb', "%s on %s" % (arc, attenCmd), doRetry=True)] if arc is not None else []

        acquisition = (duplicate - 1) * [SubCmd(spsait,
                                                "expose arc exptime=%.2f %s" % (exptime, ' '.join(optArgs)),
                                                timeLim=500 + exptime,
                                                doRetry=True)]
        acquisition += [SubCmd(spsait,
                               "expose arc exptime=%.2f %s" % (exptime, ' '.join(optArgs)),
                               timeLim=500 + exptime,
                               doRetry=True,
                               tempo=delay)]

        sequence += nb * acquisition

        return sequence

    def start(self, cmd=None):
        QThread.start(self)

    def handleTimeout(self):
        """| Is called when the thread is idle
        """
        pass
