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
    def __init__(self, cmd, subCmds, exptype, name, comments):
        object.__init__(self)
        self.cmd = cmd
        self.id = Logbook.getExperimentId()
        self.subCmds = subCmds
        self.exptype = exptype
        self.name = name
        self.comments = comments

    @property
    def info(self):
        return '%i,%s,"%s","%s","%s"' % (self.id,
                                         self.exptype,
                                         self.name,
                                         self.comments,
                                         ';'.join([sub.fullCmd for sub in self.subCmds]))