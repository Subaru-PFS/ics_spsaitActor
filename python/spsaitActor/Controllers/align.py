import logging
from collections import OrderedDict
import numpy as np

from actorcore.QThread import QThread
from spsaitActor.sequencing import Sequence


class align(QThread):
    posName = ['X', 'Y', 'Z', 'U', 'V', 'W']

    def __init__(self, actor, name, loglevel=logging.DEBUG):
        """This sets up the connections to/from the hub, the logger, and the twisted reactor.

        :param actor: spsaitActor
        :param name: controller name
        """
        QThread.__init__(self, actor, name, timeout=2)
        self.logger = logging.getLogger(self.name)
        self.logger.setLevel(loglevel)

    def slitalign(self, exptime, targetedFiber, lowBound, upBound, nbPosition, duplicate):
        seq = Sequence()

        if targetedFiber:
            seq.addSubCmd(actor='breva', cmdStr='goto fiber=%s' % targetedFiber)

        enuActor = 'enu_sm%i' % self.actor.specToAlign
        enuKeys = self.actor.models[enuActor].keyVarDict

        step = (upBound - lowBound) / (nbPosition - 1)

        for i in range(nbPosition):
            slitPos = [round(lowBound + i * step, 6)] + list(enuKeys['slit'])[1:]
            posAbsolute = ' '.join(['%s=%s' % (name, value) for name, value in zip(align.posName, slitPos)])

            seq.addSubCmd(actor=enuActor,
                          cmdStr='slit move absolute %s' % posAbsolute)

            seq.addSubCmd(actor='sac',
                          cmdStr='ccd expose exptime=%.2f' % exptime,
                          duplicate=duplicate,
                          timeLim=60 + exptime)
        return seq

    def detalign(self, exptime, cam, startPosition, upBound, nbPosition, duplicate, waveRange):
        seq = Sequence()
        xcuActor = 'xcu_%s' % cam
        step = (upBound - max(startPosition)) / (nbPosition - 1)

        for i in range(nbPosition):
            posA, posB, posC = startPosition + i * step
            seq.addSubCmd(actor=xcuActor,
                          cmdStr='motors moveCcd a=%i b=%i c=%i microns abs' % (posA, posB, posC))
            if not waveRange:
                seq.addSubCmd(actor='spsait',
                              cmdStr='single arc exptime=%.2f cam=%s' % (exptime, cam),
                              duplicate=duplicate,
                              timeLim=120 + exptime)
            else:
                seq.extend(self.detScan(exptime, cam, duplicate, *waveRange))

        return seq

    def detScan(self, exptime, cams, duplicate, waveStart, waveEnd, waveStep):
        waves = np.arange(waveStart, waveEnd+waveStep, waveStep)

        seq = Sequence()
        for wave in waves:
            seq.addSubCmd(actor='dcb',
                          cmdStr='mono set wave=%.5f'%wave)
            seq.addSubCmd(actor='spsait',
                          cmdStr='single arc exptime=%.2f cams=%s' % (exptime, ','.join(cams)),
                          duplicate=duplicate,
                          timeLim=120 + exptime)

        return seq

    def slitTF(self, exptime, nbPosition, lowBound, upBound, cams, duplicate):
        step = (upBound - lowBound) / (nbPosition - 1)

        specIds = list(OrderedDict.fromkeys([int(cam[1]) for cam in cams]))
        enuActors = ['enu_sm%i' % specId for specId in specIds]

        seq = Sequence()

        for i in range(nbPosition):
            focus = round(lowBound + i * step, 6)
            for enuActor in enuActors:
                enuKeys = self.actor.models[enuActor].keyVarDict
                posAbsolute = [focus] + list(enuKeys['slit'])[1:]
                posAbsolute = ' '.join(['%s=%.5f' % (name, value) for name, value in zip(align.posName, posAbsolute)])
                seq.addSubCmd(actor=enuActor, cmdStr='slit move absolute %s' % posAbsolute)

            seq.addSubCmd(actor='spsait',
                          cmdStr='single arc exptime=%.2f cams=%s' % (exptime, ','.join(cams)),
                          timeLim=120 + exptime,
                          duplicate=duplicate)

        return seq

    def start(self, cmd=None):
        QThread.start(self)

    def handleTimeout(self):
        """| Is called when the thread is idle
        """
        pass
