#!/usr/bin/env python


import sys
import time

import opscore.protocols.keys as keys
import opscore.protocols.types as types
from wrap import threaded, formatException


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
            ('dither', '<nb> <exptime> <shift> [<attenuator>] [switchOff]', self.dither),

        ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary("spsait_dither", (1, 1),
                                        keys.Key("exptime", types.Float(), help="The exposure time"),
                                        keys.Key("nb", types.Int(), help="Number of position"),
                                        keys.Key("shift", types.Float(), help="shift in microns"),
                                        keys.Key("attenuator", types.Int(), help="optional attenuator value"),
                                        )

    @threaded
    def dither(self, cmd):
        ti = 0.2
        cmdKeys = cmd.cmd.keywords
        nbImage = cmdKeys['nb'].values[0]
        exptime = cmdKeys['exptime'].values[0]
        shift = cmdKeys['shift'].values[0]/1000

        cmdCall = self.actor.safeCall
        enuKeys = self.actor.models['enu']

        self.actor.stopSequence = False
        switchOff = True if "switchOff" in cmdKeys else False
        attenCmd = "attenuator=%i" % cmdKeys['attenuator'].values[0] if "attenuator" in cmdKeys else ""

        [state, mode, x, y, z, u, v, w] = enuKeys.keyVarDict['slit'].getValue()

        if exptime <= 0:
            cmd.fail("text='exptime must be positive'")
            return

        if nbImage < 1:
            cmd.fail("text='nbImage must be at least 1'")
            return

        try:
            sequence = self.buildSequence(x, y, z, u, v, w, shift, nbImage, exptime, attenCmd)
            for actor, cmdStr, tempo in sequence:
                if self.actor.stopSequence:
                    break
                cmdCall(actor=actor, cmdStr=cmdStr, forUserCmd=cmd, timeLim=120)
                for i in range(int(tempo // ti)):
                    if self.actor.stopSequence:
                        break
                    time.sleep(ti)
                time.sleep(tempo % ti)

            if switchOff:
                cmdCall(actor='dcb', cmdStr="labsphere switch off", timeLim=30, forUserCmd=cmd)

        except Exception as e:
            cmd.fail("text='%s'" % formatException(e, sys.exc_info()[2]))
            return

        cmd.finish("text='Dithering is over'")

    def buildSequence(self, x, y, z, u, v, w, shift, nbImage, exptime, attenCmd):
        sequence = [('spsait', "expose flat exptime=%.2f %s" % (exptime, attenCmd), 0)]

        for i in range(nbImage):
            sequence += [('enu', " slit dither pix=-%.5f " % shift, 5)]
            sequence += [('spsait', "expose flat exptime=%.2f" % exptime, 0)]

        sequence += [('enu', " slit move absolute x=%.5f y=%.5f z=%.5f u=%.5f v=%.5f w=%.5f" % (x, y, z, u, v, w), 5)]

        for i in range(nbImage):
            sequence += [('enu', " slit dither pix=%.5f " % shift, 5)]
            sequence += [('spsait', "expose flat exptime=%.2f" % exptime, 0)]

        return sequence
