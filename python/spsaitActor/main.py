# !/usr/bin/env python

import ConfigParser
import argparse
import logging
import time
from functools import partial

import numpy as np
import spsaitActor.utils as utils
from actorcore.Actor import Actor
from actorcore.QThread import QThread
from opscore.utility.qstr import qstr
from twisted.internet import reactor


class SpsaitActor(Actor):
    def __init__(self, name, productName=None, configFile=None, logLevel=logging.INFO):
        # This sets up the connections to/from the hub, the logger, and the twisted reactor.
        #
        self.name = name
        ccd = "ccd"
        xcu = "xcu"
        arms = ['blue', 'red']

        self.ccds = ['%s_%s%i' % (ccd, cam[0], self.specId) for cam in arms]
        self.xcus = ['%s_%s%i' % (xcu, cam[0], self.specId) for cam in arms]

        self.arm2ccd = dict([(arm, ccd) for arm, ccd in zip(arms, self.ccds)])
        self.ccd2arm = dict([(ccd, arm) for arm, ccd in zip(arms, self.ccds)])

        Actor.__init__(self,
                       name,
                       productName=productName,
                       configFile=configFile,
                       modelNames=['enu', 'dcb'] + self.xcus + self.ccds)

        self.logger.setLevel(logLevel)

        self.everConnected = False

        self.monitors = dict()

        self.statusLoopCB = self.statusLoop

        self.expTime = 1.0
        self.allThreads = {}
        self.boolStop = {}
        self.ccdState = {}
        self.threadedDev = ["expose", "detalign", "dither", "cryo", "calib", "test"] + self.ccds

        self.createThreads()
        self.attachCallbacks()

    @property
    def specId(self):
        return int(self.name.split('_sm')[-1])

    @property
    def ccdDict(self):
        return dict([(key, (bool, value)) for key, (bool, value) in self.ccdState.iteritems() if bool])

    @property
    def stopExposure(self):
        return self.boolStop["expose"]

    def checkState(self, state):
        for key, (bool, value) in self.ccdState.iteritems():
            if bool and value != state:
                return False
        return True

    def attachCallbacks(self):
        for ccd in self.ccds:
            ccdKeys = self.models[ccd]
            ccdKeys.keyVarDict['exposureState'].addCallback(partial(self.exposureState, ccd))

    def exposureState(self, ccd, kwargs):
        ccdKeys = self.models[ccd]
        try:
            state = ccdKeys.keyVarDict['exposureState'].getValue()
        except ValueError:
            state = None

        bool = self.ccdState[ccd][0] if ccd in self.ccdState.iterkeys() else True
        self.ccdState[ccd] = bool, state

    def createThreads(self):
        for name in self.threadedDev:
            thread = QThread(self, name)
            thread.start()
            thread.handleTimeout = self.sleep
            self.allThreads[name] = thread
            self.boolStop[name] = False

    def safeCall(self, **kwargs):

        cmd = kwargs["forUserCmd"]
        kwargs["timeLim"] = 300 if "timeLim" not in kwargs.iterkeys() else kwargs["timeLim"]

        cmdStr = '%s %s' % (kwargs["actor"], kwargs["cmdStr"])

        doRetry = kwargs.pop("doRetry", None)
        keyStop = kwargs.pop("keyStop", None)

        cmdVar = self.cmdr.call(**kwargs)

        stat = cmdVar.lastReply.canonical().split(" ", 4)[-1]

        if cmdVar.didFail:
            cmd.warn(stat)
            if not doRetry or self.boolStop[keyStop]:
                raise Exception("%s has failed" % cmdStr)
            else:
                time.sleep(5)
                self.safeCall(**kwargs)

    def operCcd(self, kwargs):

        cmd = kwargs["forUserCmd"]
        kwargs["timeLim"] = 300 if "timeLim" not in kwargs.iterkeys() else kwargs["timeLim"]
        ccd = kwargs["actor"]

        cmdVar = self.cmdr.call(**kwargs)
        stat = cmdVar.lastReply.canonical().split(" ", 4)[-1]

        if cmdVar.didFail:
            cmd.warn(stat)
            self.ccdState[ccd] = False, "didFail"
            self.processSequence(ccd, cmd, utils.FailExposure(ccd))

    def processSequence(self, name, cmd, sequence):
        ti = 0.2
        self.boolStop[name] = False

        e = Exception("%s stop requested" % name.capitalize())

        for cmdSeq in sequence:
            if self.boolStop[name]:
                raise e
            self.safeCall(**(cmdSeq.build(cmd, name)))
            for i in range(int(cmdSeq.tempo // ti)):
                if self.boolStop[name]:
                    raise e
                time.sleep(ti)
            time.sleep(cmdSeq.tempo % ti)

    def expose(self, cmd, expType, exptime, arms):
        enuKeys = self.models['enu']
        cmdCall = self.safeCall
        shutters = 'red' if ('red' in arms and 'blue' not in arms) else ''

        if exptime <= 0:
            raise Exception("exptime must be positive")

        [state, mode, position] = enuKeys.keyVarDict['shutters'].getValue()
        if not (state == "IDLE" and position == "close") or self.stopExposure:
            raise Exception("Shutters are not in position")

        for arm in arms:
            ccd = self.arm2ccd[arm]
            self.ccdState[ccd] = True, None
            self.allThreads[ccd].putMsg(partial(self.operCcd, {'actor': ccd,
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

        for ccd in self.ccdDict:
            cmdStr = "read %s exptime=%.3f obstime=%s" % (expType, exptime, dateobs)
            self.allThreads[ccd].putMsg(partial(self.operCcd, {'actor': ccd,
                                                               'cmdStr': cmdStr,
                                                               'timeLim': 300,
                                                               'forUserCmd': cmd}))

        self.waitAndHandle(state='reading', timeout=60)
        self.waitAndHandle(state='idle', timeout=180)

    def waitAndHandle(self, state, timeout):
        t0 = time.time()

        while not (self.checkState(state) and self.ccdDict):

            if (time.time() - t0) > timeout:
                raise Exception("ccd %s timeout" % state)
            if self.stopExposure:
                raise Exception("ccd exposure interrupted by user")
            if not self.ccdDict:
                raise Exception("ccd %s has failed" % state)

    def sleep(self):
        pass

    def reloadConfiguration(self, cmd):
        logging.info("reading config file %s", self.configFile)

        try:
            newConfig = ConfigParser.ConfigParser()
            newConfig.read(self.configFile)
        except Exception, e:
            if cmd:
                cmd.fail('text=%s' % (qstr("failed to read the configuration file, old config untouched: %s" % (e))))
            raise

        self.config = newConfig
        cmd.inform('sections=%08x,%r' % (id(self.config),
                                         self.config))

    def statusLoop(self, controller):
        try:
            self.callCommand("%s status" % (controller))
        except:
            pass

        if self.monitors[controller] > 0:
            reactor.callLater(self.monitors[controller],
                              self.statusLoopCB,
                              controller)

    def monitor(self, controller, period, cmd=None):
        if controller not in self.monitors:
            self.monitors[controller] = 0

        running = self.monitors[controller] > 0
        self.monitors[controller] = period

        if (not running) and period > 0:
            cmd.warn('text="starting %gs loop for %s"' % (self.monitors[controller],
                                                          controller))
            self.statusLoopCB(controller)
        else:
            cmd.warn('text="adjusted %s loop to %gs"' % (controller, self.monitors[controller]))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', default=None, type=str, nargs='?',
                        help='configuration file to use')
    parser.add_argument('--logLevel', default=logging.INFO, type=int, nargs='?',
                        help='logging level')
    parser.add_argument('--name', default='spsait', type=str, nargs='?',
                        help='identity')
    args = parser.parse_args()

    theActor = SpsaitActor(args.name,
                           productName='spsaitActor',
                           configFile=args.config,
                           logLevel=args.logLevel)
    theActor.run()


if __name__ == '__main__':
    main()
