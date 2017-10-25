# !/usr/bin/env python

import argparse
import logging
import time
from functools import partial

import actorcore.ICC
from actorcore.QThread import QThread
from twisted.internet import reactor


class SpsaitActor(actorcore.ICC.ICC):
    def __init__(self, name, productName=None, configFile=None, logLevel=logging.INFO):
        # This sets up the connections to/from the hub, the logger, and the twisted reactor.
        #
        self.name = name
        ccd = "ccd"
        xcu = "testa"
        arms = ['blue', 'red']

        self.ccds = ['%s_%s%i' % (ccd, cam[0], self.specId) for cam in arms]
        self.xcus = ['%s_%s%i' % (xcu, cam[0], self.specId) for cam in arms]

        hack = ['xcu_r1'] if self.specId == 0 else []
        self.arm2ccd = dict([(arm, ccd) for arm, ccd in zip(arms, self.ccds)])
        self.arm2xcu = dict([(arm, xcu) for arm, xcu in zip(arms, self.xcus)])
        self.ccd2arm = dict([(ccd, arm) for arm, ccd in zip(arms, self.ccds)])

        actorcore.ICC.ICC.__init__(self,
                                   name,
                                   productName=productName,
                                   configFile=configFile,
                                   modelNames=['enu', 'dcb'] + hack + self.xcus + self.ccds)

        self.logger.setLevel(logLevel)

        self.everConnected = False

        self.monitors = dict()

        self.statusLoopCB = self.statusLoop

        self.expTime = 1.0
        self.boolStop = {}
        self.createThreads()
        self.createBool()

    @property
    def specId(self):
        return int(self.name.split('_sm')[-1])

    @property
    def jobsDone(self):
        return False if True in [thread.showOn for thread in [self.controllers[ccd] for ccd in self.ccds]] else True

    def createThreads(self):
        for ccd in self.ccds:
            thread = QThread(self, ccd, timeout=2)
            thread.start()
            thread.handleTimeout = partial(self.sleep, thread)
            self.controllers[ccd] = thread

    def createBool(self):
        for controller in self.controllers.itervalues():
            self.boolStop[controller] = False

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
                raise Exception("%s has failed" % cmdStr.upper())
            else:
                time.sleep(10)
                self.safeCall(**kwargs)

    def processSequence(self, name, cmd, sequence, ti=0.2, doReset=True):

        e = Exception("%s stop requested" % name.capitalize())
        if doReset:
            self.boolStop[name] = False

        for cmdSeq in sequence:
            if self.boolStop[name]:
                raise e
            self.safeCall(**(cmdSeq.build(cmd, name)))
            for i in range(int(cmdSeq.tempo // ti)):
                if self.boolStop[name]:
                    raise e
                time.sleep(ti)
            time.sleep(cmdSeq.tempo % ti)

    def connectionMade(self):
        if self.everConnected is False:
            logging.info("Attaching Controllers")
            self.allControllers = [s.strip() for s in self.config.get(self.name, 'startingControllers').split(',')]
            self.attachAllControllers()
            self.everConnected = True
            logging.info("All Controllers started")

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
        cmd = cmd if cmd is not None else self.bcast

        if controller not in self.monitors:
            self.monitors[controller] = 0

        running = self.monitors[controller] > 0
        self.monitors[controller] = period

        if (not running) and period > 0:

            cmd.warn('text="starting %gs loop for %s"' % (self.monitors[controller], controller))
            self.statusLoopCB(controller)
        else:
            cmd.warn('text="adjusted %s loop to %gs"' % (controller, self.monitors[controller]))

    def sleep(self, thread):
        thread.showOn = False


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
