import logging

from actorcore.QThread import QThread
from spsaitActor.sequencing import SubCmd


class align(QThread):
    def __init__(self, actor, name, loglevel=logging.DEBUG):
        """This sets up the connections to/from the hub, the logger, and the twisted reactor.

        :param actor: spsaitActor
        :param name: controller name
        """
        QThread.__init__(self, actor, name, timeout=2)
        self.logger = logging.getLogger(self.name)
        self.logger.setLevel(loglevel)

    def sacalign(self, exptime, focus, lowBound, upBound, nbPosition, duplicate):
        step = (upBound - lowBound) / (nbPosition - 1)
        sequence = [SubCmd(actor='sac',
                           cmdStr='move detector=%.2f abs' % focus,
                           timeLim=180)]

        for i in range(nbPosition):
            sequence += [SubCmd(actor='sac',
                                cmdStr='move penta=%.2f abs' % (lowBound + i * step),
                                timeLim=180)]

            sequence += duplicate * [SubCmd(actor='sac',
                                            cmdStr='ccd expose exptime=%.2f' % exptime,
                                            timeLim=30,
                                            getVisit=True)]
        return sequence

    def slitalign(self, exptime, targetedFiber, lowBound, upBound, nbPosition, duplicate):

        if targetedFiber:
            sequence = [SubCmd(actor='breva',
                               cmdStr='goto %s' % targetedFiber,
                               timeLim=180)]
        else:
            sequence = []

        posName = ['X', 'Y', 'Z', 'U', 'V', 'W']
        enuActor = 'enu_sm%i' % self.actor.specToAlign
        enuKeys = self.actor.models[enuActor].keyVarDict

        step = (upBound - lowBound) / (nbPosition - 1)

        for i in range(nbPosition):
            slitPos = [lowBound + i * step] + list(enuKeys['slit'])[1:]
            posAbsolute = ' '.join(['%s=%s' % (name, value) for name, value in zip(posName, slitPos)])

            sequence += [SubCmd(actor=enuActor,
                                cmdStr='slit move absolute %s' % posAbsolute,
                                timeLim=180)]

            sequence += duplicate * [SubCmd(actor='sac',
                                            cmdStr='ccd expose exptime=%.2f' % exptime,
                                            timeLim=30,
                                            getVisit=True)]

        return sequence

    def start(self, cmd=None):
        QThread.start(self)

    def handleTimeout(self):
        """| Is called when the thread is idle
        """
        pass
