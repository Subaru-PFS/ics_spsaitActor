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
            ('dither', '<nb> <exptime> <shift> [@(microns|pixels)] [<duplicate>] [<attenuator>] [switchOff]',
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

    @threaded
    def dither(self, cmd):
        e = False

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

        [state, mode, x, y, z, u, v, w] = enuKeys.keyVarDict['slit'].getValue()

        if exptime <= 0:
            cmd.fail("text='exptime must be positive'")
            return

        if nbImage < 1:
            cmd.fail("text='nbImage must be at least 1'")
            return

        sequence = self.buildSequence(x, y, z, u, v, w, shift, nbImage, exptime, duplicate, attenCmd)

        try:
            self.actor.processSequence(self.name, cmd, sequence)
        except Exception as e:
            pass

        if switchOff:
            cmdCall(actor='dcb', cmdStr="labsphere switch off", forUserCmd=cmd)

        if e:
            cmd.fail("text='%s'" % formatException(e, sys.exc_info()[2]))
        else:
            cmd.finish("text='Dithering is over'")

    def buildSequence(self, x, y, z, u, v, w, shift, nbImage, exptime, duplicate, attenCmd):

        sequence = duplicate * [
            CmdSeq('spsait', "expose flat exptime=%.2f %s" % (exptime, attenCmd), timeLim=exptime + 500, doRetry=True)]

        for i in range(nbImage):
            sequence += [CmdSeq('enu', "slit dither pix=-%.5f" % shift)]
            sequence += duplicate * [
                CmdSeq('spsait', "expose flat exptime=%.2f" % exptime, timeLim=exptime + 500, doRetry=True)]

        sequence += [CmdSeq('enu', "slit move absolute x=%.5f y=%.5f z=%.5f u=%.5f v=%.5f w=%.5f" % (x, y, z, u, v, w))]

        for i in range(nbImage):
            sequence += [CmdSeq('enu', "slit dither pix=%.5f " % shift)]
            sequence += duplicate * [
                CmdSeq('spsait', "expose flat exptime=%.2f" % exptime, timeLim=exptime + 500, doRetry=True)]

        sequence += [CmdSeq('enu', "slit move absolute x=%.5f y=%.5f z=%.5f u=%.5f v=%.5f w=%.5f" % (x, y, z, u, v, w))]
        sequence += duplicate * [
            CmdSeq('spsait', "expose flat exptime=%.2f" % exptime, timeLim=exptime + 500, doRetry=True)]

        return sequence
