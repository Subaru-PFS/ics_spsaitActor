#!/usr/bin/env python


import sys

import opscore.protocols.keys as keys
import opscore.protocols.types as types
from spsaitActor.utils import threaded, formatException


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
            ('dither', 'flat <nb> <exptime> <shift> [@(microns|pixels)] [@(blue|red)] [<duplicate>]'
                       ' [<attenuator>] [switchOff]', self.ditherFlat),
            ('dither', 'psf <exptime> <shift> [@(microns|pixels)] [@(blue|red)] [<duplicate>]'
                       ' [@(neon|hgar|xenon|krypton)] [<attenuator>] [switchOff] [force]', self.ditherPsf)

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
    def ditherFlat(self, cmd):
        ex = False
        arm = ''

        cmdKeys = cmd.cmd.keywords
        cmdCall = self.actor.safeCall
        enuKeys = self.actor.models['enu']

        nbImage = cmdKeys['nb'].values[0]
        exptime = cmdKeys['exptime'].values[0]
        fact = 1./30 if "pixels" in cmdKeys else 0.001
        shift = cmdKeys['shift'].values[0] * fact
        duplicate = cmdKeys['duplicate'].values[0] if "duplicate" in cmdKeys else 1
        switchOff = True if "switchOff" in cmdKeys else False
        attenCmd = "attenuator=%i" % cmdKeys['attenuator'].values[0] if "attenuator" in cmdKeys else ""

        arm = 'red' if 'red' in cmdKeys else arm
        arm = 'blue' if 'blue' in cmdKeys else arm

        [state, mode, x, y, z, u, v, w] = enuKeys.keyVarDict['slit'].getValue()

        if exptime <= 0:
            raise Exception("exptime must be > 0")
        if nbImage <= 0:
            raise Exception("nbImage > 0")

        sequence = self.controller.ditherFlat(x, y, z, u, v, w, shift, nbImage, exptime, arm, duplicate, attenCmd)

        try:
            self.actor.processSequence(self.name, cmd, sequence)
            msg = 'Dithered Flat sequence is over'
        except Exception as ex:
            msg = formatException(ex, sys.exc_info()[2])

        if switchOff:
            cmdCall(actor='dcb', cmdStr="halogen off", forUserCmd=cmd)

        ender = cmd.fail if ex else cmd.finish
        ender("text='%s'" % msg)


    @threaded
    def ditherPsf(self, cmd):
        ex = False
        optArgs = []

        cmdKeys = cmd.cmd.keywords
        cmdCall = self.actor.safeCall

        exptime = cmdKeys['exptime'].values[0]
        fact = 1./30 if "pixels" in cmdKeys else 0.001
        shift = cmdKeys['shift'].values[0] * fact
        duplicate = cmdKeys['duplicate'].values[0] if "duplicate" in cmdKeys else 1
        switchOff = True if "switchOff" in cmdKeys else False
        attenCmd = "attenuator=%i" % cmdKeys['attenuator'].values[0] if "attenuator" in cmdKeys else ""

        optArgs = ['red'] if 'red' in cmdKeys else optArgs
        optArgs = ['blue'] if 'blue' in cmdKeys else optArgs

        optArgs += (['force'] if "force" in cmdKeys else [])

        arc = None
        arc = "neon" if "neon" in cmdKeys else arc
        arc = "hgar" if "hgar" in cmdKeys else arc
        arc = "xenon" if "xenon" in cmdKeys else arc

        if exptime <= 0:
            raise Exception("exptime must be > 0")

        sequence = self.controller.ditherPsf(shift, exptime, arc, duplicate, attenCmd, optArgs)

        try:
            self.actor.processSequence(self.name, cmd, sequence)
            msg = 'Dithering PSF sequence is over'
        except Exception as ex:
            msg = formatException(ex, sys.exc_info()[2])

        if arc is not None and switchOff:
            cmdCall(actor='dcb', cmdStr="%s off" % arc, timeLim=60, forUserCmd=cmd)

        ender = cmd.fail if ex else cmd.finish
        ender("text='%s'" % msg)
