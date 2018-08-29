from spsaitActor.logbook import Logbook


class SubCmd(object):
    def __init__(self, actor, cmdStr, timeLim=600, doRetry=False, tempo=5.0, getVisit=False):
        object.__init__(self)
        self.actor = actor
        self.cmdStr = cmdStr
        self.timeLim = timeLim
        self.doRetry = doRetry
        self.tempo = tempo
        self.getVisit = getVisit

    @property
    def fullCmd(self):
        return '%s %s' % (self.actor, self.cmdStr)

    def build(self, cmd):
        return dict(actor=self.actor,
                    cmdStr=self.cmdStr,
                    forUserCmd=cmd,
                    timeLim=self.timeLim,
                    doRetry=self.doRetry)


class Experiment(object):
    def __init__(self, subCmds, name, seqtype, rawCmd, comments):
        object.__init__(self)
        self.id = Logbook.lastExperimentId() + 1
        self.subCmds = subCmds
        self.name = name
        self.seqtype = seqtype
        self.rawCmd = rawCmd
        self.cmdStr = rawCmd.replace('name="%s"' % name, '').replace('comments="%s"' % comments, '').strip()
        self.comments = comments
        self.visits = []

    @property
    def info(self):
        return '%i,%s,"%s","%s","%s"' % (self.id,
                                         self.seqtype,
                                         self.name,
                                         self.comments,
                                         ';'.join([sub.fullCmd for sub in self.subCmds]))

    def addVisits(self, newVisits):
        newVisits = [int(visit) for visit in newVisits]
        self.visits.extend(newVisits)

    def store(self):
        if self.visits:
            Logbook.newExperiment(experimentId=self.id,
                                  name=self.name,
                                  visitStart=min(self.visits),
                                  visitEnd=max(self.visits),
                                  seqtype=self.seqtype,
                                  cmdStr=self.cmdStr,
                                  comments=self.comments
                                  )
