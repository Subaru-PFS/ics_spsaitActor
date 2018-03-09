from __future__ import division
from builtins import str
from builtins import zip
from builtins import range

import logging

import numpy as np
from actorcore.QThread import QThread
from spsaitActor.utils import CmdSeq


class slitalign(QThread):
    def __init__(self, actor, name, loglevel=logging.DEBUG):
        """This sets up the connections to/from the hub, the logger, and the twisted reactor.

        :param actor: spsaitActor
        :param name: controller name
        """
        QThread.__init__(self, actor, name, timeout=2)
        self.logger = logging.getLogger(self.name)
        self.logger.setLevel(loglevel)

    def throughfocus(self, seqNumber, nbImage, exptime, slitLow, slitUp, nbBackground):

        enuKeys = self.actor.models['enu'].keyVarDict
        start = [slitLow] + list(enuKeys["slit"])[3:]
        end = [slitUp] + list(enuKeys["slit"])[3:]
        slitStart = " ".join(["%s = %.5f" % (key, val) for key, val in zip(['X', 'Y', 'Z', 'U', 'V', 'W'], start)])
        slitEnd = " ".join(["%s = %.5f" % (key, val) for key, val in zip(['X', 'Y', 'Z', 'U', 'V', 'W'], end)])

        offset = 12
        linear = np.ones(nbImage - 1) * (slitUp - slitLow) / (nbImage - 1)
        coeff = offset + (np.arange(nbImage - 1) - ((nbImage - 1)/ 2)) ** 2
        k = (sum(coeff * linear)/ (slitUp - slitLow))
        coeff = (coeff/ k)
        step = coeff * linear

        sequence = [CmdSeq('afl', 'switch off'), CmdSeq('enu', "slit move absolute %s" % slitStart)]

        for j in range(nbBackground):
            sequence.append(CmdSeq('sac', "background fname=%s exptime=%.2f" % (self.getFilename("BCK", seqNumber, j),
                                                                                exptime)))

        sequence += [CmdSeq('afl', 'switch on'),
                     CmdSeq('sac', "expose fname=%s exptime=%.2f" % (self.getFilename("EXP", seqNumber, 1),
                                                                     exptime))]

        for i in range(nbImage - 2):
            sequence += [CmdSeq('enu', "slit move relative X=%.5f" % step[i]),
                         CmdSeq('sac', "expose fname=%s exptime=%.2f" % (self.getFilename("EXP", seqNumber, i+2),
                                                                         exptime))]

        sequence += [CmdSeq('enu', "slit move absolute %s" % slitEnd),
                     CmdSeq('sac', "expose fname=%s exptime=%.2f" % (self.getFilename("EXP", seqNumber, nbImage),
                                                                     exptime))]

        return sequence

    def getFilename(self, exptype, seqNumber, expId):

        return "FCA%i_SEQ%s_%s%s.fits" % (self.actor.specId,
                                          str(seqNumber).zfill(3),
                                          exptype,
                                          str(expId).zfill(3))


    def handleTimeout(self):
        """| Is called when the thread is idle
        """
        pass
