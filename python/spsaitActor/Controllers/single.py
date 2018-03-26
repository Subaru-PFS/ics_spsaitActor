import logging
import time
from actorcore.QThread import QThread
from functools import partial
import spsaitActor.utils as utils
import numpy as np


class ExpSync(list):
    def __init__(self, actor, cams, imtype, cmd):
        list.__init__(self)
        for cam in cams:
            self.append(CcdThread(actor=actor, cam=cam, imtype=imtype, cmd=cmd))

        self.actor = actor

    def __del__(self):
        self.exit()

    @property
    def ccdActive(self):
        return [ccd for ccd in self if ccd.activated]

    def waitAndHandle(self, state, timeout, ti=0.2, force=False, doRaise=False):
        t0 = time.time()
        while not self.synchronise(state, force=force):

            if (time.time() - t0) > timeout:
                raise Exception('ccd %s timeout' % state)
            if self.actor.doStop:
                self.clearCcd()
                raise Exception('Exposure interrupted by user')
            time.sleep(ti)

        if doRaise:
            raise Exception(doRaise)

        if not self.ccdActive:
            return self.waitAndHandle(state='idle', timeout=180, force=True, doRaise=state)

    def synchronise(self, state, force=False):
        ccdList = self.ccdActive if not force else self

        for ccdThread in ccdList:
            if not ccdThread.reached(state):
                return False

        return True

    def wipeCcd(self, cmd):

        for ccd in self.ccdActive:
            ccd.wipe(cmd)

    def cmdShutters(self, cmd, exptime):
        shutters = {}

        for ccd in self.ccdActive:
            if ccd.smId not in shutters.keys():
                shutters[ccd.smId] = ccd.arm
            else:
                shutters[ccd.smId] += ccd.arm

        for smId, key in shutters.items():
            ShaThread(self.actor, smId, key, cmd, exptime)

    def clearCcd(self):

        for ccd in self.ccdActive:
            ccd.clearExposure()

    def exit(self):
        for ccd in self:
            ccd.exitASAP = True


class ShaThread(QThread):
    shut = {'r': 'red', 'b': '', 'rb': '', 'br': ''}

    def __init__(self, actor, smId, key, cmd, exptime):
        QThread.__init__(self, actor, 'sha%i' % smId, timeout=2)
        self.start()
        shutters = ShaThread.shut[key]
        self.thrCall(actor='enu_sm%i' % smId,
                     cmdStr='shutters expose exptime=%.3f %s' % (exptime, shutters),
                     timeLim=exptime + 60,
                     forUserCmd=cmd)

        self.exitASAP = True

    def thrCall(self, **kwargs):
        self.putMsg(partial(self.actor.cmdr.call, **kwargs))


class CcdThread(QThread):
    def __init__(self, actor, cam, imtype=None, cmd=None):
        QThread.__init__(self, actor, cam, timeout=2)
        self.cam = cam
        self.smId = int(cam[-1])
        self.arm = cam[0]
        self.ccdActor = 'ccd_%s' % cam
        self.enuActor = 'enu_sm%i' % self.smId
        self.imtype = imtype
        self.cmd = cmd
        self.state = None
        self.activated = False

        ccdKeys = self.actor.models[self.ccdActor]
        ccdKeys.keyVarDict['exposureState'].addCallback(self.exposureState)

        enuKeys = self.actor.models['enu_sm%i' % self.smId]
        enuKeys.keyVarDict['exptime'].addCallback(self.read, callNow=False)

        self.start()

    def dateobs(self):
        return self.actor.models['enu_sm%i' % self.smId].keyVarDict['dateobs'].getValue()

    def exposureState(self, keyvar):
        try:
            state = keyvar.getValue()
        except ValueError:
            state = None

        self.state = state

    def wipe(self, cmd):
        self.activated = True
        self.thrCall(actor=self.ccdActor, cmdStr='wipe', timeLim=60, forUserCmd=cmd)

    def read(self, keyvar):
        if not self.activated:
            return
        try:
            exptime = keyvar.getValue()
            dateobs = self.dateobs()

            if np.isnan(exptime):
                self.activated = False
                raise ValueError

        except ValueError:
            return

        self.thrCall(actor=self.ccdActor,
                     cmdStr='read %s exptime=%.3f obstime=%s' % (self.imtype, exptime, dateobs),
                     timeLim=60,
                     forUserCmd=self.cmd)

    def reached(self, state):
        ret = False if self.state != state else True
        return ret

    def callCcd(self, **kwargs):
        cmd = kwargs['forUserCmd']

        cmdVar = self.actor.cmdr.call(**kwargs)

        if cmdVar.didFail:
            print('%s : %s ' % (self.ccdActor, cmdVar.lastReply.canonical()))
            self.activated = False
            try:
                self.actor.processSequence(cmd, self.failure())
                self.state = 'idle'
            except:
                self.state = 'failed'

    def thrCall(self, **kwargs):
        self.putMsg(partial(self.callCcd, **kwargs))

    def clearExposure(self, cmd=False):
        cmd = self.cmd if not cmd else cmd
        cmdVar = self.actor.cmdr.call(actor=self.ccdActor,
                                      cmdStr='clearExposure',
                                      timeLim=60,
                                      forUserCmd=cmd)

    def failure(self):
        sequence = [utils.CmdSeq(self.ccdActor, 'clearExposure'),
                    utils.CmdSeq(self.ccdActor, 'disconnect controller=fee', tempo=10),
                    utils.CmdSeq(self.ccdActor, 'connect controller=fee')]

        return sequence

    def start(self):
        self.activated = True
        QThread.start(self)


class single(QThread):
    def __init__(self, actor, name, loglevel=logging.DEBUG):
        """This sets up the connections to/from the hub, the logger, and the twisted reactor.

        :param actor: spsaitActor
        :param name: controller name
        """
        QThread.__init__(self, actor, name, timeout=2)
        self.logger = logging.getLogger(self.name)
        self.logger.setLevel(loglevel)

    def resetExposure(self):
        self.actor.doStop = False

    def expose(self, cmd, imtype, exptime, cams):
        cams = cams if cams else self.actor.config.get('spsait', 'cams').split(',')

        expSync = ExpSync(actor=self.actor,
                          cams=cams,
                          imtype=imtype,
                          cmd=cmd)

        expSync.wipeCcd(cmd=cmd)
        expSync.waitAndHandle(state='integrating', timeout=90)

        expSync.cmdShutters(cmd=cmd, exptime=exptime)

        expSync.waitAndHandle(state='reading', timeout=60)
        expSync.waitAndHandle(state='idle', timeout=180, force=True)

    def handleTimeout(self):
        """| Is called when the thread is idle
        """
        pass
