# !/usr/bin/env python

from opscore.utility.qstr import qstr
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

        specIds = [i for i in range(1, 5)]
        allcams = ['b%i' % i for i in specIds] + ['r%i' % i for i in specIds]

        self.ccds = ['ccd_%s' % cam for cam in allcams]
        self.cam2ccd = dict([(cam, ccd) for cam, ccd in zip(allcams, self.ccds)])

        self.enus = ['enu_sm%i' % i for i in specIds]

        actorcore.ICC.ICC.__init__(self,
                                   name,
                                   productName=productName,
                                   configFile=configFile,
                                   modelNames=['dcb'] + self.ccds + self.enus)

        self.logger.setLevel(logLevel)

        self.everConnected = False
        self.monitors = dict()
        self.statusLoopCB = self.statusLoop

        self.doStop = False

    def safeCall(self, doRetry=False, **kwargs):

        cmd = kwargs["forUserCmd"]
        kwargs["timeLim"] = 300 if "timeLim" not in list(kwargs.keys()) else kwargs["timeLim"]

        # cmdStr = '%s %s' % (kwargs["actor"], kwargs["cmdStr"])

        cmdVar = self.cmdr.call(**kwargs)

        # stat = cmdVar.lastReply.canonical().split(" ", 4)[-1]
        if cmdVar.didFail:
            # cmd.warn(stat)
            if not doRetry or self.doStop:
                raise Exception('')

                # raise Exception("%s has failed" % cmdStr.upper())
            else:
                time.sleep(10)
                self.safeCall(**kwargs)

    def processSequence(self, cmd, sequence, ti=0.2):

        for id, cmdSeq in enumerate(sequence):
            self.safeCall(**(cmdSeq.build(cmd)))

            for i in range(int(cmdSeq.tempo // ti)):
                if self.doStop:
                    raise Exception('Stop requested')
                time.sleep(ti)

            time.sleep(cmdSeq.tempo % ti)

    def strTraceback(self, e):

        oneLiner = self.cmdTraceback(e)
        return qstr("command failed: %s" % oneLiner)

    def abortShutters(self, cmd):
        for enu in self.enus:
            cmdVar = self.cmdr.call(actor=enu, cmdStr="shutters abort", forUserCmd=cmd)

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
