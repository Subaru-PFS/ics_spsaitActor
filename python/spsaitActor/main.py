# !/usr/bin/env python

import argparse
import logging
import time

import actorcore.ICC
from spsaitActor.sequencing import Experiment, CmdFail
from twisted.internet import reactor


class SpsaitActor(actorcore.ICC.ICC):
    def __init__(self, name, productName=None, configFile=None, logLevel=logging.INFO):
        # This sets up the connections to/from the hub, the logger, and the twisted reactor.
        #
        self.name = name

        specIds = [i + 1 for i in range(1)]
        allcams = ['b%i' % i for i in specIds] + ['r%i' % i for i in specIds]

        self.ccds = ['ccd_%s' % cam for cam in allcams]
        self.cam2ccd = dict([(cam, ccd) for cam, ccd in zip(allcams, self.ccds)])

        self.enus = ['enu_sm%i' % i for i in specIds]

        actorcore.ICC.ICC.__init__(self,
                                   name,
                                   productName=productName,
                                   configFile=configFile,
                                   modelNames=['dcb', 'seqno'] + self.ccds + self.enus)

        self.logger.setLevel(logLevel)

        self.everConnected = False
        self.monitors = dict()
        self.statusLoopCB = self.statusLoop

        self.doStop = False

    @property
    def specToAlign(self):
        return self.config.getint('spsait', 'specToAlign')

    @property
    def cams(self):
        return self.config.get('spsait', 'cams').split(',')

    def safeCall(self, doRaise=True, doRetry=False, **kwargs):

        cmd = kwargs["forUserCmd"]
        kwargs["timeLim"] = 300 if "timeLim" not in kwargs.keys() else kwargs["timeLim"]

        cmdVar = self.cmdr.call(**kwargs)

        if cmdVar.didFail and doRaise:
            reply = cmdVar.replyList[-1]
            raise CmdFail("actor=%s %s" % (reply.header.actor, reply.keywords.canonical(delimiter=';')))
        return cmdVar

    def processSubCmd(self, cmd, experiment, subCmd, doRaise=True):
        cmdVar = self.safeCall(doRaise=doRaise, **(subCmd.build(cmd)))

        try:
            returnStr = self.recordVisit(cmdVar=cmdVar, experiment=experiment)
        except KeyError:
            returnStr = ''

        subCmd.inform(cmd=cmd, didFail=cmdVar.didFail, returnStr=returnStr)

        self.waitUntil(end=(time.time() + subCmd.tempo))

    def recordVisit(self, cmdVar, experiment):
        if cmdVar.didFail:
            return ''

        lastKeywords = cmdVar.replyList[-1].keywords
        newVisits = lastKeywords['newVisits'].values
        experiment.addVisits(newVisits=newVisits)
        return ';'.join(newVisits)

    def processSequence(self, cmd, sequence, seqtype, name='', comments='', head=None, tail=None):
        head = [] if head is None else head
        tail = [] if tail is None else tail
        experiment = Experiment(head=head, sequence=sequence, tail=tail, name=name, seqtype=seqtype, rawCmd=cmd.rawCmd,
                                comments=comments)
        cmd.inform('newExperiment=%s' % experiment.info)

        try:
            for subCmd in (head + sequence):
                self.processSubCmd(cmd=cmd, experiment=experiment, subCmd=subCmd)

        except Exception as e:
            experiment.handleError(cmd=cmd, error=self.strTraceback(e))
            raise

        finally:
            for subCmd in tail:
                self.processSubCmd(cmd=cmd, experiment=experiment, subCmd=subCmd, doRaise=False)
            experiment.store()

    def getSeqno(self, cmd):
        cmdVar = self.cmdr.call(actor='seqno',
                                cmdStr='getVisit',
                                forUserCmd=cmd,
                                timeLim=10)

        if cmdVar.didFail or not cmdVar.isDone:
            raise ValueError('getVisit has failed')

        visit = cmdVar.lastReply.keywords['visit'].values[0]

        return int(visit)

    def abortShutters(self, cmd):
        for enu in self.enus:
            cmdVar = self.cmdr.call(actor=enu, cmdStr="shutters abort", forUserCmd=cmd)

    def resetSequence(self):
        self.doStop = False

    def waitUntil(self, end):
        while time.time() < end:
            if self.doStop:
                raise UserWarning('Stop requested')

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
