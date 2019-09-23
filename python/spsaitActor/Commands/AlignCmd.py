#!/usr/bin/env python


import numpy as np
import opscore.protocols.keys as keys
import opscore.protocols.types as types
from spsaitActor.utils import threaded
from spsaitActor.utils.sequencing import SubCmd, CmdList


class AlignCmd(object):
    def __init__(self, actor):
        # This lets us access the rest of the actor.
        self.actor = actor
        # Declare the commands we implement. When the actor is started
        # these are registered with the parser, which will call the
        # associated methods when matched. The callbacks will be
        # passed a single argument, the parsed and typed command.
        #
        self.name = 'align'
        self.vocab = [
            ('slit',
             'align <exptime> <position> [<fiber>] [<duplicate>] [<name>] [<comments>] [<head>] [<tail>]',
             self.slitAlign),
            ('slit',
             'throughfocus <exptime> <position> <cam> [<duplicate>] [<switchOn>] [<switchOff>] [<attenuator>] [force] [<name>] [<comments>] [<head>] [<tail>]',
             self.slitTF),
            ('detector',
             'throughfocus <exptime> <position> <cam> [<tilt>] [<duplicate>] [<switchOn>] [<switchOff>] [<attenuator>] [force] [<waveRange>] [<name>] [<comments>] [<head>] [<tail>]',
             self.detAlign),
            ('detector',
             'scan <exptime> <waveRange> [<duplicate>] [<cam>] [<name>] [<comments>] [<head>] [<tail>]', self.detScan),
        ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary('spsait_align', (1, 1),
                                        keys.Key('exptime', types.Float(), help='The exposure time'),
                                        keys.Key('position', types.Float() * (1, 3),
                                                 help='slit/motor position for throughfocus same args as np.linspace'),
                                        keys.Key('duplicate', types.Int(),
                                                 help='exposure duplicate per position (1 is default)'),
                                        keys.Key('tilt', types.Float() * (1, 3),
                                                 help='motor tilt (a, b, c)'),
                                        keys.Key('fiber', types.String(), help='fiber to aim'),
                                        keys.Key('switchOn', types.String() * (1, None),
                                                 help='which arc lamp to switch on.'),
                                        keys.Key('switchOff', types.String() * (1, None),
                                                 help='which arc lamp to switch off.'),
                                        keys.Key('attenuator', types.Int(), help='Attenuator value.'),
                                        keys.Key('waveRange', types.Float(), types.Float() * (1, 3),
                                                 help='monochromator wavelength range'),
                                        keys.Key('cam', types.String() * (1,),
                                                 help='list of camera to take exposure from'),
                                        keys.Key('name', types.String(), help='experiment name'),
                                        keys.Key('comments', types.String(), help='operator comments'),
                                        keys.Key('head', types.String() * (1,), help='cmdStr list to process before'),
                                        keys.Key('tail', types.String() * (1,), help='cmdStr list to process after'),
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
        positions = np.linspace(*cmdKeys['position'].values)
        duplicate = cmdKeys['duplicate'].values[0] if 'duplicate' in cmdKeys else 1
        targetedFiber = cmdKeys['fiber'].values[0] if 'fiber' in cmdKeys else False

        name = cmdKeys['name'].values[0] if 'name' in cmdKeys else ''
        comments = cmdKeys['comments'].values[0] if 'comments' in cmdKeys else ''
        head = CmdList(cmdKeys['head'].values) if 'head' in cmdKeys else []
        tail = CmdList(cmdKeys['tail'].values) if 'tail' in cmdKeys else []

        sequence = self.controller.slitalign(exptime=exptime,
                                             positions=positions,
                                             targetedFiber=targetedFiber,
                                             duplicate=duplicate)

        self.actor.processSequence(cmd, sequence,
                                   seqtype='slitAlignment',
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
        positions = np.linspace(*cmdKeys['position'].values)
        duplicate = cmdKeys['duplicate'].values[0] if 'duplicate' in cmdKeys else 1

        attenuator = 'attenuator=%i' % cmdKeys['attenuator'].values[0] if 'attenuator' in cmdKeys else ''
        force = 'force' if 'force' in cmdKeys else ''
        switchOn = cmdKeys['switchOn'].values if 'switchOn' in cmdKeys else False
        switchOff = cmdKeys['switchOff'].values if 'switchOff' in cmdKeys else False

        cams = cmdKeys['cam'].values

        name = cmdKeys['name'].values[0] if 'name' in cmdKeys else ''
        comments = cmdKeys['comments'].values[0] if 'comments' in cmdKeys else ''
        head = CmdList(cmdKeys['head'].values) if 'head' in cmdKeys else []
        tail = CmdList(cmdKeys['tail'].values) if 'tail' in cmdKeys else []

        if exptime <= 0:
            raise ValueError('exptime must be > 0')

        if switchOn:
            head += [SubCmd(actor='dcb',
                            cmdStr='arc on=%s %s %s' % (','.join(switchOn), attenuator, force),
                            timeLim=300)]

        if switchOff:
            tail.insert(0, SubCmd(actor='dcb',
                                  cmdStr='arc off=%s' % ','.join(switchOff)))

        sequence = self.controller.slitTF(exptime=exptime,
                                          positions=positions,
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
    def detAlign(self, cmd):
        self.actor.resetSequence()
        cmdKeys = cmd.cmd.keywords

        exptime = cmdKeys['exptime'].values[0]
        lowBound, upBound, nbPosition = cmdKeys['position'].values
        tilt = np.array(cmdKeys['tilt'].values) if 'tilt' in cmdKeys else np.zeros(3)
        duplicate = cmdKeys['duplicate'].values[0] if 'duplicate' in cmdKeys else 1

        switchOn = cmdKeys['switchOn'].values if 'switchOn' in cmdKeys else False
        switchOff = cmdKeys['switchOff'].values if 'switchOff' in cmdKeys else False
        attenuator = 'attenuator=%i' % cmdKeys['attenuator'].values[0] if 'attenuator' in cmdKeys else ''
        force = 'force' if 'force' in cmdKeys else ''
        waveRange = cmdKeys['waveRange'].values if 'waveRange' in cmdKeys else False

        cam = cmdKeys['cam'].values[0]
        name = cmdKeys['name'].values[0] if 'name' in cmdKeys else ''
        comments = cmdKeys['comments'].values[0] if 'comments' in cmdKeys else ''
        head = CmdList(cmdKeys['head'].values) if 'head' in cmdKeys else []
        tail = CmdList(cmdKeys['tail'].values) if 'tail' in cmdKeys else []

        if exptime <= 0:
            raise ValueError('exptime must be > 0')

        if switchOn:
            head += [SubCmd(actor='dcb',
                            cmdStr='arc on=%s %s %s' % (','.join(switchOn), attenuator, force),
                            timeLim=300)]

        if switchOff:
            tail.insert(0, SubCmd(actor='dcb',
                                  cmdStr='arc off=%s' % ','.join(switchOff)))

        sequence = self.controller.detalign(exptime=exptime,
                                            cam=cam,
                                            lowBound=lowBound,
                                            upBound=upBound,
                                            nbPosition=nbPosition,
                                            tilt=tilt,
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
    def detScan(self, cmd):
        self.actor.resetSequence()
        cmdKeys = cmd.cmd.keywords

        exptime = cmdKeys['exptime'].values[0]
        waveStart, waveEnd, waveNb = cmdKeys['waveRange'].values

        duplicate = cmdKeys['duplicate'].values[0] if 'duplicate' in cmdKeys else 1

        cams = cmdKeys['cam'].values if 'cam' in cmdKeys else False

        name = cmdKeys['name'].values[0] if 'name' in cmdKeys else ''
        comments = cmdKeys['comments'].values[0] if 'comments' in cmdKeys else ''
        head = CmdList(cmdKeys['head'].values) if 'head' in cmdKeys else []
        tail = CmdList(cmdKeys['tail'].values) if 'tail' in cmdKeys else []

        if exptime <= 0:
            raise ValueError('exptime must be > 0')

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
