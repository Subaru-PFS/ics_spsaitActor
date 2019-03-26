#!/usr/bin/env python


import opscore.protocols.keys as keys
import opscore.protocols.types as types

from spsaitActor.utils import threaded
from spsaitActor.sequencing import SubCmd


class CalibCmd(object):
    def __init__(self, actor):
        # This lets us access the rest of the actor.
        self.actor = actor
        # Declare the commands we implement. When the actor is started
        # these are registered with the parser, which will call the
        # associated methods when matched. The callbacks will be
        # passed a single argument, the parsed and typed command.
        #
        self.name = "calib"
        self.vocab = [
            ('bias', '[<duplicate>] [<cam>] [<cams>] [<name>] [<comments>] [<head>] [<tail>]',
             self.doBias),
            ('dark', '<exptime> [<duplicate>] [<cam>] [<cams>] [<name>] [<comments>] [<head>] [<tail>]',
             self.doDarks),
            ('calib',
             '[<nbias>] [<ndarks>] [<exptime>] [<cam>] [<cams>] [<name>] [<comments>] [<head>] [<tail>]',
             self.doBasicCalib),
            ('imstab',
             '<exptime> <nbPosition> <delay> [<duplicate>] [keepOn] [<switchOn>] [<switchOff>] [<attenuator>] [force] [<cam>] [<cams>] [<name>] [<comments>] [<head>] [<tail>]',
             self.imstab)
        ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary("spsait_calib", (1, 1),
                                        keys.Key("duplicate", types.Int(),
                                                 help="duplicate number of exposure per tempo(1 is default)"),
                                        keys.Key("exptime", types.Float(), help="The exposure time"),
                                        keys.Key("ndarks", types.Int(), help="Number of darks"),
                                        keys.Key("nbias", types.Int(), help="Number of bias"),
                                        keys.Key("nbPosition", types.Int(), help="Number of position"),
                                        keys.Key("delay", types.Int(), help="delay in sec"),
                                        keys.Key("switchOn", types.String() * (1, None),
                                                 help='which arc lamp to switch on.'),
                                        keys.Key("switchOff", types.String() * (1, None),
                                                 help='which arc lamp to switch off.'),
                                        keys.Key("attenuator", types.Int(), help="optional attenuator value"),
                                        keys.Key("cam", types.String(), help='single camera to take exposure from'),
                                        keys.Key("cams", types.String() * (1,),
                                                 help='list of camera to take exposure from'),
                                        keys.Key("name", types.String(), help='experiment name'),
                                        keys.Key("comments", types.String(), help='operator comments'),
                                        keys.Key("head", types.String() * (1,), help='cmdStr list to process before'),
                                        keys.Key("tail", types.String() * (1,), help='cmdStr list to process after'),
                                        )

    @property
    def controller(self):
        try:
            return self.actor.controllers[self.name]
        except KeyError:
            raise RuntimeError('%s controller is not connected.' % self.name)

    @threaded
    def doBias(self, cmd):
        cams = False
        self.actor.resetSequence()
        cmdKeys = cmd.cmd.keywords

        duplicate = cmdKeys['duplicate'].values[0] if "duplicate" in cmdKeys else 1

        cams = [cmdKeys['cam'].values[0]] if 'cam' in cmdKeys else cams
        cams = cmdKeys['cams'].values if 'cams' in cmdKeys else cams

        name = cmdKeys['name'].values[0] if 'name' in cmdKeys else ''
        comments = cmdKeys['comments'].values[0] if 'comments' in cmdKeys else ''
        head = self.actor.subCmdList(cmdKeys['head'].values) if 'head' in cmdKeys else []
        tail = self.actor.subCmdList(cmdKeys['tail'].values) if 'tail' in cmdKeys else []

        sequence = self.controller.biases(duplicate=duplicate, cams=cams)

        self.actor.processSequence(cmd, sequence,
                                   seqtype='biases',
                                   name=name,
                                   comments=comments,
                                   head=head,
                                   tail=tail)

        cmd.finish()

    @threaded
    def doDarks(self, cmd):
        cams = False
        self.actor.resetSequence()
        cmdKeys = cmd.cmd.keywords

        exptime = cmdKeys['exptime'].values[0]

        cams = [cmdKeys['cam'].values[0]] if 'cam' in cmdKeys else cams
        cams = cmdKeys['cams'].values if 'cams' in cmdKeys else cams

        name = cmdKeys['name'].values[0] if 'name' in cmdKeys else ''
        comments = cmdKeys['comments'].values[0] if 'comments' in cmdKeys else ''
        head = self.actor.subCmdList(cmdKeys['head'].values) if 'head' in cmdKeys else []
        tail = self.actor.subCmdList(cmdKeys['tail'].values) if 'tail' in cmdKeys else []

        if exptime <= 0:
            raise Exception("exptime must be > 0")

        duplicate = cmdKeys['duplicate'].values[0] if "duplicate" in cmdKeys else 1

        sequence = self.controller.darks(duplicate=duplicate, exptime=exptime, cams=cams)

        self.actor.processSequence(cmd, sequence,
                                   seqtype='darks',
                                   name=name,
                                   comments=comments,
                                   head=head,
                                   tail=tail)

        cmd.finish()

    @threaded
    def doBasicCalib(self, cmd):
        cams = False
        self.actor.resetSequence()
        cmdKeys = cmd.cmd.keywords

        ndarks = cmdKeys['ndarks'].values[0] if 'ndarks' in cmdKeys else 5
        exptime = cmdKeys['exptime'].values[0] if 'exptime' in cmdKeys else 900
        nbias = cmdKeys['nbias'].values[0] if 'nbias' in cmdKeys else 15

        cams = [cmdKeys['cam'].values[0]] if 'cam' in cmdKeys else cams
        cams = cmdKeys['cams'].values if 'cams' in cmdKeys else cams

        name = cmdKeys['name'].values[0] if 'name' in cmdKeys else ''
        comments = cmdKeys['comments'].values[0] if 'comments' in cmdKeys else ''
        head = self.actor.subCmdList(cmdKeys['head'].values) if 'head' in cmdKeys else []
        tail = self.actor.subCmdList(cmdKeys['tail'].values) if 'tail' in cmdKeys else []

        if exptime <= 0:
            raise Exception("exptime must be > 0")

        sequence = self.controller.biases(duplicate=nbias, cams=cams)
        sequence += self.controller.darks(duplicate=ndarks, exptime=exptime, cams=cams)

        self.actor.processSequence(cmd, sequence,
                                   seqtype='calib',
                                   name=name,
                                   comments=comments,
                                   head=head,
                                   tail=tail)

        cmd.finish()

    @threaded
    def imstab(self, cmd):
        cams = False
        self.actor.resetSequence()
        cmdKeys = cmd.cmd.keywords

        exptime = cmdKeys['exptime'].values[0]
        nbPosition = cmdKeys['nbPosition'].values[0]
        delay = cmdKeys['delay'].values[0]
        duplicate = cmdKeys['duplicate'].values[0] if "duplicate" in cmdKeys else 1
        keepOn = True if 'keepOn' in cmdKeys else False

        switchOn = cmdKeys['switchOn'].values if 'switchOn' in cmdKeys else False
        switchOff = cmdKeys['switchOff'].values if 'switchOff' in cmdKeys else False
        attenuator = 'attenuator=%i' % cmdKeys['attenuator'].values[0] if 'attenuator' in cmdKeys else ''
        force = 'force' if 'force' in cmdKeys else ''

        cams = [cmdKeys['cam'].values[0]] if 'cam' in cmdKeys else cams
        cams = cmdKeys['cams'].values if 'cams' in cmdKeys else cams

        name = cmdKeys['name'].values[0] if 'name' in cmdKeys else ''
        comments = cmdKeys['comments'].values[0] if 'comments' in cmdKeys else ''
        head = self.actor.subCmdList(cmdKeys['head'].values) if 'head' in cmdKeys else []
        tail = self.actor.subCmdList(cmdKeys['tail'].values) if 'tail' in cmdKeys else []

        if exptime <= 0:
            raise Exception("exptime must be > 0")

        keepOn = True if not switchOn else keepOn

        if switchOff:
            tail.insert(0, SubCmd(actor='dcb',
                                  cmdStr="arc off=%s" % ','.join(switchOff)))

        sequence = self.controller.imstab(exptime=exptime,
                                          nbPosition=nbPosition,
                                          delay=delay,
                                          duplicate=duplicate,
                                          cams=cams,
                                          keepOn=keepOn,
                                          switchOn=switchOn,
                                          attenuator=attenuator,
                                          force=force)

        self.actor.processSequence(cmd, sequence,
                                   seqtype='imageStability',
                                   name=name,
                                   comments=comments,
                                   head=head,
                                   tail=tail)

        cmd.finish()
