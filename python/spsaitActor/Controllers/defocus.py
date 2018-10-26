import logging
from collections import OrderedDict

import numpy as np
from actorcore.QThread import QThread
from spsaitActor.sequencing import Sequence


class defocus(QThread):
    posName = ['X', 'Y', 'Z', 'U', 'V', 'W']

    def __init__(self, actor, name, loglevel=logging.DEBUG):
        """This sets up the connections to/from the hub, the logger, and the twisted reactor.

        :param actor: spsaitActor
        :param name: controller name
        """
        QThread.__init__(self, actor, name, timeout=2)
        self.logger = logging.getLogger(self.name)
        self.logger.setLevel(loglevel)

    def getExptime(self, exptime, focus):
        pmean = np.array([0.03920849, 5.04702675, -1.24206109, 2.611892])
        return exptime * np.polyval(pmean, focus)

    def defocus(self, exptime, nbPosition, lowBound, upBound, cams, duplicate):
        step = (upBound - lowBound) / (nbPosition - 1)
        cams = cams if cams else self.actor.cams

        specIds = list(OrderedDict.fromkeys([int(cam[1]) for cam in cams]))
        enuActors = ['enu_sm%i' % specId for specId in specIds]

        seq = Sequence()

        for i in range(nbPosition):
            focus = round(lowBound + i * step, 6)
            cexptime = self.getExptime(exptime, focus)
            for enuActor in enuActors:
                enuKeys = self.actor.models[enuActor].keyVarDict
                posAbsolute = [focus] + list(enuKeys['slit'])[1:]
                posAbsolute = ' '.join(['%s=%.5f' % (name, value) for name, value in zip(defocus.posName, posAbsolute)])
                seq.addSubCmd(actor=enuActor, cmdStr='slit move absolute %s' % posAbsolute)

            seq.addSubCmd(actor='spsait',
                          cmdStr='single arc exptime=%.2f cams=%s' % (cexptime, ','.join(cams)),
                          timeLim=120 + cexptime,
                          duplicate=duplicate)

        for enuActor in enuActors:
            enuKeys = self.actor.models[enuActor].keyVarDict
            posAbsolute = [0] + list(enuKeys['slit'])[1:]
            posAbsolute = ' '.join(['%s=%.5f' % (name, value) for name, value in zip(defocus.posName, posAbsolute)])
            seq.addSubCmd(actor=enuActor, cmdStr='slit move absolute %s' % posAbsolute)

        return seq

    def start(self, cmd=None):
        QThread.start(self)

    def handleTimeout(self):
        """| Is called when the thread is idle
        """
        pass
