#!/usr/bin/env python


import opscore.protocols.keys as keys
import opscore.protocols.types as types
from enuActor.utils.wrap import threaded
from spsaitActor.sequencing import SubCmd


class DefocusCmd(object):
    def __init__(self, actor):
        # This lets us access the rest of the actor.
        self.actor = actor
        # Declare the commands we implement. When the actor is started
        # these are registered with the parser, which will call the
        # associated methods when matched. The callbacks will be
        # passed a single argument, the parsed and typed command.
        #
        self.name = "defocus"
        self.vocab = [
            ('defocus',
             '<exptime> <nbPosition> [<duplicate>] [<switchOn>] [<switchOff>] [<attenuator>] [force] [<drpFolder>] [<name>] [<comments>] [<cam>] [<cams>]',
             self.defocus)
        ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary("spsait_defocus", (1, 1),
                                        keys.Key("exptime", types.Float(), help="The exposure time"),
                                        keys.Key("nbPosition", types.Int(), help="Number of position"),
                                        keys.Key("attenuator", types.Int(), help="optional attenuator value"),
                                        keys.Key("duplicate", types.Int(),
                                                 help="duplicate number of flat per position(1 is default)"),
                                        keys.Key("switchOn", types.String() * (1, None),
                                                 help='which arc lamp to switch on.'),
                                        keys.Key("switchOff", types.String() * (1, None),
                                                 help='which arc lamp to switch off.'),
                                        keys.Key("drpFolder", types.String(), help='detrend exposures to this folder'),
                                        keys.Key("name", types.String(), help='experiment name'),
                                        keys.Key("comments", types.String(), help='operator comments'),
                                        keys.Key("cam", types.String(), help='single camera to take exposure from'),
                                        keys.Key("cams", types.String() * (1,),
                                                 help='list of camera to take exposure from'),
                                        )

    @property
    def controller(self):
        try:
            return self.actor.controllers[self.name]
        except KeyError:
            raise RuntimeError('%s controller is not connected.' % self.name)

    @threaded
    def defocus(self, cmd):
        cams = False
        head = False
        tail = False
        self.actor.resetSequence()

        cmdKeys = cmd.cmd.keywords

        exptime = cmdKeys['exptime'].values[0]
        nbPosition = cmdKeys['nbPosition'].values[0]
        duplicate = cmdKeys['duplicate'].values[0] if "duplicate" in cmdKeys else 1
        attenuator = 'attenuator=%i' % cmdKeys['attenuator'].values[0] if 'attenuator' in cmdKeys else ''
        force = 'force' if 'force' in cmdKeys else ''
        switchOn = cmdKeys['switchOn'].values if 'switchOn' in cmdKeys else False
        switchOff = cmdKeys['switchOff'].values if 'switchOff' in cmdKeys else False

        name = cmdKeys['name'].values[0] if 'name' in cmdKeys else ''
        comments = cmdKeys['comments'].values[0] if 'comments' in cmdKeys else ''
        drpFolder = cmdKeys['drpFolder'].values[0] if 'drpFolder' in cmdKeys else 'defocused'

        cams = [cmdKeys['cam'].values[0]] if 'cam' in cmdKeys else cams
        cams = cmdKeys['cams'].values if 'cams' in cmdKeys else cams

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

        sequence = self.controller.defocus(exptime=exptime,
                                           nbPosition=nbPosition,
                                           cams=cams,
                                           duplicate=duplicate)

        self.actor.processSequence(cmd, sequence,
                                   seqtype='defocusedPsf',
                                   name=name,
                                   comments=comments,
                                   head=head,
                                   tail=tail)

        cmd.finish()
