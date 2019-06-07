#!/usr/bin/env python


import numpy as np
import opscore.protocols.keys as keys
import opscore.protocols.types as types
from spsaitActor.sequencing import SubCmd
from spsaitActor.utils import threaded


class AlignCmd(object):
    def __init__(self, actor):
        # This lets us access the rest of the actor.
        self.actor = actor
        # Declare the commands we implement. When the actor is started
        # these are registered with the parser, which will call the
        # associated methods when matched. The callbacks will be
        # passed a single argument, the parsed and typed command.
        #
        self.name = "align"
        self.vocab = [
            ('slit',
             'align <exptime> <nbPosition> <lowBound> <upBound> [<fiber>] [<duplicate>] [<name>] [<comments>] [<head>] [<tail>]',
             self.slitAlign),
            ('detector',
             'throughfocus <exptime> <cam> <nbPosition> [<lowBound>] [<upBound>] [<startPosition>] [<duplicate>] [<switchOn>] [<switchOff>] [<attenuator>] [force] [<waveRange>] [<name>] [<comments>] [<head>] [<tail>]',
             self.detAlign),
            ('slit',
             'throughfocus <exptime> <nbPosition> <lowBound> [<upBound>] [<duplicate>] [<switchOn>] [<switchOff>] [<attenuator>] [force] [<cam>] [<name>] [<comments>] [<head>] [<tail>]',
             self.slitTF),
            ('detector',
             'scan <exptime> <waveRange> [<duplicate>] [<cam>] [<name>] [<comments>] [<head>] [<tail>]', self.detScan),
        ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary("spsait_align", (1, 1),
                                        keys.Key("exptime", types.Float(), help="The exposure time"),
                                        keys.Key("nbPosition", types.Int(), help="Number of position"),
                                        keys.Key("focus", types.Float(), help="sac ccd stage absolute position"),
                                        keys.Key("lowBound", types.Float(), help="lower bound for through focus"),
                                        keys.Key("upBound", types.Float(), help="upper bound for through focus"),
                                        keys.Key("duplicate", types.Int(),
                                                 help="exposure duplicate per position (1 is default)"),
                                        keys.Key("startPosition", types.Float() * (1, 3),
                                                 help="Start from this position a,b,c.The 3 motors positions are required. "
                                                      "If it is not set the lowBound position is used. "),
                                        keys.Key("fiber", types.String(), help='fiber to aim'),
                                        keys.Key("switchOn", types.String() * (1, None),
                                                 help='which arc lamp to switch on.'),
                                        keys.Key("switchOff", types.String() * (1, None),
                                                 help='which arc lamp to switch off.'),
                                        keys.Key("attenuator", types.Int(), help='Attenuator value.'),
                                        keys.Key("waveRange", types.Float(), types.Float() * (1, 3),
                                                 help='monochromator wavelength range'),
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
    def slitAlign(self, cmd):
        self.actor.resetSequence()
        cmdKeys = cmd.cmd.keywords

        exptime = cmdKeys['exptime'].values[0]
        lowBound = cmdKeys['lowBound'].values[0]
        upBound = cmdKeys['upBound'].values[0]
        nbPosition = cmdKeys['nbPosition'].values[0]
        duplicate = cmdKeys['duplicate'].values[0] if 'duplicate' in cmdKeys else 1
        targetedFiber = cmdKeys['fiber'].values[0] if 'fiber' in cmdKeys else False

        name = cmdKeys['name'].values[0] if 'name' in cmdKeys else ''
        comments = cmdKeys['comments'].values[0] if 'comments' in cmdKeys else ''
        head = self.actor.subCmdList(cmdKeys['head'].values) if 'head' in cmdKeys else []
        tail = self.actor.subCmdList(cmdKeys['tail'].values) if 'tail' in cmdKeys else []

        sequence = self.controller.slitalign(exptime=exptime,
                                             targetedFiber=targetedFiber,
                                             lowBound=lowBound,
                                             upBound=upBound,
                                             nbPosition=nbPosition,
                                             duplicate=duplicate)

        self.actor.processSequence(cmd, sequence,
                                   seqtype='slitAlignment',
                                   name=name,
                                   comments=comments,
                                   head=head,
                                   tail=tail)

        cmd.finish()

    @threaded
    def detAlign(self, cmd):
        self.actor.resetSequence()
        cmdKeys = cmd.cmd.keywords

        exptime = cmdKeys['exptime'].values[0]
        nbPosition = cmdKeys['nbPosition'].values[0]
        lowBound = cmdKeys['lowBound'].values[0] if 'lowBound' in cmdKeys else 0
        upBound = cmdKeys['upBound'].values[0] if 'upBound' in cmdKeys else 290
        startPosition = cmdKeys['startPosition'].values if "startPosition" in cmdKeys else 3 * [lowBound]
        duplicate = cmdKeys['duplicate'].values[0] if "duplicate" in cmdKeys else 1

        switchOn = cmdKeys['switchOn'].values if 'switchOn' in cmdKeys else False
        switchOff = cmdKeys['switchOff'].values if 'switchOff' in cmdKeys else False
        attenuator = 'attenuator=%i' % cmdKeys['attenuator'].values[0] if 'attenuator' in cmdKeys else ''
        force = 'force' if 'force' in cmdKeys else ''
        waveRange = cmdKeys['waveRange'].values if 'waveRange' in cmdKeys else False

        cam = cmdKeys['cam'].values[0]
        name = cmdKeys['name'].values[0] if 'name' in cmdKeys else ''
        comments = cmdKeys['comments'].values[0] if 'comments' in cmdKeys else ''
        head = self.actor.subCmdList(cmdKeys['head'].values) if 'head' in cmdKeys else []
        tail = self.actor.subCmdList(cmdKeys['tail'].values) if 'tail' in cmdKeys else []

        if exptime <= 0:
            raise ValueError("exptime must be > 0")

        if switchOn:
            head += [SubCmd(actor='dcb',
                            cmdStr="arc on=%s %s %s" % (','.join(switchOn), attenuator, force),
                            timeLim=300)]

        if switchOff:
            tail.insert(0, SubCmd(actor='dcb',
                                  cmdStr="arc off=%s" % ','.join(switchOff)))

        sequence = self.controller.detalign(exptime=exptime,
                                            cam=cam,
                                            startPosition=np.array(startPosition),
                                            upBound=upBound,
                                            nbPosition=nbPosition,
                                            duplicate=duplicate,
                                            waveRange=waveRange)

        self.actor.processSequence(cmd, sequence,
                                   seqtype='detectorAlignment',
                                   name=name,
                                   comments=comments,
                                   head=head,
                                   tail=tail)

        cmd.finish()

    @threaded
    def slitTF(self, cmd):
        self.actor.resetSequence()
        cmdKeys = cmd.cmd.keywords

        exptime = cmdKeys['exptime'].values[0]
        nbPosition = cmdKeys['nbPosition'].values[0]
        lowBound = cmdKeys['lowBound'].values[0]
        upBound = cmdKeys['upBound'].values[0]
        duplicate = cmdKeys['duplicate'].values[0] if "duplicate" in cmdKeys else 1

        attenuator = 'attenuator=%i' % cmdKeys['attenuator'].values[0] if 'attenuator' in cmdKeys else ''
        force = 'force' if 'force' in cmdKeys else ''
        switchOn = cmdKeys['switchOn'].values if 'switchOn' in cmdKeys else False
        switchOff = cmdKeys['switchOff'].values if 'switchOff' in cmdKeys else False

        cams = cmdKeys['cam'].values if 'cam' in cmdKeys else self.actor.cams

        name = cmdKeys['name'].values[0] if 'name' in cmdKeys else ''
        comments = cmdKeys['comments'].values[0] if 'comments' in cmdKeys else ''
        head = self.actor.subCmdList(cmdKeys['head'].values) if 'head' in cmdKeys else []
        tail = self.actor.subCmdList(cmdKeys['tail'].values) if 'tail' in cmdKeys else []

        if exptime <= 0:
            raise ValueError("exptime must be > 0")

        if switchOn:
            head += [SubCmd(actor='dcb',
                            cmdStr="arc on=%s %s %s" % (','.join(switchOn), attenuator, force),
                            timeLim=300)]

        if switchOff:
            tail.insert(0, SubCmd(actor='dcb',
                                  cmdStr="arc off=%s" % ','.join(switchOff)))

        sequence = self.controller.slitTF(exptime=exptime,
                                          nbPosition=nbPosition,
                                          lowBound=lowBound,
                                          upBound=upBound,
                                          cams=cams,
                                          duplicate=duplicate)

        self.actor.processSequence(cmd, sequence,
                                   seqtype='slitThroughFocus',
                                   name=name,
                                   comments=comments,
                                   head=head,
                                   tail=tail)

        cmd.finish()

    @threaded
    def detScan(self, cmd):
        self.actor.resetSequence()
        cmdKeys = cmd.cmd.keywords

        exptime = cmdKeys['exptime'].values[0]
        waveStart, waveEnd, waveNb = cmdKeys['waveRange'].values

        duplicate = cmdKeys['duplicate'].values[0] if "duplicate" in cmdKeys else 1

        cams = cmdKeys['cam'].values if 'cam' in cmdKeys else self.actor.cams

        name = cmdKeys['name'].values[0] if 'name' in cmdKeys else ''
        comments = cmdKeys['comments'].values[0] if 'comments' in cmdKeys else ''
        head = self.actor.subCmdList(cmdKeys['head'].values) if 'head' in cmdKeys else []
        tail = self.actor.subCmdList(cmdKeys['tail'].values) if 'tail' in cmdKeys else []

        if exptime <= 0:
            raise ValueError("exptime must be > 0")

        sequence = self.controller.detScan(exptime=exptime,
                                           waveStart=waveStart,
                                           waveEnd=waveEnd,
                                           waveNb=waveNb,
                                           cams=cams,
                                           duplicate=duplicate)

        self.actor.processSequence(cmd, sequence,
                                   seqtype='detScan',
                                   name=name,
                                   comments=comments,
                                   head=head,
                                   tail=tail)

        cmd.finish()
