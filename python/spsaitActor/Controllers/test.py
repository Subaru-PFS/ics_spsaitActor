import logging

from actorcore.QThread import QThread
from spsaitActor.utils import CmdSeq

class test(QThread):
    def __init__(self, actor, name, loglevel=logging.DEBUG):
        """This sets up the connections to/from the hub, the logger, and the twisted reactor.

        :param actor: spsaitActor
        :param name: controller name
        """
        QThread.__init__(self, actor, name, timeout=2)
        self.logger = logging.getLogger(self.name)
        self.logger.setLevel(loglevel)

    def test(self, arm):
        xcu = self.actor.arm2xcu[arm]
        sequence = [CmdSeq('enu', "slit status", tempo=2),
                    CmdSeq('enu', "rexm status", tempo=2),
                    CmdSeq(xcu, "motors status", tempo=2),
                    CmdSeq(xcu, "cooler status", tempo=2),
                    CmdSeq('enu', "slit status", tempo=2),
                    CmdSeq('enu', "rexm status", tempo=2),
                    CmdSeq(xcu, "motors status", tempo=2),
                    CmdSeq(xcu, "cooler status", tempo=2),
                    ]
        return sequence

    def handleTimeout(self):
        """| Is called when the thread is idle
        """
        pass
