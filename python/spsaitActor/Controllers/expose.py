import logging

from actorcore.QThread import QThread
from spsaitActor.sequencing import SubCmd


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

        sequence = duplicate * [SubCmd(actor='spsait',
                                       cmdStr='single %s exptime=%.2f %s' % (exptype, exptime, cams),
                                       timeLim=180 + exptime,
                                       getVisit=True)]

        return sequence

    def start(self, cmd=None):
        QThread.start(self)

    def handleTimeout(self):
        """| Is called when the thread is idle
        """
        pass
