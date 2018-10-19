#!/usr/bin/env python


import opscore.protocols.keys as keys
import opscore.protocols.types as types
from enuActor.utils.wrap import threaded
from spsaitActor.sequencing import SubCmd


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
             'flat <exptime> <shift> <nbPosition> [@(microns|pixels)] [<duplicate>] [switchOff] [<attenuator>] [force] [<cam>] [<cams>] [<name>] [<comments>] [<head>] [<tail>] [<drpFolder>]',
             self.ditherFlat),
            ('dither',
             'psf <exptime> <shift> [@(microns|pixels)] [<duplicate>] [<switchOn>] [<switchOff>] [<attenuator>] [force] [<cam>] [<cams>] [<name>] [<head>] [<tail>] [<comments>][<drpFolder>]',
             self.ditherPsf)

        ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary("spsait_dither", (1, 1),
                                        keys.Key("exptime", types.Float(), help="The exposure time"),
                                        keys.Key("shift", types.Float(), help="shift in microns/pixels"),
                                        keys.Key("nbPosition", types.Int(), help="Number of position"),
                                        keys.Key("duplicate", types.Int(),
                                                 help="duplicate number of flat per position(1 is default)"),
                                        keys.Key("switchOn", types.String() * (1, None),
                                                 help='which arc lamp to switch on.'),
                                        keys.Key("switchOff", types.String() * (1, None),
                                                 help='which arc lamp to switch off.'),
                                        keys.Key("attenuator", types.Int(), help='Attenuator value.'),
                                        keys.Key("cam", types.String(), help='single camera to take exposure from'),
                                        keys.Key("cams", types.String() * (1,),
                                                 help='camera list to take exposure from'),
                                        keys.Key("name", types.String(), help='experiment name'),
                                        keys.Key("comments", types.String(), help='operator comments'),
                                        keys.Key("head", types.String() * (1,), help='cmdStr list to process before'),
                                        keys.Key("tail", types.String() * (1,), help='cmdStr list to process after'),
                                        keys.Key("drpFolder", types.String(), help='detrend exposures to this folder'),
                                        )

    @property
    def controller(self):
        try:
            return self.actor.controllers[self.name]
        except KeyError:
            raise RuntimeError('%s controller is not connected.' % self.name)

    @threaded
    def ditherFlat(self, cmd):
        cams = False
        self.actor.resetSequence()
        cmdKeys = cmd.cmd.keywords

        exptime = cmdKeys['exptime'].values[0]
        fact = (1. / (29.4)) if "pixels" in cmdKeys else 0.001
        shift = cmdKeys['shift'].values[0] * fact
        nbPosition = cmdKeys['nbPosition'].values[0]

        duplicate = cmdKeys['duplicate'].values[0] if "duplicate" in cmdKeys else 1
        attenuator = 'attenuator=%i' % cmdKeys['attenuator'].values[0] if 'attenuator' in cmdKeys else ''
        force = 'force' if 'force' in cmdKeys else ''
        switchOff = True if 'switchOff' in cmdKeys else False

        cams = [cmdKeys['cam'].values[0]] if 'cam' in cmdKeys else cams
        cams = cmdKeys['cams'].values if 'cams' in cmdKeys else cams

        name = cmdKeys['name'].values[0] if 'name' in cmdKeys else ''
        comments = cmdKeys['comments'].values[0] if 'comments' in cmdKeys else ''
        head = self.actor.subCmdList(cmdKeys['head'].values) if 'head' in cmdKeys else []
        tail = self.actor.subCmdList(cmdKeys['tail'].values) if 'tail' in cmdKeys else []
        drpFolder = cmdKeys['drpFolder'].values[0] if 'drpFolder' in cmdKeys else 'ditherflat'
        doRaise = True if 'drpFolder' in cmdKeys else False

        if exptime <= 0:
            raise Exception("exptime must be > 0")

        if drpFolder:
            self.actor.safeCall(actor='drp',
                                cmdStr='set drpFolder=%s' % drpFolder,
                                forUserCmd=cmd,
                                doRaise=doRaise,
                                timeLim=5)

        head = [SubCmd(actor='dcb', cmdStr="arc on=halogen %s %s" % (attenuator, force), timeLim=300)]
        tail = [SubCmd(actor='dcb', cmdStr="arc off=halogen", timeLim=300)] if switchOff else None

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
        cams = False
        self.actor.resetSequence()
        cmdKeys = cmd.cmd.keywords

        exptime = cmdKeys['exptime'].values[0]
        fact = (1. / (29.4)) if "pixels" in cmdKeys else 0.001
        shift = cmdKeys['shift'].values[0] * fact
        duplicate = cmdKeys['duplicate'].values[0] if "duplicate" in cmdKeys else 1

        attenuator = 'attenuator=%i' % cmdKeys['attenuator'].values[0] if 'attenuator' in cmdKeys else ''
        force = 'force' if 'force' in cmdKeys else ''
        switchOn = cmdKeys['switchOn'].values if 'switchOn' in cmdKeys else False
        switchOff = cmdKeys['switchOff'].values if 'switchOff' in cmdKeys else False

        name = cmdKeys['name'].values[0] if 'name' in cmdKeys else ''
        comments = cmdKeys['comments'].values[0] if 'comments' in cmdKeys else ''
        head = self.actor.subCmdList(cmdKeys['head'].values) if 'head' in cmdKeys else []
        tail = self.actor.subCmdList(cmdKeys['tail'].values) if 'tail' in cmdKeys else []
        drpFolder = cmdKeys['drpFolder'].values[0] if 'drpFolder' in cmdKeys else 'ditherpsf'
        doRaise = True if 'drpFolder' in cmdKeys else False

        cams = [cmdKeys['cam'].values[0]] if 'cam' in cmdKeys else cams
        cams = cmdKeys['cams'].values if 'cams' in cmdKeys else cams

        if exptime <= 0:
            raise Exception("exptime must be > 0")

        if drpFolder:
            self.actor.safeCall(actor='drp',
                                cmdStr='set drpFolder=%s' % drpFolder,
                                forUserCmd=cmd,
                                doRaise=doRaise,
                                timeLim=5)

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
