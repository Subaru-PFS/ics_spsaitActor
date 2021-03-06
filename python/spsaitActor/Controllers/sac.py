import logging

from actorcore.QThread import QThread
from spsaitActor.utils.sequencing import CmdList


class sac(QThread):
    def __init__(self, actor, name, loglevel=logging.DEBUG):
        """This sets up the connections to/from the hub, the logger, and the twisted reactor.

        :param actor: spsaitActor
        :param name: controller name
        """
        QThread.__init__(self, actor, name, timeout=2)
        self.logger = logging.getLogger(self.name)
        self.logger.setLevel(loglevel)

    def expose(self, exptime, exptype, duplicate):

        seq = CmdList()
        seq.addSubCmd(actor='sac',
                      cmdStr='ccd %s exptime=%.2f' % (exptype, exptime),
                      duplicate=duplicate,
                      timeLim=60 + exptime)
        return seq

    def sacalign(self, exptime, positions, focus, duplicate):
        seq = CmdList()
        seq.addSubCmd(actor='sac', cmdStr='move detector=%.2f abs' % focus)

        for position in positions:
            seq.addSubCmd(actor='sac',
                          cmdStr='move penta=%.2f abs' % position)

            seq.addSubCmd(actor='sac',
                          cmdStr='ccd expose exptime=%.2f' % exptime,
                          duplicate=duplicate,
                          timeLim=60 + exptime)
        return seq

    def sacTF(self, exptime, positions, duplicate):
        seq = CmdList()

        for position in positions:
            seq.addSubCmd(actor='sac',
                          cmdStr='move detector=%.2f abs' % position)

            seq.addSubCmd(actor='sac',
                          cmdStr='ccd expose exptime=%.2f' % exptime,
                          duplicate=duplicate,
                          timeLim=60 + exptime)
        return seq

    def start(self, cmd=None):
        QThread.start(self)

    def stop(self, cmd=None):
        self.exit()

    def handleTimeout(self):
        """| Is called when the thread is idle
        """
        pass
