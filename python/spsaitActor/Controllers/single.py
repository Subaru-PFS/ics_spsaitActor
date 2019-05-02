import logging
import time
from datetime import datetime as dt
from datetime import timedelta
from functools import partial

import numpy as np
from actorcore.QThread import QThread
from spsaitActor.logbook import Logbook
from spsaitActor.sequencing import SubCmd


class CcdList(object):
    def __init__(self, actor, cams, cmd):
        object.__init__(self)
        self.actor = actor
        self.cmd = cmd
        self.cams = cams
        self.ccds = []

        self.start = dt.utcnow()
        self.timeout = 10

    def __del__(self):
        self.exit()

    @property
    def ccdActive(self):
        return [ccd for ccd in self.ccds if ccd.activated]

    def filesExist(self):
        time.sleep(1)
        return True in [ccd.isLogged for ccd in self.ccds]

    def waitAndHandle(self, state, timeout, ti=0.2, force=False, doRaise=False):
        t0 = time.time()
        while not self.synchronise(state, force=force):

            if (time.time() - t0) > timeout:
                raise Exception('ccd %s timeout' % state)
            if not state == 'idle' and self.actor.doStop:
                self.clearCcd()
                raise Exception('Exposure interrupted by user')
            time.sleep(ti)

        if doRaise:
            raise Exception(doRaise)

        if not self.ccdActive:
            return self.waitAndHandle(state='idle', timeout=180, force=True,
                                      doRaise='no ccd active, cannot reach %s' % state)

    def synchronise(self, state, force=False):
        ccdList = self.ccdActive if not force else self.ccds

        for ccdThread in ccdList:
            if not ccdThread.reached(state):
                return False

        return True

    def clearCcd(self):
        for ccd in self.ccdActive:
            ccd.clearExposure()

    def exit(self):
        for ccd in self.ccds:
            ccd.exit()


class Exposure(CcdList):
    def __init__(self, actor, cams, visit, exptype, exptime, cmd):
        object.__init__(self)
        self.visit = visit
        self.exptype = exptype
        self.exptime = exptime

        self.start = dt.utcnow()

        CcdList.__init__(self, actor=actor, cmd=cmd, cams=cams)

        for cam in cams:
            self.ccds.append(CcdThread(actor=actor, exptype=exptype, visit=visit, cmd=cmd, cam=cam))

    def wipeCcd(self, cmd):

        for ccd in self.ccdActive:
            ccd.wipeCmd(cmd)

    def readCcd(self, cmd, exptime):

        for ccd in self.ccdActive:
            ccd.readCmd(cmd, exptime=exptime)

    def cmdShutters(self, cmd, exptime):
        shutters = {}

        for ccd in self.ccdActive:
            if ccd.smId not in shutters.keys():
                shutters[ccd.smId] = ccd.arm
            else:
                shutters[ccd.smId] += ccd.arm

        for smId, key in shutters.items():
            ShaThread(self.actor, smId, key, cmd, exptime)

    def store(self):
        Logbook.newExposure(exposureId='PFLA%s' % (str(self.visit).zfill(6)),
                            site='L',
                            visit=self.visit,
                            obsdate=self.start.isoformat(),
                            exptime=self.exptime,
                            exptype=self.exptype,
                            )
        return self.visit



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
    armNum = {'1': 'b',
              '2': 'r',
              '3': 'n',
              '4': 'm'}

    def __init__(self, actor, exptype, visit, cmd, cam):
        self.cam = cam
        self.smId = int(cam[-1])
        self.arm = cam[0]
        self.ccdActor = 'ccd_%s' % cam
        self.enuActor = 'enu_sm%i' % self.smId
        self.actor = actor
        self.exptype = exptype
        self.visit = visit
        self.cmd = cmd

        QThread.__init__(self, self.actor, cam, timeout=2)

        self.state = None
        self.isLogged = False
        self.activated = False
        self.darktime = None

        ccdKeys = self.actor.models[self.ccdActor]
        ccdKeys.keyVarDict['exposureState'].addCallback(self.exposureState, callNow=False)
        ccdKeys.keyVarDict['filepath'].addCallback(self.storeCamExposure, callNow=False)

        enuKeys = self.actor.models[self.enuActor]
        enuKeys.keyVarDict['exptime'].addCallback(self.read, callNow=False)

        self.start()

    def dateobs(self):
        return self.actor.models[self.enuActor].keyVarDict['dateobs'].getValue()

    def exposureState(self, keyvar):
        try:
            state = keyvar.getValue()
        except ValueError:
            state = None

        self.state = state

        if state == 'integrating':
            self.darktime = dt.utcnow()

    def wipeCmd(self, cmd):
        self.activated = True
        self.thrCall(actor=self.ccdActor, cmdStr='wipe', timeLim=60, forUserCmd=cmd)

    def readCmd(self, cmd, exptime):
        while self.darktime is None:
            pass

        self.waitUntil(start=self.darktime, exptime=exptime)

        dateobs = self.darktime.isoformat()
        darktime = (dt.utcnow() - self.darktime).total_seconds()

        self.thrCall(actor=self.ccdActor,
                     cmdStr='read %s visit=%i exptime=%.3f darktime=%.3f obstime=%s' % (self.exptype, self.visit,
                                                                                        exptime, darktime, dateobs),
                     timeLim=60,
                     forUserCmd=cmd)

    def read(self, keyvar):
        if not (self.activated and self.state == 'integrating'):
            return
        try:
            exptime = keyvar.getValue()
            if np.isnan(exptime):
                raise ValueError

            dateobs = self.dateobs()
            darktime = (dt.utcnow() - self.darktime).total_seconds()

        except ValueError:
            return

        self.thrCall(actor=self.ccdActor,
                     cmdStr='read %s visit=%i exptime=%.3f darktime=%.3f obstime=%s' % (self.exptype, self.visit,
                                                                                        exptime, darktime, dateobs),
                     timeLim=60,
                     forUserCmd=self.cmd)

    def reached(self, state):
        ret = False if self.state != state else True
        return ret

    def callCcd(self, **kwargs):
        cmd = kwargs['forUserCmd']

        cmdVar = self.actor.cmdr.call(**kwargs)

        if cmdVar.didFail:
            self.actor.logger.warning('%s : %s ' % (self.ccdActor, cmdVar.lastReply.canonical()))
            self.activated = False
            try:
                self.failureRoutine(cmd=cmd)
            except Exception as e:
                self.actor.logger.warning(self.actor.strTraceback(e))

            self.state = 'idle'

    def thrCall(self, **kwargs):
        self.putMsg(partial(self.callCcd, **kwargs))

    def clearExposure(self, cmd=False):

        cmd = self.cmd if not cmd else cmd
        cmdVar = self.actor.cmdr.call(actor=self.ccdActor,
                                      cmdStr='clearExposure',
                                      timeLim=60,
                                      forUserCmd=cmd)

        self.activated = False

    def failureRoutine(self, cmd):
        sequence = [SubCmd(actor=self.ccdActor, cmdStr='clearExposure'),
                    SubCmd(actor=self.ccdActor, cmdStr='disconnect controller=fee', tempo=10),
                    SubCmd(actor=self.ccdActor, cmdStr='connect controller=fee')]

        for subCmd in sequence:
            self.actor.safeCall(**(subCmd.build(cmd)))

        return sequence

    def start(self):
        self.activated = True
        QThread.start(self)

    def storeCamExposure(self, keyvar):

        rootDir, dateDir, filename = keyvar.getValue()

        camExposureId = filename.split('.fits')[0]
        exposureId = camExposureId[:-2]
        arm = self.armNum[camExposureId[-1]]

        Logbook.newCamExposure(camExposureId=camExposureId,
                               exposureId=exposureId,
                               smId=self.smId,
                               arm=arm)

        self.isLogged = True

    def waitUntil(self, start, exptime, ti=0.001):
        """| Temporization, check every 0.01 sec for a user abort command.

        :param cmd: current command,
        :param exptime: exposure time,
        :type exptime: float
        :raise: Exception("Exposure aborted by user") if the an abort command has been received
        """
        tlim = start + timedelta(seconds=exptime)

        while dt.utcnow() < tlim:
            time.sleep(ti)

        return dt.utcnow()

    def exit(self):
        """ Signal our thread in .run() that it should exit. """
        ccdKeys = self.actor.models[self.ccdActor]
        enuKeys = self.actor.models[self.enuActor]

        ccdKeys.keyVarDict['exposureState'].removeCallback(self.exposureState)
        ccdKeys.keyVarDict['filepath'].removeCallback(self.storeCamExposure)
        enuKeys.keyVarDict['exptime'].removeCallback(self.read)

        self.exitASAP = True


