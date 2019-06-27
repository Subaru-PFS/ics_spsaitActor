# !/usr/bin/env python

import argparse
import logging
import time

import actorcore.ICC
from spsaitActor.sequencing import Experiment, CmdFail, Sequence


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
        self.doStop = False

        self.logger.setLevel(logLevel)

    @property
    def specToAlign(self):
        return self.config.getint('spsait', 'specToAlign')

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

        self.waitUntil(end=(time.time() + subCmd.tempo), doRaise=doRaise)

    def recordVisit(self, cmdVar, experiment):
        if cmdVar.didFail:
            return ''

        lastKeywords = cmdVar.replyList[-1].keywords
        newVisits = lastKeywords['visit'].values
        experiment.addVisits(newVisits=newVisits)
        return ';'.join(newVisits)

    def processSequence(self, cmd, sequence, seqtype, name, comments, head=None, tail=None):
        head = [] if head is None else head
        tail = [] if tail is None else tail

        experiment = Experiment(rawCmd=cmd.rawCmd, sequence=sequence, seqtype=seqtype, name=name, comments=comments,
                                head=head, tail=tail)
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

    def subCmdList(self, cmdList):
        subCmds = Sequence()

        for cmd in cmdList:
            actor, cmdStr = cmd.split(' ', 1)
            subCmds.addSubCmd(actor=actor, cmdStr=cmdStr)

        return subCmds

    def abortShutters(self, cmd):
        for enu in self.enus:
            cmdVar = self.cmdr.call(actor=enu, cmdStr="exposure abort", forUserCmd=cmd)

    def resetSequence(self):
        self.doStop = False

    def waitUntil(self, end, doRaise=True):
        while time.time() < end:
            if self.doStop and doRaise:
                raise UserWarning('Stop requested')

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
