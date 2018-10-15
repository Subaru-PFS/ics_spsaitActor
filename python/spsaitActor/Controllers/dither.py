import logging
from collections import OrderedDict

import numpy as np
from actorcore.QThread import QThread
from spsaitActor.sequencing import Sequence, SubCmd


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
        cams = cams if cams else self.actor.cams
        specIds = list(OrderedDict.fromkeys([int(cam[1]) for cam in cams]))
        enuActors = ['enu_sm%i' % specId for specId in specIds]

        seq = Sequence()

        seq += [SubCmd(actor=enuActor, cmdStr='slit move home') for enuActor in enuActors]
        seq.addSubCmd(actor='spsait',
                      cmdStr='single flat exptime=%.2f cams=%s' % (exptime, ','.join(cams)),
                      timeLim=120 + exptime,
                      duplicate=duplicate)

        specIds = list(OrderedDict.fromkeys([int(cam[1]) for cam in cams]))
        enuActors = ['enu_sm%i' % specId for specId in specIds]

        for enuActor in enuActors:
            posAbsolute = [0, 0, -nbPosition * shift, 0, 0, 0]
            posAbsolute = ' '.join(['%s=%.5f' % (name, value) for name, value in zip(dither.posName, posAbsolute)])
            seq.addSubCmd(actor=enuActor, cmdStr='slit move absolute %s' % posAbsolute)

        seq.addSubCmd(actor='spsait',
                      cmdStr='single flat exptime=%.2f cams=%s' % (exptime, ','.join(cams)),
                      timeLim=120 + exptime,
                      duplicate=duplicate)

        for i in range(2 * nbPosition + 1):
            seq += [SubCmd(actor=enuActor, cmdStr="slit dither pix=%.5f" % shift) for enuActor in enuActors]
            seq.addSubCmd(actor='spsait',
                          cmdStr='single flat exptime=%.2f cams=%s' % (exptime, ','.join(cams)),
                          timeLim=120 + exptime,
                          duplicate=duplicate)

        seq += [SubCmd(actor=enuActor, cmdStr='slit move home') for enuActor in enuActors]
        seq.addSubCmd(actor='spsait',
                      cmdStr='single flat exptime=%.2f cams=%s' % (exptime, ','.join(cams)),
                      timeLim=120 + exptime,
                      duplicate=duplicate)

        return seq

    def ditherpsf(self, exptime, cams, shift, duplicate):
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

        seq = Sequence()

        for position in positions:
            posAbsolute = ' '.join(['%s=%.5f' % (name, value) for name, value in zip(dither.posName, position)])

            seq += [SubCmd(actor=enuActor, cmdStr='slit move absolute %s' % posAbsolute) for enuActor in enuActors]
            seq.addSubCmd(actor='spsait',
                          cmdStr='single arc exptime=%.2f cams=%s' % (exptime, ','.join(cams)),
                          timeLim=120 + exptime,
                          duplicate=duplicate)

        seq += [SubCmd(actor=enuActor, cmdStr='slit move home') for enuActor in enuActors]

        return seq

    def start(self, cmd=None):
        QThread.start(self)

    def handleTimeout(self):
        """| Is called when the thread is idle
        """
        pass
