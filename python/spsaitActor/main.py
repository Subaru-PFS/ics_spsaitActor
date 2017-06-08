# !/usr/bin/env python

import ConfigParser
import argparse
import logging
import time

import spsaitActor.utils as utils
from actorcore.Actor import Actor
from actorcore.QThread import QThread
from opscore.utility.qstr import qstr
from twisted.internet import reactor


class SpsaitActor(Actor):
    def __init__(self, name, productName=None, configFile=None, logLevel=logging.INFO):
        # This sets up the connections to/from the hub, the logger, and the twisted reactor.
        #
        Actor.__init__(self,
                       name,
                       productName=productName,
                       configFile=configFile,
                       modelNames=['ccd_r1', 'xcu_r1', 'xcu_r0', 'enu', 'dcb'],
                       )

        self.logger.setLevel(logLevel)

        self.everConnected = False

        self.monitors = dict()

        self.statusLoopCB = self.statusLoop

        self.expTime = 1.0
        self.allThreads = {}
        self.boolStop = {}
        self.threadedDev = ["expose", "detalign", "dither", "cryo", "calib", "test"]

        self.createThreads()

    def createThreads(self):
        for name in self.threadedDev:
            thread = QThread(self, name)
            thread.start()
            thread.handleTimeout = self.sleep
            self.allThreads[name] = thread
            self.boolStop[name] = False

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

    def processSequence(self, name, cmd, sequence):
        ti = 0.2
        self.boolStop[name] = False
        e = getattr(utils, "%sException" % name.capitalize())

        for cmdSeq in sequence:
            if self.boolStop[name]:
                raise e
            self.safeCall(**(cmdSeq.build(cmd, name)))
            for i in range(int(cmdSeq.tempo // ti)):
                if self.boolStop[name]:
                    raise e
                time.sleep(ti)
            time.sleep(cmdSeq.tempo % ti)

    def sleep(self):
        pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', default=None, type=str, nargs='?',
                        help='configuration file to use')
    parser.add_argument('--logLevel', default=logging.INFO, type=int, nargs='?',
                        help='logging level')
    parser.add_argument('--name', default='enu', type=str, nargs='?',
                        help='identity')
    args = parser.parse_args()

    theActor = SpsaitActor('spsait',
                           productName='spsaitActor',
                           configFile=args.config,
                           logLevel=args.logLevel)
    theActor.run()


if __name__ == '__main__':
    main()
