import logging
import time
from functools import partial

import numpy as np
import spsaitActor.utils as utils
from actorcore.QThread import QThread


class expose(QThread):
    def __init__(self, actor, name, loglevel=logging.DEBUG):
        """This sets up the connections to/from the hub, the logger, and the twisted reactor.

        :param actor: spsaitActor
        :param name: controller name
        """
        QThread.__init__(self, actor, name, timeout=2)
        self.logger = logging.getLogger(self.name)
        self.logger.setLevel(loglevel)
        self.ccdState = {}
        self.boolStop = False

    @property
    def ccdExposing(self):
        return dict([(key, (bool, value)) for key, (bool, value) in self.ccdState.iteritems() if bool])

    def operCcd(self, kwargs):

        cmd = kwargs["forUserCmd"]
        kwargs["timeLim"] = 300 if "timeLim" not in kwargs.iterkeys() else kwargs["timeLim"]
        ccd = kwargs["actor"]

        cmdVar = self.actor.cmdr.call(**kwargs)
        stat = cmdVar.lastReply.canonical().split(" ", 4)[-1]

        if cmdVar.didFail:
            cmd.warn(stat)
            self.ccdState[ccd] = False, "didFail"
            self.actor.processSequence(ccd, cmd, utils.FailExposure(ccd))

    def expose(self, cmd, expType, exptime, arms):
        enuKeys = self.actor.models['enu']
        cmdCall = self.actor.safeCall
        shutters = 'red' if ('red' in arms and 'blue' not in arms) else ''

        if exptime <= 0:
            raise Exception("exptime must be positive")

        [state, mode, position] = enuKeys.keyVarDict['shutters'].getValue()
        if not (state == "IDLE" and position == "close") or self.boolStop:
            raise Exception("Shutters are not in position")

        for arm in arms:
            ccd = self.actor.arm2ccd[arm]
            self.ccdState[ccd] = True, None
            self.actor.controllers[ccd].putMsg(partial(self.operCcd, {'actor': ccd,
                                                                      'cmdStr': "wipe",
                                                                      'timeLim': 60,
                                                                      'forUserCmd': cmd}))

        self.waitAndHandle(state='integrating', timeout=20)

        cmdCall(actor='enu', cmdStr="shutters expose exptime=%.3f %s" % (exptime, shutters), timeLim=exptime + 60,
                forUserCmd=cmd)
        dateobs = enuKeys.keyVarDict['dateobs'].getValue()
        exptime = enuKeys.keyVarDict['exptime'].getValue()

        if np.isnan(exptime):
            raise Exception("Shutters expose did not occur as expected (interlock ?) Aborting ... ")

        for ccd in self.ccdExposing:
            cmdStr = "read %s exptime=%.3f obstime=%s" % (expType, exptime, dateobs)
            self.actor.controllers[ccd].putMsg(partial(self.operCcd, {'actor': ccd,
                                                                      'cmdStr': cmdStr,
                                                                      'timeLim': 300,
                                                                      'forUserCmd': cmd}))

        self.waitAndHandle(state='reading', timeout=60)
        self.waitAndHandle(state='idle', timeout=180)

    def checkState(self, state):
        for key, (bool, value) in self.ccdState.iteritems():
            if bool and value != state:
                return False
        return True

    def waitAndHandle(self, state, timeout):
        t0 = time.time()

        while not (self.checkState(state) and self.ccdExposing):

            if (time.time() - t0) > timeout:
                raise Exception("ccd %s timeout" % state)
            if self.boolStop:
                raise Exception("ccd exposure interrupted by user")
            if not self.ccdExposing:
                raise Exception("ccd %s has failed" % state)

    def handleTimeout(self):
        """| Is called when the thread is idle
        """
        pass
