import logging
from collections import OrderedDict

import numpy as np
from actorcore.QThread import QThread
from spsaitActor.sequencing import SubCmd


class dither(QThread):
    posName = ['X', 'Y', 'Z', 'U', 'V', 'W']

    def __init__(self, actor, name, loglevel=logging.DEBUG):
        """This sets up the connections to/from the hub, the logger, and the twisted reactor.
        :param actor: spsaitActor
        :param name: controller name
        """
        QThread.__init__(self, actor, name, timeout=2)
        self.logger = logging.getLogger(self.name)
        self.logger.setLevel(loglevel)

    def ditherflat(self, exptime, cams, shift, nbPosition, duplicate):
        sequence = []

        cams = cams if cams else self.actor.cams

        flats = duplicate * [SubCmd(actor='spsait',
                                    cmdStr='single flat exptime=%.2f cams=%s' % (exptime, ','.join(cams)),
                                    timeLim=180 + exptime,
                                    getVisit=True)]
        sequence += flats

        specIds = list(OrderedDict.fromkeys([int(cam[1]) for cam in cams]))
        enuActors = ['enu_sm%i' % specId for specId in specIds]
        moveToStart = []

        for enuActor in enuActors:
            posAbsolute = list(self.actor.models[enuActor].keyVarDict['slit'])
            posAbsolute = ' '.join(['%s=%.5f' % (name, value) for name, value in zip(dither.posName, posAbsolute)])
            moveToStart.append(SubCmd(actor=enuActor, cmdStr='slit move absolute %s' % posAbsolute, timeLim=180))

        negShift = [SubCmd(actor=enuActor, cmdStr="slit dither pix=-%.5f" % shift) for enuActor in enuActors]
        posShift = [SubCmd(actor=enuActor, cmdStr="slit dither pix=%.5f" % shift) for enuActor in enuActors]

        for i in range(nbPosition):
            sequence += negShift
            sequence += flats

        sequence += moveToStart

        for i in range(nbPosition):
            sequence += posShift
            sequence += flats

        sequence += moveToStart
        sequence += flats

        return sequence

    def ditherpsf(self, exptime, cams, shift, duplicate):
        sequence = []
        positions = np.array([(0, -1, -1, 0, 0, 0),
                              (0, -1, 0, 0, 0, 0),
                              (0, -1, 1, 0, 0, 0),
                              (0, 0, -1, 0, 0, 0),
                              (0, 0, 0, 0, 0, 0),
                              (0, 0, 1, 0, 0, 0),
                              (0, 1, -1, 0, 0, 0),
                              (0, 1, 0, 0, 0, 0),
                              (0, 1, 1, 0, 0, 0)])

        positions = positions * shift

        cams = cams if cams else self.actor.cams
        specIds = list(OrderedDict.fromkeys([int(cam[1]) for cam in cams]))
        enuActors = ['enu_sm%i' % specId for specId in specIds]

        for position in positions:
            posAbsolute = ' '.join(['%s=%.5f' % (name, value) for name, value in zip(dither.posName, position)])

            sequence += [SubCmd(actor=enuActor, cmdStr='slit move absolute %s' % posAbsolute) for enuActor in enuActors]

            sequence += duplicate * [SubCmd(actor='spsait',
                                            cmdStr='single arc exptime=%.2f cams=%s' % (exptime, ','.join(cams)),
                                            timeLim=180 + exptime,
                                            getVisit=True)]

        sequence += [SubCmd(actor=enuActor, cmdStr='slit move home') for enuActor in enuActors]

        return sequence

    def start(self, cmd=None):
        QThread.start(self)

    def handleTimeout(self):
        """| Is called when the thread is idle
        """
        pass
