import logging
import time
from actorcore.QThread import QThread
from functools import partial
import spsaitActor.utils as utils
from datetime import datetime as dt
import numpy as np
import sqlite3


def storeAitDB(engine, sqlRequest):
    conn = sqlite3.connect(engine)
    c = conn.cursor()

    try:
        c.execute(sqlRequest)
        conn.commit()

    except sqlite3.IntegrityError:
        pass


class Exposure(object):
    def __init__(self, actor, cams, visit, imtype, exptime, cmd):
        object.__init__(self)
        self.actor = actor
        self.visit = visit
        self.imtype = imtype
        self.exptime = exptime
        self.cmd = cmd
        self.ccds = []

        self.start = dt.utcnow()

        for cam in cams:
            self.ccds.append(CcdThread(actor=actor, imtype=imtype, visit=visit, cmd=cmd, cam=cam))

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

    def store(self):
        site = 'L'
        visit = self.visit
        exposureId = 'PFLA%s' % (str(visit).zfill(6))
        obsdate = self.start.isoformat()
        exptime = self.exptime
        exptype = self.imtype
        quality = 'OK'
        sqlRequest = """INSERT INTO Exposure VALUES ('%s','%s', %i, '%s', %.3f, '%s', '%s');""" % (exposureId,
                                                                                                   site,
                                                                                                   visit,
                                                                                                   obsdate,
                                                                                                   exptime,
                                                                                                   exptype,
                                                                                                   quality)

        storeAitDB(engine=self.actor.dbEnginePath, sqlRequest=sqlRequest)

    def info(self):
        conn = sqlite3.connect(self.actor.dbEnginePath)
        c = conn.cursor()
        c.execute(
            '''select visit,spectrograph,arm,quality from Exposure inner join CamExposure on Exposure.exposureId=CamExposure.exposureId where visit=%i''' % self.visit)
        return c.fetchall()

    def exit(self):
        for ccd in self.ccds:
            ccd.exit()


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
    def __init__(self, actor, imtype, visit, cmd, cam):
        self.cam = cam
        self.smId = int(cam[-1])
        self.arm = cam[0]
        self.ccdActor = 'ccd_%s' % cam
        self.enuActor = 'enu_sm%i' % self.smId
        self.actor = actor
        self.imtype = imtype
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
                     cmdStr='read %s visit=%i exptime=%.3f obstime=%s' % (self.imtype, self.visit, exptime, dateobs),
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
        sqlRequest = """INSERT INTO CamExposure VALUES ('%s','%s', %i, '%s');""" % (camExposureId,
                                                                                    exposureId,
                                                                                    self.smId,
                                                                                    self.arm)
        #
        storeAitDB(engine=self.actor.dbEnginePath, sqlRequest=sqlRequest)
        self.isLogged = True

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

    def resetExposure(self):
        self.actor.doStop = False

    def expose(self, cmd, imtype, exptime, cams):
        cams = cams if cams else self.actor.config.get('spsait', 'cams').split(',')
        visit = self.actor.getSeqno(cmd=cmd)
        exposure = Exposure(actor=self.actor,
                            cams=cams,
                            visit=visit,
                            imtype=imtype,
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

        for visit, spectrograph, arm, quality in exposure.info():
            cmd.inform('camExposure=%i,%i,%s,%s' % (visit, spectrograph, arm, quality))

    def start(self, cmd=None):
        QThread.start(self)

    def handleTimeout(self):
        """| Is called when the thread is idle
        """
        pass
