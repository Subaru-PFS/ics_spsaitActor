#!/usr/bin/env python


import os
import time

import opscore.protocols.keys as keys
import opscore.protocols.types as types
from wrap import threaded


class SlitalignCmd(object):
    def __init__(self, actor):
        # This lets us access the rest of the actor.
        self.actor = actor
        # Declare the commands we implement. When the actor is started
        # these are registered with the parser, which will call the
        # associated methods when matched. The callbacks will be
        # passed a single argument, the parsed and typed command.
        #
        self.vocab = [
            ('slitalign', 'loop <exptime>', self.loop),
            ('slitalign', 'throughfocus <nb> <exptime> <prefix> <lowBound> <highBound>', self.throughFocus),
            ('test', '', self.test),
        ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary("spsait_slitalign", (1, 1),
                                        keys.Key("exptime", types.Float(), help="The exposure time"),
                                        keys.Key("nb", types.Float(), help="Number of exposure"),
                                        keys.Key("prefix", types.String(), help="FITS Prefix name"),
                                        keys.Key("lowBound", types.Float(), help="lower bound for through focus"),
                                        keys.Key("highBound", types.Float(), help="higher bound for through focus"),
                                        )

    @threaded
    def loop(self, cmd):
        expTime = cmd.cmd.keywords['exptime'].values[0]
        if expTime > 0:
            self.actor.stopSequence = False
            self.actor.expTime = expTime
            while not self.actor.stopSequence:
                cmdVar = self.actor.cmdr.call(actor='sac', cmdStr="exposure remote exptime=%.2f" % self.actor.expTime,
                                              forUserCmd=cmd)
                # cmdVar = self.actor.cmdr.call(actor='sac', cmdStr="status", forUserCmd=cmd)

                time.sleep(0.5)
            else:
                cmd.finish("text='Exposure Loop is over'")
        else:
            cmd.fail("text='exptime must be positive'")

    @threaded
    def throughFocus(self, cmd):

        expTime = cmd.cmd.keywords['exptime'].values[0]
        nbImage = cmd.cmd.keywords['nb'].values[0]
        prefix = str(cmd.cmd.keywords['prefix'].values[0])
        slitLowBound = cmd.cmd.keywords['lowBound'].values[0]
        slitHighBound = cmd.cmd.keywords['highBound'].values[0]

        if expTime > 0 and nbImage > 1:
            i = 1
            self.actor.stopSequence = False
            self.actor.expTime = expTime
            self.actor.cmdr.call(actor='enu',
                                 cmdStr="slit move absolute X=%.4f Y=0.0 Z=0.0 U=0.0 V=0.0 W=0.0" % slitLowBound,
                                 forUserCmd=cmd)
            time.sleep(0.3)
            cmdVar = self.actor.cmdr.call(actor='sac',
                                          cmdStr="exposure fname=%s exptime=%.2f" % (self.getFilename(prefix), expTime),
                                          forUserCmd=cmd)
            step = (slitHighBound - slitLowBound) / (nbImage - 1)
            while not self.actor.stopSequence and i < nbImage:

                cmdVar = self.actor.cmdr.call(actor='enu', cmdStr="slit move relative X=%.4f" % step,
                                              forUserCmd=cmd)
                time.sleep(0.3)
                cmdVar = self.actor.cmdr.call(actor='sac', cmdStr="exposure fname=%s exptime=%.2f" % (
                    self.getFilename(prefix), expTime), forUserCmd=cmd)
                i += 1
            else:
                cmd.finish("text='Exposure Loop is over'")
        else:
            cmd.fail("text='exptime must be positive'")

    def getFilename(self, prefix, i=1):
        while os.path.isfile("/data/ait/slit-align/%s_%s.fits" % (prefix, str(i).zfill(2))):
            i += 1

        return "%s_%s.fits" % (prefix, str(i).zfill(2))

    def test(self, cmd):
        cmdVar = self.actor.cmdr.cmdq(actor='sac', cmdStr="status", forUserCmd=cmd)
        print cmdVar.get()
