#!/usr/bin/env python


import opscore.protocols.keys as keys
import opscore.protocols.types as types
from spsaitActor.utils.sequencing import SubCmd, CmdList
from spsaitActor.utils import threaded


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
            ('bias', '[<duplicate>] [<cam>] [<name>] [<comments>] [<head>] [<tail>]',
             self.doBias),
            ('dark', '<exptime> [<duplicate>] [<cam>] [<name>] [<comments>] [<head>] [<tail>]',
             self.doDarks),
            ('imstab',
             '<exptime> <duration> <delay> [<duplicate>] [keepOn] [<switchOn>] [<switchOff>] [<attenuator>] [force] [<cam>] [<name>] [<comments>] [<head>] [<tail>]',
             self.imstab)
        ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary("spsait_calib", (1, 1),
                                        keys.Key("duplicate", types.Int(),
                                                 help="duplicate number of exposure per tempo(1 is default)"),
                                        keys.Key("exptime", types.Float(), help="The exposure time"),
                                        keys.Key("delay", types.Float(), help="delay in hours"),
                                        keys.Key("duration", types.Float(), help="total duration in hours"),
                                        keys.Key("switchOn", types.String() * (1, None),
                                                 help='which arc lamp to switch on.'),
                                        keys.Key("switchOff", types.String() * (1, None),
                                                 help='which arc lamp to switch off.'),
                                        keys.Key("attenuator", types.Int(), help="optional attenuator value"),
                                        keys.Key("cam", types.String() * (1,),
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
        self.actor.resetSequence()
        cmdKeys = cmd.cmd.keywords

        duplicate = cmdKeys['duplicate'].values[0] if "duplicate" in cmdKeys else 1
        cams = cmdKeys['cam'].values if 'cam' in cmdKeys else False

        name = cmdKeys['name'].values[0] if 'name' in cmdKeys else ''
        comments = cmdKeys['comments'].values[0] if 'comments' in cmdKeys else ''
        head = CmdList(cmdKeys['head'].values) if 'head' in cmdKeys else []
        tail = CmdList(cmdKeys['tail'].values) if 'tail' in cmdKeys else []

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
        self.actor.resetSequence()
        cmdKeys = cmd.cmd.keywords

        exptime = cmdKeys['exptime'].values[0]
        cams = cmdKeys['cam'].values if 'cam' in cmdKeys else False

        name = cmdKeys['name'].values[0] if 'name' in cmdKeys else ''
        comments = cmdKeys['comments'].values[0] if 'comments' in cmdKeys else ''
        head = CmdList(cmdKeys['head'].values) if 'head' in cmdKeys else []
        tail = CmdList(cmdKeys['tail'].values) if 'tail' in cmdKeys else []

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
    def imstab(self, cmd):
        self.actor.resetSequence()
        cmdKeys = cmd.cmd.keywords

        exptime = cmdKeys['exptime'].values[0]
        duration = cmdKeys['duration'].values[0]
        delay = cmdKeys['delay'].values[0]
        duplicate = cmdKeys['duplicate'].values[0] if "duplicate" in cmdKeys else 1
        cams = cmdKeys['cam'].values if 'cam' in cmdKeys else False
        keepOn = True if 'keepOn' in cmdKeys else False

        switchOn = cmdKeys['switchOn'].values if 'switchOn' in cmdKeys else False
        switchOff = cmdKeys['switchOff'].values if 'switchOff' in cmdKeys else False
        attenuator = 'attenuator=%i' % cmdKeys['attenuator'].values[0] if 'attenuator' in cmdKeys else ''
        force = 'force' if 'force' in cmdKeys else ''

        name = cmdKeys['name'].values[0] if 'name' in cmdKeys else ''
        comments = cmdKeys['comments'].values[0] if 'comments' in cmdKeys else ''
        head = CmdList(cmdKeys['head'].values) if 'head' in cmdKeys else []
        tail = CmdList(cmdKeys['tail'].values) if 'tail' in cmdKeys else []

        if exptime <= 0:
            raise Exception("exptime must be > 0")

        keepOn = True if not switchOn else keepOn

        if switchOff:
            tail.insert(0, SubCmd(actor='dcb',
                                  cmdStr="arc off=%s" % ','.join(switchOff)))

        sequence = self.controller.imstab(exptime=exptime,
                                          duration=duration,
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
