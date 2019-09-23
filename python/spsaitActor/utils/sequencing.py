from spsaitActor.utils import cleanStr


class SubCmd(object):
    def __init__(self, actor, cmdStr, timeLim=300, tempo=5.0):
        object.__init__(self)
        self.actor = actor
        self.cmdStr = cmdStr
        self.timeLim = timeLim
        self.tempo = tempo
        self.didFail = -1
        self.id = 0
        self.cleanReply = ''
        self.visit = -1

    @property
    def fullCmd(self):
        return ('%s %s' % (self.actor, self.cmdStr)).strip()

    def setId(self, experiment, cmdId):
        self.experiment = experiment
        self.id = cmdId

    def build(self, cmd):
        return dict(actor=self.actor,
                    cmdStr=self.cmdStr,
                    forUserCmd=cmd,
                    timeLim=self.timeLim)

    def callAndUpdate(self, cmd):
        cmdVar = self.experiment.actor.cmdr.call(**(self.build(cmd=cmd)))
        self.didFail = cmdVar.didFail
        self.cleanReply = cleanStr(cmdVar.replyList[-1].keywords.canonical(delimiter=';'))
        self.visit = self.getVisit(cmdVar)

        self.inform(cmd=cmd)
        return cmdVar

    def inform(self, cmd):
        cmd.inform('subCommand=%d,%d,"%s",%d,"%s"' % (self.experiment.id,
                                                      self.id,
                                                      self.fullCmd,
                                                      self.didFail,
                                                      self.cleanReply))

    def getVisit(self, cmdVar):
        visit = -1
        if not self.didFail:
            try:
                visit = int(cmdVar.replyList[-1].keywords['visit'].values[0])
            except KeyError:
                pass

        return visit


class CmdList(list):
    def __init__(self, cmdList=None):
        list.__init__(self)
        cmdList = [] if cmdList is None else cmdList

        for cmd in cmdList:
            actor, cmdStr = cmd.split(' ', 1)
            self.addSubCmd(actor=actor, cmdStr=cmdStr)

    def addSubCmd(self, actor, cmdStr, duplicate=1, timeLim=300, tempo=5.0):
        for i in range(duplicate):
            self.append(SubCmd(actor=actor, cmdStr=cmdStr, timeLim=timeLim, tempo=tempo))
