#!/usr/bin/env python


import opscore.protocols.keys as keys
import opscore.protocols.types as types
from spsaitActor.utils import threaded
from spsaitActor.utils.sequencing import SubCmd, CmdList


class DitherCmd(object):
    def __init__(self, actor):
        # This lets us access the rest of the actor.
        self.actor = actor
        # Declare the commands we implement. When the actor is started
        # these are registered with the parser, which will call the
        # associated methods when matched. The callbacks will be
        # passed a single argument, the parsed and typed command.
        #
        self.name = "dither"
        self.vocab = [
            ('dither',
             'flat <exptime> <pixels> <nbPosition> [<duplicate>] [switchOff] [<attenuator>] [force] [<cam>] [<name>] [<comments>] [<head>] [<tail>]',
             self.ditherFlat),
            ('dither',
             'psf <exptime> <pixels> [<duplicate>] [<switchOn>] [<switchOff>] [<attenuator>] [force] [<cam>] [<name>] [<head>] [<tail>] [<comments>]',
             self.ditherPsf)

        ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary("spsait_dither", (1, 1),
                                        keys.Key("exptime", types.Float(), help="The exposure time"),
                                        keys.Key("pixels", types.Float(), help="shift in pixels"),
                                        keys.Key("nbPosition", types.Int(), help="Number of position"),
                                        keys.Key("duplicate", types.Int(),
                                                 help="duplicate number of flat per position(1 is default)"),
                                        keys.Key("switchOn", types.String() * (1, None),
                                                 help='which arc lamp to switch on.'),
                                        keys.Key("switchOff", types.String() * (1, None),
                                                 help='which arc lamp to switch off.'),
                                        keys.Key("attenuator", types.Int(), help='Attenuator value.'),
                                        keys.Key("cam", types.String() * (1,),
                                                 help='camera list to take exposure from'),
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
    def ditherFlat(self, cmd):
        self.actor.resetSequence()
        cmdKeys = cmd.cmd.keywords

        exptime = cmdKeys['exptime'].values[0]
        shift = cmdKeys['pixels'].values[0]
        nbPosition = cmdKeys['nbPosition'].values[0]
        duplicate = cmdKeys['duplicate'].values[0] if "duplicate" in cmdKeys else 1

        attenuator = 'attenuator=%i' % cmdKeys['attenuator'].values[0] if 'attenuator' in cmdKeys else ''
        force = 'force' if 'force' in cmdKeys else ''
        switchOff = True if 'switchOff' in cmdKeys else False

        cams = cmdKeys['cam'].values if 'cam' in cmdKeys else False

        name = cmdKeys['name'].values[0] if 'name' in cmdKeys else ''
        comments = cmdKeys['comments'].values[0] if 'comments' in cmdKeys else ''
        head = CmdList(cmdKeys['head'].values) if 'head' in cmdKeys else []
        tail = CmdList(cmdKeys['tail'].values) if 'tail' in cmdKeys else []

        if exptime <= 0:
            raise Exception("exptime must be > 0")

        head += [SubCmd(actor='dcb', cmdStr="arc on=halogen %s %s" % (attenuator, force), timeLim=300)]
        tail = ([SubCmd(actor='dcb', cmdStr="arc off=halogen", timeLim=300)] if switchOff else []) + tail

        sequence = self.controller.ditherflat(exptime=exptime,
                                              cams=cams,
                                              shift=shift,
                                              nbPosition=nbPosition,
                                              duplicate=duplicate)

        self.actor.processSequence(cmd, sequence,
                                   seqtype='ditheredFlats',
                                   name=name,
                                   comments=comments,
                                   head=head,
                                   tail=tail)

        cmd.finish()

    @threaded
    def ditherPsf(self, cmd):
        self.actor.resetSequence()
        cmdKeys = cmd.cmd.keywords

        exptime = cmdKeys['exptime'].values[0]
        shift = cmdKeys['pixels'].values[0]
        duplicate = cmdKeys['duplicate'].values[0] if "duplicate" in cmdKeys else 1

        attenuator = 'attenuator=%i' % cmdKeys['attenuator'].values[0] if 'attenuator' in cmdKeys else ''
        force = 'force' if 'force' in cmdKeys else ''
        switchOn = cmdKeys['switchOn'].values if 'switchOn' in cmdKeys else False
        switchOff = cmdKeys['switchOff'].values if 'switchOff' in cmdKeys else False

        name = cmdKeys['name'].values[0] if 'name' in cmdKeys else ''
        comments = cmdKeys['comments'].values[0] if 'comments' in cmdKeys else ''
        head = CmdList(cmdKeys['head'].values) if 'head' in cmdKeys else []
        tail = CmdList(cmdKeys['tail'].values) if 'tail' in cmdKeys else []

        cams = cmdKeys['cam'].values if 'cam' in cmdKeys else False

        if exptime <= 0:
            raise Exception("exptime must be > 0")

        if switchOn:
            head += [SubCmd(actor='dcb',
                            cmdStr="arc on=%s %s %s" % (','.join(switchOn), attenuator, force),
                            timeLim=300)]

        if switchOff:
            tail.insert(0, SubCmd(actor='dcb',
                                  cmdStr="arc off=%s" % ','.join(switchOff)))

        sequence = self.controller.ditherpsf(exptime=exptime,
                                             cams=cams,
                                             shift=shift,
                                             duplicate=duplicate)

        self.actor.processSequence(cmd, sequence,
                                   seqtype='ditheredPsf',
                                   name=name,
                                   comments=comments,
                                   head=head,
                                   tail=tail)

        cmd.finish()
