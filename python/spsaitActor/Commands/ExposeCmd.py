#!/usr/bin/env python


import sys
import time
from functools import partial

import numpy as np
import opscore.protocols.keys as keys
import opscore.protocols.types as types
from spsaitActor.utils import threaded, formatException, FailExposure


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
            ('expose', '[object] <exptime> [<comment>] [@(blue|red)]', self.doExposure),
            ('expose', 'arc <exptime> [@(neon|hgar|xenon|krypton)] [<attenuator>] [@(blue|red)] [switchOff] [force]', self.doArc),
            ('expose', 'flat <exptime> [<attenuator>] [@(blue|red)] [switchOff] [force]', self.doArc),
        ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary("spsait_expose", (1, 1),
                                        keys.Key("exptime", types.Float(), help="The exposure time"),
                                        keys.Key("comment", types.String(), help="user comment"),
                                        keys.Key("attenuator", types.Int(), help="optional attenuator value"),
                                        )

    @property
    def controller(self):
        try:
            return self.actor.controllers[self.name]
        except KeyError:
            raise RuntimeError('%s controller is not connected.' % self.name)

    @property
    def boolStop(self):
        return self.actor.boolStop[self.name]

    @threaded
    def doArc(self, cmd):
        self.controller.resetExposure()

        cmdKeys = cmd.cmd.keywords
        dcbKeys = self.actor.models['dcb']
        cmdCall = self.actor.safeCall
        ex = False

        arms = ['blue', 'red']

        arms = arms[:1] if 'blue' in cmdKeys else arms
        arms = arms[1:] if 'red' in cmdKeys else arms

        exptime = cmdKeys['exptime'].values[0]
        expType = "flat" if "flat" in cmdKeys else "arc"

        switchOff = True if "switchOff" in cmdKeys else False
        force = True if "force" in cmdKeys else False
        attenCmd = "attenuator=%i" % cmdKeys['attenuator'].values[0] if "attenuator" in cmdKeys else ""
        forceCmd = 'force' if force else ''

        arc = None
        arc = "neon" if "neon" in cmdKeys else arc
        arc = "hgar" if "hgar" in cmdKeys else arc
        arc = "xenon" if "xenon" in cmdKeys else arc
        arc = "krypton" if "krypton" in cmdKeys else arc
        arc = "halogen" if "flat" in cmdKeys else arc

        if exptime <= 0:
            raise Exception("exptime must be > 0")

        if arc is not None:
            cmdCall(actor='dcb', cmdStr="%s on %s %s" % (arc, attenCmd, forceCmd), timeLim=300, forUserCmd=cmd)

        if not force:
            flux = dcbKeys.keyVarDict['photodiode'].getValue()

            if np.isnan(flux) or flux <= 0 or self.boolStop:
                raise Exception("Flux is null")

        try:
            self.controller.expose(cmd, expType, exptime, arms)
            arms = [self.actor.ccd2arm[ccd] for ccd in self.controller.ccdActive]
            msg = 'arc done arms=%s exptime=%.2f' % (','.join(arms), exptime)

        except Exception as ex:
            msg = formatException(ex, sys.exc_info()[2])

        if arc is not None and switchOff:
            cmdCall(actor='dcb', cmdStr="%s off" % arc, timeLim=60, forUserCmd=cmd)

        ender = cmd.fail if ex else cmd.finish
        ender("text='%s'" % msg)

    @threaded
    def doExposure(self, cmd):
        self.controller.resetExposure()

        cmdKeys = cmd.cmd.keywords

        arms = ['blue', 'red']

        arms = arms[1:] if 'red' in cmdKeys else arms
        arms = arms[:1] if 'blue' in cmdKeys else arms

        exptime = cmdKeys['exptime'].values[0]
        expType = "object" if "object" in cmdKeys else "arc"

        if exptime <= 0:
            raise Exception("exptime must be > 0")

        self.controller.expose(cmd, expType, exptime, arms)

        arms = [self.actor.ccd2arm[ccd] for ccd in self.controller.ccdActive]
        cmd.finish("text='exposure done arms=%s exptime=%.2f'" % (','.join(arms), exptime))
