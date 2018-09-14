import logging
from collections import OrderedDict

import numpy as np
from actorcore.QThread import QThread
from spsaitActor.sequencing import SubCmd


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
        pmean = np.array([0.03920849, 5.04702675, -1.24206109, 2.611892])
        return exptime * np.polyval(pmean, focus)

    def defocus(self, exptime, nbPosition, cams, duplicate):
        sequence = []
        step = 9.0 / (nbPosition - 1)
        cams = cams if cams else self.actor.cams
        specIds = list(OrderedDict.fromkeys([int(cam[1]) for cam in cams]))
        enuActors = ['enu_sm%i' % specId for specId in specIds]

        allHomed = [SubCmd(actor=enuActor, cmdStr='slit move home') for enuActor in enuActors]

        for i in range(nbPosition):
            focus = -4.5 + i * step
            cexptime = self.getExptime(exptime, focus)
            moveAbs = [SubCmd(actor=enuActor,
                              cmdStr='slit move absolute x=%.5f y=0.0 z=0.0 u=0.0 v=0.0 w=0.0' % focus) for enuActor in
                       enuActors]

            sequence += moveAbs

            sequence += duplicate * [SubCmd(actor='spsait',
                                            cmdStr='single arc exptime=%.2f cams=%s' % (cexptime, ','.join(cams)),
                                            timeLim=180 + cexptime,
                                            getVisit=True)]

        sequence += allHomed

        return sequence

    def start(self, cmd=None):
        QThread.start(self)

    def handleTimeout(self):
        """| Is called when the thread is idle
        """
        pass
