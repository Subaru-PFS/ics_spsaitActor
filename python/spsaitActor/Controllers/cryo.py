import logging
import time

from actorcore.QThread import QThread
from spsaitActor.utils import CmdSeq, xcuData



class cryo(QThread):
    def __init__(self, actor, name, loglevel=logging.DEBUG):
        """This sets up the connections to/from the hub, the logger, and the twisted reactor.

        :param actor: spsaitActor
        :param name: controller name
        """
        QThread.__init__(self, actor, name, timeout=2)
        self.logger = logging.getLogger(self.name)
        self.logger.setLevel(loglevel)
        self.xcuDatas = {}
        self.attachCallbacks()

    @property
    def roughGauge(self):
        model = self.actor.models['xcu_r1']
        keyvar = model['roughGauge1']
        try:
            val = keyvar.getValue()
        except ValueError:
            val = None
        return val

    def startPumps(self, xcuActor, ionPumpsOn, turboOn, gvOpen):

        sequence = [CmdSeq(xcuActor, "gatevalve open", timeLim=90)] if (turboOn and gvOpen) else []
        sequence += ([CmdSeq(xcuActor, "ionpump on", timeLim=90)] if ionPumpsOn else [])
        sequence += self.sample(xcuActor)

        return sequence

    def stopPumps(self, xcuActor, ionPumpsOn, gvOpen):
        sequence = [CmdSeq(xcuActor, "ionpump off", timeLim=90)] if ionPumpsOn else []
        sequence += ([CmdSeq(xcuActor, "gatevalve close")] if gvOpen else [])
        sequence += self.sample(xcuActor)

        return sequence

    def sample(self, xcuActor, cmd=None, keys=None):
        keys = ["turbo", "gauge", "cooler", "gatevalve", "ionpump"] if keys is None else keys
        sequence = [CmdSeq(xcuActor, "%s status" % key, doRetry=True, tempo=1.0) for key in keys]
        if cmd is not None:
            self.actor.processSequence(self.name, cmd, sequence)
        else:
            return sequence

    def startRoughing(self):
        sequence = [CmdSeq("dcb", "aten switch on channel=roughpump")]
        return sequence

    def stopRoughing(self):
        sequence = [CmdSeq("dcb", "aten switch off channel=roughpump")]
        return sequence

    def startTurbo(self, xcuActor):
        sequence = [CmdSeq(xcuActor, "turbo start")]
        return sequence

    def stopTurbo(self, xcuActor):
        sequence = [CmdSeq(xcuActor, "turbo stop")]
        return sequence

    def openGV(self, xcuActor):
        sequence = [CmdSeq(xcuActor, "gatevalve open")]
        return sequence

    def closeGV(self, xcuActor):
        sequence = [CmdSeq(xcuActor, "gatevalve close")]
        return sequence

    def regeneration(self, xcuActor):
        sequence = [CmdSeq(xcuActor, "ionpump off"),
                    CmdSeq(xcuActor, "cooler off"),
                    CmdSeq(xcuActor, "heaters ccd power=100"),
                    CmdSeq(xcuActor, "heaters spider power=100")]
        return sequence

    def attachCallbacks(self):
        for xcu in self.actor.xcus:
            self.xcuDatas[xcu] = xcuData(self.actor, xcu)

    def handleTimeout(self):
        """| Is called when the thread is idle
        """
        pass

    def xcuKeys(self, arm):
        xcuActor = self.actor.arm2xcu[arm]
        return xcuActor, self.actor.models[xcuActor]
