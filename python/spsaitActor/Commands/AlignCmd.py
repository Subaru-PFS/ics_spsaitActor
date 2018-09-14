#!/usr/bin/env python


import opscore.protocols.keys as keys
import opscore.protocols.types as types
import numpy as np
from enuActor.utils.wrap import threaded
from spsaitActor.sequencing import SubCmd

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
            ('sac','align <exptime> <focus> <nbPosition> [<lowBound>] [<upBound>] [<duplicate>] [<name>] [<comments>]', self.sacAlign),
            ('slit','throughfocus <exptime> <nbPosition> <lowBound> <upBound> [<fiber>] [<duplicate>] [<name>] [<comments>]', self.slitAlign),
            ('detector', 'throughfocus <exptime> <cam> <nbPosition> [<lowBound>] [<upBound>] [<startPosition>] [<duplicate>] [<switchOn>] [<switchOff>] [<attenuator>] [force] [<drpFolder>] [<name>] [<comments>]', self.detAlign),
        ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary("spsait_align", (1, 1),
                                        keys.Key("exptime", types.Float(), help="The exposure time"),
                                        keys.Key("focus", types.Float(), help="sac ccd stage absolute position"),
                                        keys.Key("lowBound", types.Float(), help="lower bound for through focus"),
                                        keys.Key("upBound", types.Float(), help="upper bound for through focus"),
                                        keys.Key("nbPosition", types.Int(), help="Number of position"),
                                        keys.Key("duplicate", types.Int(),
                                                 help="exposure duplicate per position (1 is default)"),
                                        keys.Key("cam", types.String(),
                                                 help='single camera to take exposure from'),
                                        keys.Key("startPosition", types.Float() * (1, 3), help="Start from this position a,b,c.\
                                                 The 3 motors positions are required. If it is not set the lowBound position is used. "),
                                        keys.Key("switchOn", types.String() * (1, None),
                                                 help='which arc lamp to switch on.'),
                                        keys.Key("switchOff", types.String() * (1, None),
                                                 help='which arc lamp to switch off.'),
                                        keys.Key("attenuator", types.Int(),
                                                 help='Attenuator value.'),
                                        keys.Key("fiber", types.String(),
                                                 help='fiber to aim'),
                                        keys.Key("drpFolder", types.String(),
                                                 help='detrend exposures to this folder'),
                                        keys.Key("name", types.String(),
                                                 help='experiment name'),
                                        keys.Key("comments", types.String(),
                                                 help='operator comments'),
                                        )

    @property
    def controller(self):
        try:
            return self.actor.controllers[self.name]
        except KeyError:
            raise RuntimeError('%s controller is not connected.' % self.name)

    @threaded
    def sacAlign(self, cmd):
        self.actor.resetSequence()

        cmdKeys = cmd.cmd.keywords

        exptime = cmdKeys['exptime'].values[0]
        focus = cmdKeys['focus'].values[0]
        nbPosition = cmdKeys['nbPosition'].values[0]
        lowBound = cmdKeys['lowBound'].values[0] if 'lowBound' in cmdKeys else -300
        upBound = cmdKeys['upBound'].values[0] if 'upBound' in cmdKeys else 500
        duplicate = cmdKeys['duplicate'].values[0] if 'duplicate' in cmdKeys else 1

        name = cmdKeys['name'].values[0] if 'name' in cmdKeys else ''
        comments = cmdKeys['comments'].values[0] if 'comments' in cmdKeys else ''

        sequence = self.controller.sacalign(exptime=exptime,
                                            focus=focus,
                                            lowBound=lowBound,
                                            upBound=upBound,
                                            nbPosition=nbPosition,
                                            duplicate=duplicate)

        self.actor.processSequence(cmd, sequence,
                                   seqtype='SacAlignment',
                                   name=name,
                                   comments=comments)

        cmd.finish()

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

        sequence = self.controller.slitalign(exptime=exptime,
                                             targetedFiber=targetedFiber,
                                             lowBound=lowBound,
                                             upBound=upBound,
                                             nbPosition=nbPosition,
                                             duplicate=duplicate)

        self.actor.processSequence(cmd, sequence,
                                   seqtype='slitAlignment',
                                   name=name,
                                   comments=comments)

        cmd.finish()

    @threaded
    def detAlign(self, cmd):
        head = False
        tail = False
        self.actor.resetSequence()

        cmdKeys = cmd.cmd.keywords

        exptime = cmdKeys['exptime'].values[0]
        cam = cmdKeys['cam'].values[0]
        nbPosition = cmdKeys['nbPosition'].values[0]
        lowBound = cmdKeys['lowBound'].values[0] if 'lowBound' in cmdKeys else 0
        upBound = cmdKeys['upBound'].values[0] if 'upBound' in cmdKeys else 290
        startPosition = cmdKeys['startPosition'].values if "startPosition" in cmdKeys else 3*[lowBound]

        switchOn = cmdKeys['switchOn'].values if 'switchOn' in cmdKeys else False
        switchOff = cmdKeys['switchOff'].values if 'switchOff' in cmdKeys else False
        attenuator = 'attenuator=%i' % cmdKeys['attenuator'].values[0] if 'attenuator' in cmdKeys else ''
        force = 'force' if 'force' in cmdKeys else ''

        name = cmdKeys['name'].values[0] if 'name' in cmdKeys else ''
        comments = cmdKeys['comments'].values[0] if 'comments' in cmdKeys else ''
        drpFolder = cmdKeys['drpFolder'].values[0] if 'drpFolder' in cmdKeys else 'detalign'

        duplicate = cmdKeys['duplicate'].values[0] if "duplicate" in cmdKeys else 1

        if exptime <= 0:
            raise Exception("exptime must be > 0")

        if drpFolder:
            self.actor.safeCall(actor='drp',
                                cmdStr='set drpFolder=%s' % drpFolder,
                                forUserCmd=cmd)

        if switchOn:
            head = SubCmd(actor='dcb',
                          cmdStr="arc on=%s %s %s" % (','.join(switchOn), attenuator, force),
                          timeLim=300)

        if switchOff:
            tail = SubCmd(actor='dcb',
                          cmdStr="arc off=%s" % ','.join(switchOff),
                          timeLim=300)

        sequence = self.controller.detalign(exptime=exptime,
                                            cam=cam,
                                            startPosition=np.array(startPosition),
                                            upBound=upBound,
                                            nbPosition=nbPosition,
                                            duplicate=duplicate)

        self.actor.processSequence(cmd, sequence,
                                   seqtype='detectorAlignment',
                                   name=name,
                                   comments=comments,
                                   head=head,
                                   tail=tail)

        cmd.finish()
