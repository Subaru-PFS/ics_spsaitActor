import logging
import time
from functools import partial

import numpy as np
from actorcore.QThread import QThread

import spsaitActor.utils as utils


class CcdStatus(object):
    def __init__(self):
        object.__init__(self)
        self.activated = False
        self.state = None

    def reached(self, state, force=False):
        if force:
            if self.state == "failed":
                return True
            if self.state != state:
                return False
        else:
            if self.activated and self.state != state:
                return False
        return True


class expose(QThread):
    def __init__(self, actor, name, loglevel=logging.DEBUG):
        """This sets up the connections to/from the hub, the logger, and the twisted reactor.

        :param actor: spsaitActor
        :param name: controller name
        """
        QThread.__init__(self, actor, name, timeout=2)
        self.logger = logging.getLogger(self.name)
        self.logger.setLevel(loglevel)
        self.ccdStatus = {}
        self.cmdCcd = []
        self.attachCallbacks()

    @property
    def boolStop(self):
        return self.actor.boolStop[self.name]

    @property
    def ccdActive(self):
        return dict([(key, ccdstatus) for key, ccdstatus in self.cmdCcd if ccdstatus.activated])

    def attachCallbacks(self):
        for ccd in self.actor.ccds:
            self.ccdStatus[ccd] = CcdStatus()
            ccdKeys = self.actor.models[ccd]
            ccdKeys.keyVarDict['exposureState'].addCallback(self.exposureState)

    def exposureState(self, keyvar):

        try:
            state = keyvar.getValue()
        except ValueError:
            state = None

        ccd = keyvar.actor
        self.ccdStatus[ccd].state = state

    def operCcd(self, kwargs):

        cmd = kwargs["forUserCmd"]
        kwargs["timeLim"] = 300 if "timeLim" not in kwargs.iterkeys() else kwargs["timeLim"]
        ccd = kwargs["actor"]

        cmdVar = self.actor.cmdr.call(**kwargs)
        stat = cmdVar.lastReply.canonical().split(" ", 4)[-1]

        if cmdVar.didFail:
            cmd.warn(stat)
            self.ccdStatus[ccd].activated = False
            try:
                self.actor.processSequence(ccd, cmd, utils.FailExposure(ccd))
                self.ccdStatus[ccd].state = "idle"
            except:
                self.ccdStatus[ccd].state = "failed"

    def expose(self, cmd, expType, exptime, arms):
        self.cmdCcd = []
        enuKeys = self.actor.models['enu']
        cmdCall = self.actor.safeCall
        shutters = 'red' if ('red' in arms and 'blue' not in arms) else ''

        if exptime <= 0:
            raise Exception("exptime must be positive")

        [state, mode, position] = enuKeys.keyVarDict['shutters'].getValue()
        if not (state == "IDLE" and position == "close"):
            raise Exception("Shutters are not in position")

        for arm in arms:
            ccd = self.actor.arm2ccd[arm]
            self.ccdStatus[ccd].activated = True
            self.cmdCcd.append((ccd, self.ccdStatus[ccd]))
            self.actor.controllers[ccd].putMsg(partial(self.operCcd, {'actor': ccd,
                                                                      'cmdStr': "wipe",
                                                                      'timeLim': 60,
                                                                      'forUserCmd': cmd}))

        self.waitAndHandle(state='integrating', timeout=90)

        cmdCall(actor='enu', cmdStr="shutters expose exptime=%.3f %s" % (exptime, shutters), timeLim=exptime + 60,
                forUserCmd=cmd)
        dateobs = enuKeys.keyVarDict['dateobs'].getValue()
        exptime = enuKeys.keyVarDict['exptime'].getValue()

        if np.isnan(exptime):
            raise Exception("Shutters expose did not occur as expected (interlock ?) Aborting ... ")

        for ccd in self.ccdActive:
            cmdStr = "read %s exptime=%.3f obstime=%s" % (expType, exptime, dateobs)
            self.actor.controllers[ccd].putMsg(partial(self.operCcd, {'actor': ccd,
                                                                      'cmdStr': cmdStr,
                                                                      'timeLim': 300,
                                                                      'forUserCmd': cmd}))

        self.waitAndHandle(state='reading', timeout=60)
        self.waitAndHandle(state='idle', timeout=180, force=True)

    def synchronise(self, state, force=False):
        for key, ccdstatus in self.cmdCcd:
            if not ccdstatus.reached(state, force=force):
                return False
        return True

    def waitAndHandle(self, state, timeout, ti=0.2, force=False, doRaise=False):
        t0 = time.time()

        while not self.synchronise(state, force=force):

            if (time.time() - t0) > timeout:
                raise Exception("ccd %s timeout" % state)
            if self.boolStop:
                raise Exception("ccd exposure interrupted by user")
            time.sleep(ti)

        if doRaise:
            raise Exception("ccd %s has failed" % doRaise)

        if not bool(self.ccdActive):
            return self.waitAndHandle(state='idle', timeout=180, force=True, doRaise=state)

    def resetExposure(self):
        self.actor.boolStop[self.name] = False

    def handleTimeout(self):
        """| Is called when the thread is idle
        """
        pass
