import logging

from actorcore.QThread import QThread
from spsaitActor.utils.sequencing import CmdList


class calib(QThread):
    def __init__(self, actor, name, loglevel=logging.DEBUG):
        """This sets up the connections to/from the hub, the logger, and the twisted reactor.

        :param actor: spsaitActor
        :param name: controller name
        """
        QThread.__init__(self, actor, name, timeout=2)
        self.logger = logging.getLogger(self.name)
        self.logger.setLevel(loglevel)

    def biases(self, duplicate, cams):
        cams = 'cams=%s' % ','.join(cams) if cams else ''
        seq = CmdList()
        seq.addSubCmd(actor='sps',
                      cmdStr='expose bias %s' % cams,
                      duplicate=duplicate)
        return seq

    def darks(self, duplicate, exptime, cams):
        cams = 'cams=%s' % ','.join(cams) if cams else ''
        seq = CmdList()
        seq.addSubCmd(actor='sps',
                      cmdStr='expose dark exptime=%.2f %s' % (exptime, cams),
                      duplicate=duplicate,
                      timeLim=120 + exptime)
        return seq

    def imstab(self, exptime, duration, delay, duplicate, cams, keepOn, switchOn, attenuator, force):
        cams = 'cams=%s' % ','.join(cams) if cams else ''
        seq = CmdList()
        nbPosition = int(duration / delay) + 1

        for i in range(nbPosition):
            tempo = 0 if i == (nbPosition - 1) else delay * 3600
            cmdOn = 'arc on=%s %s %s' % (','.join(switchOn), attenuator, force) if switchOn else 'status'
            seq.addSubCmd(actor='dcb',
                          cmdStr=cmdOn,
                          timeLim=300)

            seq.addSubCmd(actor='sps',
                          cmdStr='expose arc exptime=%.2f %s' % (exptime, cams),
                          timeLim=120 + exptime,
                          duplicate=duplicate)

            cmdOff = 'arc off=%s' % ','.join(switchOn) if not keepOn else 'status'
            seq.addSubCmd(actor='dcb',
                          cmdStr=cmdOff,
                          tempo=tempo)
        return seq

    def start(self, cmd=None):
        QThread.start(self)

    def stop(self, cmd=None):
        self.exit()

    def handleTimeout(self):
        """| Is called when the thread is idle
        """
        pass
