#!/usr/bin/env python


from builtins import object
import sys
import time
from functools import partial

import numpy as np
import opscore.protocols.keys as keys
import opscore.protocols.types as types
from spsaitActor.utils import threaded


class ExposeCmd(object):
    def __init__(self, actor):
        # This lets us access the rest of the actor.
        self.actor = actor
        # Declare the commands we implement. When the actor is started
        # these are registered with the parser, which will call the
        # associated methods when matched. The callbacks will be
        # passed a single argument, the parsed and typed command.
        #
        self.name = "expose"
        self.vocab = [
            ('expose', 'arc <exptime> [<switchOn>] [<switchOff>] [<attenuator>] [force] [<duplicate>] [<cam>] [<cams>]',
             self.doArc),
            ('expose', 'flat <exptime> [<attenuator>] [switchOff] [<duplicate>] [<cam>] [<cams>]', self.doArc),
        ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary("spsait_expose", (1, 1),
                                        keys.Key("exptime", types.Float(), help="The exposure time"),
                                        keys.Key("switchOn", types.String() * (1, None),
                                                 help='which arc lamp to switch on.'),
                                        keys.Key("switchOff", types.String() * (1, None),
                                                 help='which arc lamp to switch off.'),
                                        keys.Key("attenuator", types.Int(),
                                                 help='Attenuator value.'),
                                        keys.Key("duplicate", types.Int(),
                                                 help="exposure duplicate (1 is default)"),
                                        keys.Key("cam", types.String(),
                                                 help='single camera to take exposure from'),
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
    def doArc(self, cmd):

        ex = False
        self.actor.resetSequence()

        cmdKeys = cmd.cmd.keywords
        cmdCall = self.actor.safeCall

        exptime = cmdKeys['exptime'].values[0]

        if 'arc' in cmdKeys:
            exptype = 'arc'
            switchOn = cmdKeys['switchOn'].values if 'switchOn' in cmdKeys else False
            switchOff = cmdKeys['switchOff'].values if 'switchOff' in cmdKeys else False
        else:
            exptype = 'flat'
            switchOn = ['halogen']
            switchOff = ['halogen'] if 'switchOff' in cmdKeys else False

        cams = False
        cams = [cmdKeys['cam'].values[0]] if 'cam' in cmdKeys else cams
        cams = cmdKeys['cams'].values if 'cams' in cmdKeys else cams

        duplicate = cmdKeys['duplicate'].values[0] if "duplicate" in cmdKeys else 1

        attenuator = 'attenuator=%i' % cmdKeys['attenuator'].values[0] if 'attenuator' in cmdKeys else ''
        force = 'force' if 'force' in cmdKeys else ''

        if exptime <= 0:
            raise Exception("exptime must be > 0")

        if switchOn:
            cmdCall(actor='dcb',
                    cmdStr="arc on=%s %s %s" % (','.join(switchOn), attenuator, force),
                    timeLim=300,
                    forUserCmd=cmd)

        try:
            sequence = self.controller.arcs(exptype=exptype,
                                            exptime=exptime,
                                            duplicate=duplicate,
                                            cams=cams)

            self.actor.processSequence(cmd, sequence)

        except Exception as e:
            ex = e

        if switchOff:
            cmdCall(actor='dcb',
                    cmdStr="arc off=%s" % ','.join(switchOff),
                    timeLim=300,
                    forUserCmd=cmd)

        if ex:
            raise ex

        cmd.finish()
