# !/usr/bin/env python

import argparse
import logging
import time
import actorcore.ICC
from spsaitActor.utils.experiment import Experiment


class SpsaitActor(actorcore.ICC.ICC):
    def __init__(self, name, productName=None, configFile=None, logLevel=logging.INFO):
        # This sets up the connections to/from the hub, the logger, and the twisted reactor.
        #
        self.name = name
        self.enus = ['enu_sm%i' % (i + 1) for i in range(4)]

        actorcore.ICC.ICC.__init__(self,
                                   name,
                                   productName=productName,
                                   configFile=configFile,
                                   modelNames=self.enus)

        self.everConnected = False
        self.current = None
        self.doStop = False

        self.logger.setLevel(logLevel)

    @property
    def specToAlign(self):
        return self.config.getint('spsait', 'specToAlign')

    def processSequence(self, cmd, sequence, seqtype, name, comments, head=None, tail=None):
        head = [] if head is None else head
        tail = [] if tail is None else tail

        self.current = Experiment(self, rawCmd=cmd.rawCmd, sequence=sequence, seqtype=seqtype,
                                  name=name, comments=comments, head=head, tail=tail)

        self.current.inform(cmd=cmd)
        self.current.registerCmds(cmd=cmd)
        self.current.process(cmd=cmd)
        self.current = None

    def getStatus(self, cmd):
        if self.current is None:
            return
        self.current.inform(cmd=cmd)
        self.current.status(cmd=cmd)

    def waitUntil(self, end, ti=0.01):
        while time.time() < end:
            if self.doStop:
                break
            time.sleep(ti)

        return self.doStop

    def resetSequence(self):
        self.doStop = False

    def connectionMade(self):
        if self.everConnected is False:
            logging.info("Attaching Controllers")
            self.allControllers = [s.strip() for s in self.config.get(self.name, 'startingControllers').split(',')]
            self.attachAllControllers()
            self.everConnected = True
            logging.info("All Controllers started")


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
