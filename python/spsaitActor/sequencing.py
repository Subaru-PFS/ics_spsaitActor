from opscore.utility.qstr import qstr
from spsaitActor.logbook import Logbook
from datetime import datetime as dt

class CmdFail(ValueError):
    def __init__(self, *args):
        ValueError.__init__(self, *args)


class SubCmd(object):
    def __init__(self, actor, cmdStr, timeLim=120, tempo=5.0):
        object.__init__(self)
        self.finished = False
        self.id = 0
        self.actor = actor
        self.cmdStr = cmdStr
        self.timeLim = timeLim
        self.tempo = tempo

    @property
    def fullCmd(self):
        return '%s %s' % (self.actor, self.cmdStr)

    def setId(self, id):
        self.id = id

    def build(self, cmd):
        return dict(actor=self.actor,
                    cmdStr=self.cmdStr,
                    forUserCmd=cmd,
                    timeLim=self.timeLim)

    def inform(self, cmd, didFail, returnStr):
        cmd.inform('subCommand=%i,%i,%s' % (self.id, didFail, qstr(returnStr)))
        self.finished = True


class Experiment(object):
    def __init__(self, head, sequence, tail, name, seqtype, rawCmd, comments):
        object.__init__(self)
        self.id = Logbook.lastExperimentId() + 1
        self.startdate = dt.utcnow().replace(microsecond=0).isoformat()
        self.head = head
        self.sequence = sequence
        self.tail = tail
        self.name = name
        self.seqtype = seqtype
        self.rawCmd = rawCmd
        self.cmdStr = rawCmd.replace('name="%s"' % name, '').replace('comments="%s"' % comments, '')
        self.comments = comments
        self.cmdError = ''
        self.visits = []

        self.registerCmds()

    @property
    def subCmds(self):
        return self.head + self.sequence + self.tail

    @property
    def info(self):
        return '%i,%s,"%s","%s","%s"' % (self.id,
                                         self.seqtype,
                                         self.name,
                                         self.comments,
                                         ';'.join([sub.fullCmd for sub in self.subCmds]))

    def registerCmds(self):
        for id, subCmd in enumerate(self.subCmds):
            subCmd.setId(id=id)

    def addVisits(self, newVisits):
        newVisits = [int(visit) for visit in newVisits]
        self.visits.extend(newVisits)

    def handleError(self, cmd, error):
        for unfinished in [subCmd for subCmd in self.head + self.sequence if not subCmd.finished]:
            unfinished.inform(cmd=cmd, didFail=True, returnStr='')

        self.cmdError = error

    def store(self):
        if self.visits:
            Logbook.newExperiment(experimentId=self.id,
                                  visitStart=min(self.visits),
                                  visitEnd=max(self.visits),
                                  seqtype=self.seqtype,
                                  cmdStr=self.cmdStr,
                                  name=self.name,
                                  comments=self.comments,
                                  startdate=self.startdate,
                                  cmdError=self.cmdError
                                  )


class Sequence(list):
    def __init__(self, *args):
        list.__init__(self, *args)

    def addSubCmd(self, actor, cmdStr, duplicate=1, timeLim=120, tempo=5.0):
        for i in range(duplicate):
            self.append(SubCmd(actor=actor, cmdStr=cmdStr, timeLim=timeLim, tempo=tempo))
