import logging
from collections import OrderedDict

import numpy as np
from actorcore.QThread import QThread
from spsaitActor.utils.sequencing import CmdList


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

    def slitalign(self, exptime, positions, targetedFiber, duplicate):
        seq = CmdList()

        if targetedFiber:
            seq.addSubCmd(actor='breva', cmdStr='goto fiber=%s' % targetedFiber)

        enuActor = 'enu_sm%i' % self.actor.specToAlign
        enuKeys = self.actor.models[enuActor].keyVarDict

        for focus in positions:
            posAbsolute = [focus] + list(enuKeys['slit'])[1:]
            posAbsolute = ' '.join(['%s=%.5f' % (name, value) for name, value in zip(align.posName, posAbsolute)])

            seq.addSubCmd(actor=enuActor,
                          cmdStr='slit move absolute %s' % posAbsolute)

            seq.addSubCmd(actor='sac',
                          cmdStr='ccd expose exptime=%.2f' % exptime,
                          duplicate=duplicate,
                          timeLim=60 + exptime)
        return seq

    def slitTF(self, exptime, positions, cams, duplicate):
        specIds = list(OrderedDict.fromkeys([int(cam[1]) for cam in cams])) if cams else self.actor.specIds
        cams = 'cams=%s' % ','.join(cams) if cams else ''
        enuActors = ['enu_sm%i' % specId for specId in specIds]

        seq = CmdList()

        for focus in positions:
            for enuActor in enuActors:
                enuKeys = self.actor.models[enuActor].keyVarDict
                posAbsolute = [focus] + list(enuKeys['slit'])[1:]
                posAbsolute = ' '.join(['%s=%.5f' % (name, value) for name, value in zip(align.posName, posAbsolute)])
                seq.addSubCmd(actor=enuActor, cmdStr='slit move absolute %s' % posAbsolute)

            seq.addSubCmd(actor='sps',
                          cmdStr='expose arc exptime=%.2f %s' % (exptime, cams),
                          timeLim=120 + exptime,
                          duplicate=duplicate)

        return seq

    def detalign(self, exptime, cam, lowBound, upBound, nbPosition, tilt, duplicate, waveRange):
        seq = CmdList()
        xcuActor = 'xcu_%s' % cam
        upBound -= tilt.max()
        positions = np.linspace(lowBound, upBound, nbPosition)

        for position in positions:
            posA, posB, posC = np.ones(3) * position + tilt
            seq.addSubCmd(actor=xcuActor,
                          cmdStr='motors moveCcd a=%i b=%i c=%i microns abs' % (posA, posB, posC))
            if not waveRange:
                seq.addSubCmd(actor='sps',
                              cmdStr='expose arc exptime=%.2f cam=%s' % (exptime, cam),
                              duplicate=duplicate,
                              timeLim=120 + exptime)
            else:
                seq.extend(self.detScan(exptime, [cam], duplicate, *waveRange))

        return seq

    def detScan(self, exptime, cams, duplicate, waveStart, waveEnd, waveNb):
        cams = 'cams=%s' % ','.join(cams) if cams else ''
        waves = np.linspace(waveStart, waveEnd, waveNb)

        seq = CmdList()
        for wave in waves:
            seq.addSubCmd(actor='dcb',
                          cmdStr='mono set wave=%.5f' % wave)
            seq.addSubCmd(actor='sps',
                          cmdStr='expose arc exptime=%.2f %s' % (exptime, cams),
                          duplicate=duplicate,
                          timeLim=120 + exptime)

        return seq

    def start(self, cmd=None):
        QThread.start(self)

    def stop(self, cmd=None):
        self.exit()

    def handleTimeout(self):
        """| Is called when the thread is idle
        """
        pass
