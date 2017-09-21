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
            ('expose', 'arc <exptime> [@(neon|hgar|xenon)] [<attenuator>] [@(blue|red)] [switchOff]', self.doArc),
            ('expose', 'flat <exptime> [<attenuator>] [@(blue|red)] [switchOff]', self.doArc),
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

    def resetExposure(self):
        self.controller.ccdState = {}
        self.actor.boolStop[self.name] = False

    @threaded
    def doArc(self, cmd):
        self.resetExposure()

        cmdKeys = cmd.cmd.keywords
        dcbKeys = self.actor.models['dcb']
        cmdCall = self.actor.safeCall
        ex = False

        arms = ['blue', 'red']

        arms = arms[:1] if 'blue' in cmdKeys else arms
        arms = arms[1:] if 'red' in cmdKeys else arms

        exptime = cmdKeys['exptime'].values[0]
        expType = "arc"

        switchOff = True if "switchOff" in cmdKeys else False
        attenCmd = "attenuator=%i" % cmdKeys['attenuator'].values[0] if "attenuator" in cmdKeys else ""

        if "neon" in cmdKeys:
            arcLamp = "neon"
        elif "hgar" in cmdKeys:
            arcLamp = "hgar"
        elif "xenon" in cmdKeys:
            arcLamp = "xenon"
        elif "flat" in cmdKeys:
            arcLamp = "halogen"
        else:
            arcLamp = None

        try:
            if arcLamp is not None:
                cmdCall(actor='dcb', cmdStr="%s on %s" % (arcLamp, attenCmd), timeLim=300, forUserCmd=cmd)

            flux = dcbKeys.keyVarDict['photodiode'].getValue()

            if np.isnan(flux) or flux == 0 or self.boolStop:
                raise Exception("Flux is null")

        except Exception as e:
            cmd.fail("text='%s'" % formatException(e, sys.exc_info()[2]))
            return

        try:
            self.controller.expose(cmd, expType, exptime, arms)
            arms = [self.actor.ccd2arm[ccd] for ccd in self.controller.ccdExposing]
            msg = "text='arc done arms=%s exptime=%.2f'" % (','.join(arms), exptime)

        except Exception as ex:
            msg = "text='%s'" % formatException(ex, sys.exc_info()[2])

        if arcLamp is not None and switchOff:
            cmdCall(actor='dcb', cmdStr="%s off" % arcLamp, timeLim=60, forUserCmd=cmd)

        cmd.fail(msg) if ex else cmd.finish(msg)


    @threaded
    def doExposure(self, cmd):
        self.resetExposure()

        cmdKeys = cmd.cmd.keywords

        arms = ['blue', 'red']

        arms = arms[1:] if 'red' in cmdKeys else arms
        arms = arms[:1] if 'blue' in cmdKeys else arms

        exptime = cmdKeys['exptime'].values[0]
        expType = "object" if "object" in cmdKeys else "arc"

        try:
            self.controller.expose(cmd, expType, exptime, arms)

        except Exception as e:
            cmd.fail("text='%s'" % formatException(e, sys.exc_info()[2]))
            return

        arms = [self.actor.ccd2arm[ccd] for ccd in self.controller.ccdExposing]
        cmd.finish("text='exposure done arms=%s exptime=%.2f'" % (','.join(arms), exptime))

