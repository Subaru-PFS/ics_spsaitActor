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
                                       timeLim=exptime + 180,
                                       getVisit=True)]
        return sequence

    def calibration(self, nbias, ndarks, exptime, cams):
        sequence = self.biases(duplicate=nbias, cams=cams)
        sequence += self.darks(duplicate=ndarks, exptime=exptime, cams=cams)

        return sequence

    def imstab(self, exptime, nbPosition, delay, duplicate, cams):
        sequence = []
        subseq = (duplicate - 1) * [SubCmd(actor='spsait',
                                           cmdStr='single arc exptime=%.2f cams=%s' % (exptime, ','.join(cams)),
                                           timeLim=180 + exptime,
                                           getVisit=True)]
        subseq += [SubCmd(actor='spsait',
                          cmdStr='single arc exptime=%.2f cams=%s' % (exptime, ','.join(cams)),
                          timeLim=180 + exptime,
                          tempo=delay,
                          getVisit=True)]

        sequence = (nbPosition - 1) * subseq
        sequence += duplicate * [SubCmd(actor='spsait',
                                        cmdStr='single arc exptime=%.2f cams=%s' % (exptime, ','.join(cams)),
                                        timeLim=180 + exptime,
                                        getVisit=True)]
        return sequence

    def start(self, cmd=None):
        QThread.start(self)

    def handleTimeout(self):
        """| Is called when the thread is idle
        """
        pass
