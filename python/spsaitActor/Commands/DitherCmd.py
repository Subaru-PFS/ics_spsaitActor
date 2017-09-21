#!/usr/bin/env python


import sys

import opscore.protocols.keys as keys
import opscore.protocols.types as types
from spsaitActor.utils import threaded, formatException, CmdSeq


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
            ('dither', '<nb> <exptime> <shift> [@(microns|pixels)] [@(blue|red)] [<duplicate>] [<attenuator>] [switchOff]',
             self.dither),

        ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary("spsait_dither", (1, 1),
                                        keys.Key("exptime", types.Float(), help="The exposure time"),
                                        keys.Key("nb", types.Int(), help="Number of position"),
                                        keys.Key("shift", types.Float(), help="shift in microns/pixels"),
                                        keys.Key("attenuator", types.Int(), help="optional attenuator value"),
                                        keys.Key("duplicate", types.Int(),
                                                 help="duplicate number of flat per position(1 is default)"),
                                        )

    @property
    def controller(self):
        try:
            return self.actor.controllers[self.name]
        except KeyError:
            raise RuntimeError('%s controller is not connected.' % self.name)

    @threaded
    def dither(self, cmd):
        e = False
        arm = ''

        cmdKeys = cmd.cmd.keywords
        cmdCall = self.actor.safeCall
        enuKeys = self.actor.models['enu']

        nbImage = cmdKeys['nb'].values[0]
        exptime = cmdKeys['exptime'].values[0]
        fact = 0.034697 if "pixels" in cmdKeys else 0.001
        shift = cmdKeys['shift'].values[0] * fact
        duplicate = cmdKeys['duplicate'].values[0] if "duplicate" in cmdKeys else 1
        switchOff = True if "switchOff" in cmdKeys else False
        attenCmd = "attenuator=%i" % cmdKeys['attenuator'].values[0] if "attenuator" in cmdKeys else ""

        arm = 'red' if 'red' in cmdKeys else arm
        arm = 'blue' if 'blue' in cmdKeys else arm

        [state, mode, x, y, z, u, v, w] = enuKeys.keyVarDict['slit'].getValue()

        if exptime <= 0:
            cmd.fail("text='exptime must be positive'")
            return

        if nbImage < 1:
            cmd.fail("text='nbImage must be at least 1'")
            return

        sequence = self.controller.dithering(x, y, z, u, v, w, shift, nbImage, exptime, arm, duplicate, attenCmd)

        try:
            self.actor.processSequence(self.name, cmd, sequence)
            msg = "text='Dithering is over'"
        except Exception as e:
            msg = "text='%s'" % formatException(e, sys.exc_info()[2])

        if switchOff:
            cmdCall(actor='dcb', cmdStr="halogen off", forUserCmd=cmd)

        cmd.fail(msg) if e else cmd.finish(msg)