import logging

from actorcore.QThread import QThread
from spsaitActor.utils import CmdSeq

class cryo(QThread):
    def __init__(self, actor, name, loglevel=logging.DEBUG):
        """This sets up the connections to/from the hub, the logger, and the twisted reactor.

        :param actor: spsaitActor
        :param name: controller name
        """
        QThread.__init__(self, actor, name, timeout=2)
        self.logger = logging.getLogger(self.name)
        self.logger.setLevel(loglevel)

    def leakback(self, xcuActor, duration):

        seqClosing = [CmdSeq(xcuActor, "gauge status"),
                      CmdSeq(xcuActor, "gatevalve close", tempo=5),
                      CmdSeq(xcuActor, "gatevalve status")]

        seqCheck = [CmdSeq(xcuActor, "gauge status", tempo=duration * 60),
                    CmdSeq(xcuActor, "gatevalve status"),
                    CmdSeq(xcuActor, "gauge status"),
                    CmdSeq(xcuActor, "turbo status")]

        seqOpening = [CmdSeq(xcuActor, "gatevalve open", tempo=5),
                      CmdSeq(xcuActor, "gatevalve status")]

        return seqClosing, seqCheck, seqOpening


    def handleTimeout(self):
        """| Is called when the thread is idle
        """
        pass
