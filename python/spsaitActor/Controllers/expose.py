import logging

from actorcore.QThread import QThread
from spsaitActor.sequencing import Sequence


class expose(QThread):
    def __init__(self, actor, name, loglevel=logging.DEBUG):
        """This sets up the connections to/from the hub, the logger, and the twisted reactor.

        :param actor: spsaitActor
        :param name: controller name
        """
        QThread.__init__(self, actor, name, timeout=2)
        self.logger = logging.getLogger(self.name)
        self.logger.setLevel(loglevel)

    def arcs(self, exptype, exptime, duplicate, cams):
        cams = 'cams=%s' % ','.join(cams) if cams else ''
        seq = Sequence()

        seq.addSubCmd(actor='sps',
                      cmdStr='expose %s exptime=%.2f %s' % (exptype, exptime, cams),
                      timeLim=120 + exptime,
                      duplicate=duplicate)

        return seq

    def start(self, cmd=None):
        QThread.start(self)

    def handleTimeout(self):
        """| Is called when the thread is idle
        """
        pass
