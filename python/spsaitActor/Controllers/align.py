import logging

from actorcore.QThread import QThread
from spsaitActor.sequencing import Sequence


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

        seq = Sequence()
        seq.addSubCmd(actor='sac', cmdStr='move detector=%.2f abs' % focus)

        for i in range(nbPosition):
            seq.addSubCmd(actor='sac',
                          cmdStr='move penta=%.2f abs' % (lowBound + i * step))

            seq.addSubCmd(actor='sac',
                          cmdStr='ccd expose exptime=%.2f' % exptime,
                          duplicate=duplicate,
                          timeLim=60 + exptime)
        return seq

    def slitalign(self, exptime, targetedFiber, lowBound, upBound, nbPosition, duplicate):
        seq = Sequence()

        if targetedFiber:
            seq.addSubCmd(actor='breva', cmdStr='goto fiber=%s' % targetedFiber)

        posName = ['X', 'Y', 'Z', 'U', 'V', 'W']
        enuActor = 'enu_sm%i' % self.actor.specToAlign
        enuKeys = self.actor.models[enuActor].keyVarDict

        step = (upBound - lowBound) / (nbPosition - 1)

        for i in range(nbPosition):
            slitPos = [round(lowBound + i * step, 6)] + list(enuKeys['slit'])[1:]
            posAbsolute = ' '.join(['%s=%s' % (name, value) for name, value in zip(posName, slitPos)])

            seq.addSubCmd(actor=enuActor,
                          cmdStr='slit move absolute %s' % posAbsolute)

            seq.addSubCmd(actor='sac',
                          cmdStr='ccd expose exptime=%.2f' % exptime,
                          duplicate=duplicate,
                          timeLim=60 + exptime)
        return seq

    def detalign(self, exptime, cam, startPosition, upBound, nbPosition, duplicate):
        seq = Sequence()
        xcuActor = 'xcu_%s' % cam
        step = (upBound - max(startPosition)) / (nbPosition - 1)

        for i in range(nbPosition):
            posA, posB, posC = startPosition + i * step
            seq.addSubCmd(actor=xcuActor,
                          cmdStr='motors moveCcd a=%i b=%i c=%i microns abs' % (posA, posB, posC))

            seq.addSubCmd(actor='spsait',
                          cmdStr='single arc exptime=%.2f cam=%s' % (exptime, cam),
                          duplicate=duplicate,
                          timeLim=120 + exptime)
        return seq

    def start(self, cmd=None):
        QThread.start(self)

    def handleTimeout(self):
        """| Is called when the thread is idle
        """
        pass