class single(QThread):
    def __init__(self, actor, name, loglevel=logging.DEBUG):
        """This sets up the connections to/from the hub, the logger, and the twisted reactor.

        :param actor: spsaitActor
        :param name: controller name
        """
        QThread.__init__(self, actor, name, timeout=2)
        self.logger = logging.getLogger(self.name)
        self.logger.setLevel(loglevel)

    def expose(self, cmd, exptype, exptime, cams):
        cams = cams if cams else self.actor.cams
        visit = self.actor.getSeqno(cmd=cmd)
        exposure = Exposure(actor=self.actor,
                            cams=cams,
                            visit=visit,
                            exptype=exptype,
                            exptime=exptime,
                            cmd=cmd)

        exposure.wipeCcd(cmd=cmd)
        exposure.waitAndHandle(state='integrating', timeout=90)

        exposure.cmdShutters(cmd=cmd, exptime=exptime)

        exposure.waitAndHandle(state='reading', timeout=60 + exptime)
        exposure.waitAndHandle(state='idle', timeout=180, force=True)

        start = time.time()
        while not exposure.filesExist():
            if time.time() - start > exposure.timeout:
                raise Exception('no exposure has been created')

        visit = exposure.store()
        return visit

    def calibExposure(self, cmd, cams, exptype, exptime):
        cams = cams if cams else self.actor.cams
        visit = self.actor.getSeqno(cmd=cmd)
        exposure = Exposure(actor=self.actor,
                            cams=cams,
                            visit=visit,
                            exptype=exptype,
                            exptime=exptime,
                            cmd=cmd)

        exposure.wipeCcd(cmd=cmd)
        exposure.readCcd(cmd=cmd, exptime=exptime)

        exposure.waitAndHandle(state='reading', timeout=60 + exptime)
        exposure.waitAndHandle(state='idle', timeout=180, force=True)

        start = time.time()
        while not exposure.filesExist():
            if time.time() - start > exposure.timeout:
                raise Exception('no exposure has been created')

        visit = exposure.store()
        return visit

    def start(self, cmd=None):
        QThread.start(self)

    def handleTimeout(self):
        """| Is called when the thread is idle
        """
        pass
