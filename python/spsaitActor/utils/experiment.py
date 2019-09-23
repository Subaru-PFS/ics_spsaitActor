import time
from datetime import datetime as dt

import numpy as np
import spsaitActor.utils.storage as storage
from spsaitActor.utils.logbook import Logbook


class Experiment(object):
    stopMsg = ["""text="command failed: UserWarning('Stop requested') in waitUntil()"""]

    def __init__(self, actor, rawCmd, sequence, seqtype, name, comments, head, tail):
        object.__init__(self)
        self.actor = actor
        self.cmdStr = 'spsait %s' % (rawCmd.replace('name="%s"' % name, '').replace('comments="%s"' % comments, ''))
        self.sequence = sequence
        self.seqtype = seqtype
        self.name = name
        self.comments = comments
        self.head = head
        self.tail = tail

        self.cmdError = ''
        self.dateobs = dt.utcnow().replace(microsecond=0)

        self.dbname = self.getStorage()
        self.id = Logbook.lastExperimentId(dbname=self.dbname) + 1

    @property
    def subCmds(self):
        return self.head + self.sequence + self.tail

    @property
    def visits(self):
        return [subCmd.visit for subCmd in self.subCmds if subCmd.visit != -1]

    @property
    def completion(self):
        completed = [subCmd for subCmd in self.subCmds if subCmd.didFail != -1]
        return 100 * len(completed) / len(self.subCmds)

    @property
    def remainingTime(self):
        completed = [subCmd for subCmd in self.subCmds if subCmd.didFail != -1]
        if not completed:
            return np.nan
        speed = len(completed) / ((dt.utcnow() - self.dateobs).total_seconds())
        return (len(self.subCmds) - len(completed)) / speed

    def inform(self, cmd):
        cmd.inform('experiment=%s,%d,%s,"%s","%s","%s"' % (self.dbname, self.id, self.seqtype, self.cmdStr,
                                                           self.name, self.comments))

    def status(self, cmd):
        cmd.inform('status=%.2f,%d' % (self.completion, self.remainingTime))

    def registerCmds(self, cmd):
        for cmdId, subCmd in enumerate(self.subCmds):
            subCmd.setId(self, cmdId=cmdId)
            subCmd.inform(cmd=cmd)

    def process(self, cmd):
        try:
            for subCmd in (self.head + self.sequence):
                self.processSubCmd(cmd, subCmd=subCmd)

        finally:
            for subCmd in self.tail:
                self.processSubCmd(cmd, subCmd=subCmd, doRaise=False)

            self.store()

    def processSubCmd(self, cmd, subCmd, doRaise=True):
        cmdVar = subCmd.callAndUpdate(cmd=cmd)
        self.status(cmd=cmd)

        if cmdVar.didFail and doRaise:
            self.handleError(cmd=cmd, cmdId=subCmd.id, cmdVar=cmdVar)
            raise RuntimeError('subCmd has failed.. sequence aborted..')

        doStop = self.actor.waitUntil(time.time() + subCmd.tempo)
        if doStop and doRaise:
            self.handleError(cmd=cmd, cmdId=subCmd.id)
            raise RuntimeError('abort sequence requested..')

    def handleError(self, cmd, cmdId, cmdVar=None):
        for id in range(cmdId + 1, len(self.head + self.sequence)):
            self.subCmds[id].didFail = 1
            self.subCmds[id].inform(cmd)

        cmdErrors = self.stopMsg if cmdVar is None else [r.keywords.canonical(delimiter=';') for r in cmdVar.replyList]
        self.cmdError = cmdErrors[-1]

        for cmdError in cmdErrors:
            cmd.warn(cmdError)

    def store(self):
        if self.visits:
            Logbook.newExperiment(dbname=self.dbname,
                                  experimentId=self.id,
                                  visitStart=min(self.visits),
                                  visitEnd=max(self.visits),
                                  seqtype=self.seqtype,
                                  cmdStr=self.cmdStr,
                                  name=self.name,
                                  comments=self.comments,
                                  startdate=self.dateobs.isoformat(),
                                  cmdError=self.cmdError
                                  )

    def getStorage(self):
        try:
            location = storage.locate(seqtype=self.seqtype)
        except KeyError:
            location = storage.guess(subCmds=self.subCmds)

        return location