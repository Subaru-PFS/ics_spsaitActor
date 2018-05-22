import logging
import time
from actorcore.QThread import QThread
from functools import partial
import spsaitActor.utils as utils
from datetime import datetime as dt
import numpy as np


class CcdList(object):
    def __init__(self, actor, cams, cmd):
        object.__init__(self)
        self.actor = actor
        self.cmd = cmd
        self.cams = cams
        self.ccds = []

        self.start = dt.utcnow()

    def __del__(self):
        self.exit()

    @property
    def ccdActive(self):
        return [ccd for ccd in self.ccds if ccd.activated]

    @property
    def exist(self):
        return True in [ccd.isLogged for ccd in self.ccds]

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

    def store(self):
        utils.Logbook.newExposure(exposureId='PFLA%s' % (str(self.visit).zfill(6)),
                                  site='L',
                                  visit=self.visit,
                                  obsdate=self.start.isoformat(),
                                  exptime=self.exptime,
                                  exptype=self.exptype,
                                  quality='OK')

    def info(self):
        return utils.Logbook.getInfo(visit=self.visit)

class Biases(CcdList):
    def __init__(self, actor, cams, cmd):

        CcdList.__init__(self, actor=actor, cmd=cmd, cams=cams)

        for cam in cams:
            self.ccds.append(Bias(actor=actor, cmd=cmd, cam=cam))


class Darks(CcdList):
    def __init__(self, actor, cams, cmd, exptime):
        CcdList.__init__(self, actor=actor, cmd=cmd, cams=cams)

        for cam in cams:
            self.ccds.append(Dark(actor=actor, cmd=cmd, exptime=exptime, cam=cam))


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

        ccdKeys = self.actor.models[self.ccdActor]
        ccdKeys.keyVarDict['exposureState'].addCallback(self.exposureState)
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

    def wipe(self, cmd):
        self.activated = True
        self.thrCall(actor=self.ccdActor, cmdStr='wipe', timeLim=60, forUserCmd=cmd)

    def read(self, keyvar):
        if not self.activated:
            return
        try:
            exptime = keyvar.getValue()
            if np.isnan(exptime):
                raise ValueError

            dateobs = self.dateobs()

        except ValueError:
            return

        self.thrCall(actor=self.ccdActor,
                     cmdStr='read %s visit=%i exptime=%.3f obstime=%s' % (self.exptype, self.visit, exptime, dateobs),
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

        self.activated = False

    def failure(self):
        sequence = [utils.CmdSeq(self.ccdActor, 'clearExposure'),
                    utils.CmdSeq(self.ccdActor, 'disconnect controller=fee', tempo=10),
                    utils.CmdSeq(self.ccdActor, 'connect controller=fee')]

        return sequence

    def start(self):
        self.activated = True
        QThread.start(self)

    def storeCamExposure(self, keyvar):

        rootDir, dateDir, filename = keyvar.getValue()

        camExposureId = filename.split('.fits')[0]
        exposureId = camExposureId[:-2]

        utils.Logbook.newCamExposure(camExposureId=camExposureId,
                                     exposureId=exposureId,
                                     smId=self.smId,
                                     arm=self.arm)

        self.isLogged = True

    def exit(self):
        """ Signal our thread in .run() that it should exit. """
        ccdKeys = self.actor.models[self.ccdActor]
        enuKeys = self.actor.models[self.enuActor]

        ccdKeys.keyVarDict['exposureState'].removeCallback(self.exposureState)
        ccdKeys.keyVarDict['filepath'].removeCallback(self.storeCamExposure)
        enuKeys.keyVarDict['exptime'].removeCallback(self.read)

        self.exitASAP = True


class CalibThread(CcdThread):
    def __init__(self, actor, exptype, exptime, cmd, cam):
        self.exptime = exptime
        self.dateobs = dt.utcnow().isoformat()

        CcdThread.__init__(self, actor=actor, exptype=exptype, visit=None, cmd=cmd, cam=cam)
        self.activated = True

    def storeCamExposure(self, keyvar):
        rootDir, dateDir, filename = keyvar.getValue()

        self.visit = int(filename[4:10])

        CcdThread.storeCamExposure(self, keyvar)
        utils.Logbook.newExposure(exposureId=filename[:10],
                                  site='L',
                                  visit=self.visit,
                                  obsdate=self.dateobs,
                                  exptime=self.exptime,
                                  exptype=self.exptype,
                                  quality='OK')

        visit, exptype, spectrograph, arm, quality = self.info()[0]
        self.cmd.inform('camExposure=%i,%s,%i,%s,%s' % (visit, exptype, spectrograph, arm, quality))


    def info(self):
        return utils.Logbook.getInfo(visit=self.visit)


class Bias(CalibThread):
    def __init__(self, actor, cmd, cam):
        CalibThread.__init__(self, actor=actor, exptype='bias', exptime=0, cmd=cmd, cam=cam)

        self.thrCall(actor=self.ccdActor,
                     cmdStr='expose nbias=1',
                     timeLim=60,
                     forUserCmd=cmd)


class Dark(CalibThread):
    def __init__(self, actor, cmd, exptime, cam):
        CalibThread.__init__(self, actor=actor, exptype='dark', exptime=exptime, cmd=cmd, cam=cam)

        self.thrCall(actor=self.ccdActor,
                     cmdStr='expose darks=%.2f' % exptime,
                     timeLim=60+exptime,
                     forUserCmd=cmd)
        


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

    def expose(self, cmd, exptype, exptime, cams):
        cams = cams if cams else self.actor.config.get('spsait', 'cams').split(',')
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

        exposure.waitAndHandle(state='reading', timeout=60)
        exposure.waitAndHandle(state='idle', timeout=180, force=True)

        if not exposure.exist:
            raise Exception('no exposure has been created')

        exposure.store()

        for visit, exptype, spectrograph, arm, quality in exposure.info():
            cmd.inform('camExposure=%i,%s,%i,%s,%s' % (visit, exptype, spectrograph, arm, quality))

    def bias(self, cmd, cams):
        cams = cams if cams else self.actor.config.get('spsait', 'cams').split(',')

        biases = Biases(actor=self.actor,
                        cams=cams,
                        cmd=cmd)

        biases.waitAndHandle(state='reading', timeout=90)
        biases.waitAndHandle(state='idle', timeout=180, force=True)

        if not biases.exist:
            raise Exception('no exposure has been created')

    def dark(self, cmd, exptime, cams):
        cams = cams if cams else self.actor.config.get('spsait', 'cams').split(',')

        darks = Darks(actor=self.actor,
                       cams=cams,
                       cmd=cmd,
                       exptime=exptime)

        darks.waitAndHandle(state='reading', timeout=90)
        darks.waitAndHandle(state='idle', timeout=180, force=True)

        if not darks.exist:
            raise Exception('no exposure has been created')

    def start(self, cmd=None):
        QThread.start(self)

    def handleTimeout(self):
        """| Is called when the thread is idle
        """
        pass
