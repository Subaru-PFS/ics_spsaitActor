#!/usr/bin/env python


import sys
import time

import opscore.protocols.keys as keys
import opscore.protocols.types as types
from wrap import threaded, formatException, CmdSeq


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
        e = False
        self.actor.stopSequence = False

        cmdKeys = cmd.cmd.keywords
        cmdCall = self.actor.safeCall
        enuKeys = self.actor.models['enu']

        nbImage = cmdKeys['nb'].values[0]
        exptime = cmdKeys['exptime'].values[0]
        shift = cmdKeys['shift'].values[0] / 1000
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
            for cmdSeq in sequence:
                if self.actor.stopSequence:
                    break
                cmdCall(**(cmdSeq.build(cmd)))
                for i in range(int(cmdSeq.tempo // ti)):
                    if self.actor.stopSequence:
                        break
                    time.sleep(ti)
                time.sleep(cmdSeq.tempo % ti)

        except Exception as e:
            pass

        if switchOff:
            cmdCall(actor='dcb', cmdStr="labsphere switch off", timeLim=60, forUserCmd=cmd)

        if e:
            cmd.fail("text='%s'" % formatException(e, sys.exc_info()[2]))
        else:
            cmd.finish("text='Dithering is over'")

    def buildSequence(self, x, y, z, u, v, w, shift, nbImage, exptime, attenCmd):

        sequence = [CmdSeq('spsait', "expose flat exptime=%.2f %s" % (exptime, attenCmd), timeLim=500)]

        for i in range(nbImage):
            sequence += [CmdSeq('enu', " slit dither pix=-%.5f " % shift, tempo=5)]
            sequence += [CmdSeq('spsait', "expose flat exptime=%.2f" % exptime, timeLim=500)]

        sequence += [CmdSeq('enu', " slit move absolute x=%.5f y=%.5f z=%.5f u=%.5f v=%.5f w=%.5f" % (x, y, z, u, v, w),
                            tempo=5)]

        for i in range(nbImage):
            sequence += [CmdSeq('enu', " slit dither pix=%.5f " % shift, tempo=5)]
            sequence += [CmdSeq('spsait', "expose flat exptime=%.2f" % exptime, timeLim=500)]

        return sequence
