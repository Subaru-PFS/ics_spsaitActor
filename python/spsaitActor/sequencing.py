from datetime import datetime as dt

import spsaitActor.storage as storage
from opscore.utility.qstr import qstr
from spsaitActor.logbook import Logbook


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
    def __init__(self, rawCmd, sequence, seqtype, name, comments, head, tail):
        object.__init__(self)
        self.rawCmd = rawCmd
        self.cmdStr = rawCmd.replace('name="%s"' % name, '').replace('comments="%s"' % comments, '')
        self.sequence = sequence
        self.seqtype = seqtype
        self.name = name
        self.comments = comments
        self.head = head
        self.tail = tail

        self.cmdError = ''
        self.visits = []
        self.startdate = dt.utcnow().replace(microsecond=0).isoformat()

        self.dbname = self.getStorage()
        self.id = Logbook.lastExperimentId(dbname=self.dbname) + 1

        self.registerCmds()

    @property
    def subCmds(self):
        return self.head + self.sequence + self.tail

    @property
    def info(self):
        return '%s,%i,%s,"%s","%s","%s"' % (self.dbname,
                                            self.id,
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
            Logbook.newExperiment(dbname=self.dbname,
                                  experimentId=self.id,
                                  visitStart=min(self.visits),
                                  visitEnd=max(self.visits),
                                  seqtype=self.seqtype,
                                  cmdStr=self.cmdStr,
                                  name=self.name,
                                  comments=self.comments,
                                  startdate=self.startdate,
                                  cmdError=self.cmdError
                                  )

    def getStorage(self):
        try:
            location = storage.locate(seqtype=self.seqtype)
        except KeyError:
            location = storage.guess(subCmds=self.subCmds)

        return location


class Sequence(list):
    def __init__(self, *args):
        list.__init__(self, *args)

    def addSubCmd(self, actor, cmdStr, duplicate=1, timeLim=120, tempo=5.0):
        for i in range(duplicate):
            self.append(SubCmd(actor=actor, cmdStr=cmdStr, timeLim=timeLim, tempo=tempo))


class FocusFlats(Sequence):
    exptime = 1.0
    attenuator = 20

    def __init__(self, cams):
        Sequence.__init__(self)
        self.addSubCmd(actor='dcb', cmdStr='arc on=halogen attenuator=%d' % FocusFlats.attenuator, timeLim=300)

        self.addSubCmd(actor='spsait',
                       cmdStr='single flat exptime=%.2f cams=%s' % (FocusFlats.exptime, ','.join(cams)),
                       timeLim=120)

        self.addSubCmd(actor='dcb', cmdStr='arc off=halogen')
