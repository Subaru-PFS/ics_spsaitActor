import logging
from collections import OrderedDict

from actorcore.QThread import QThread
from spsaitActor.utils.sequencing import CmdList


class dither(QThread):
    def __init__(self, actor, name, loglevel=logging.DEBUG):
        """This sets up the connections to/from the hub, the logger, and the twisted reactor.
        :param actor: spsaitActor
        :param name: controller name
        """
        QThread.__init__(self, actor, name, timeout=2)
        self.logger = logging.getLogger(self.name)
        self.logger.setLevel(loglevel)

    def ditherflat(self, exptime, cams, shift, nbPosition, duplicate):
        specIds = list(OrderedDict.fromkeys([int(cam[1]) for cam in cams])) if cams else self.actor.specIds
        cams = 'cams=%s' % ','.join(cams) if cams else ''
        enuActors = ['enu_sm%i' % specId for specId in specIds]

        seq = CmdList()

        seq.addSubCmd(actor='sps',
                      cmdStr='expose flat exptime=%.2f %s' % (exptime, cams),
                      timeLim=120 + exptime,
                      duplicate=duplicate)

        for enuActor in enuActors:
            seq.addSubCmd(actor=enuActor, cmdStr='slit dither=%.5f pixels' % (-nbPosition * shift))

        seq.addSubCmd(actor='sps',
                      cmdStr='expose flat exptime=%.2f %s' % (exptime, cams),
                      timeLim=120 + exptime,
                      duplicate=duplicate)

        for i in range(2 * nbPosition):
            for enuActor in enuActors:
                seq.addSubCmd(actor=enuActor, cmdStr='slit dither=%.5f pixels' % shift)

            seq.addSubCmd(actor='sps',
                          cmdStr='expose flat exptime=%.2f %s' % (exptime, cams),
                          timeLim=120 + exptime,
                          duplicate=duplicate)

        for enuActor in enuActors:
            seq.addSubCmd(actor=enuActor, cmdStr='slit dither=%.5f pixels' % (-nbPosition * shift))

        seq.addSubCmd(actor='sps',
                      cmdStr='expose flat exptime=%.2f %s' % (exptime, cams),
                      timeLim=120 + exptime,
                      duplicate=duplicate)

        return seq

    def ditherpsf(self, exptime, cams, shift, duplicate):
        specIds = list(OrderedDict.fromkeys([int(cam[1]) for cam in cams])) if cams else self.actor.specIds
        cams = 'cams=%s' % ','.join(cams) if cams else ''
        enuActors = ['enu_sm%i' % specId for specId in specIds]

        seq = CmdList()

        for yn in range(int(1 / shift)):
            for zn in range(int(1 / shift)):

                for enuActor in enuActors:
                    seq.addSubCmd(actor=enuActor, cmdStr='slit home')
                    seq.addSubCmd(actor=enuActor, cmdStr='slit shift=%.5f pixels' % (yn * shift))
                    seq.addSubCmd(actor=enuActor, cmdStr='slit dither=%.5f pixels' % (zn * shift))

                seq.addSubCmd(actor='sps',
                              cmdStr='expose arc exptime=%.2f %s' % (exptime, cams),
                              timeLim=120 + exptime,
                              duplicate=duplicate)

        for enuActor in enuActors:
            seq.addSubCmd(actor=enuActor, cmdStr='slit home')

        return seq

    def start(self, cmd=None):
        QThread.start(self)

    def stop(self, cmd=None):
        self.exit()

    def handleTimeout(self):
        """| Is called when the thread is idle
        """
        pass
