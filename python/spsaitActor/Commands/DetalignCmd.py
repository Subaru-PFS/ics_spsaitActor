#!/usr/bin/env python


import time

import numpy as np
import opscore.protocols.keys as keys
import opscore.protocols.types as types
from astropy.io import fits
from imgtool import centroid
from wrap import threaded


class DetalignCmd(object):
    def __init__(self, actor):
        # This lets us access the rest of the actor.
        self.actor = actor
        # Declare the commands we implement. When the actor is started
        # these are registered with the parser, which will call the
        # associated methods when matched. The callbacks will be
        # passed a single argument, the parsed and typed command.
        #
        self.name = "detalign"
        self.vocab = [
            ('detalign', 'throughfocus <nb> <exptime> <lowBound> <highBound> [<motor>]', self.throughFocus),
        ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary("spsait_detalign", (1, 1),
                                        keys.Key("exptime", types.Float(), help="The exposure time"),
                                        keys.Key("nb", types.Int(), help="Number of exposure"),
                                        keys.Key("lowBound", types.Float(), help="lower bound for through focus"),
                                        keys.Key("highBound", types.Float(), help="higher bound for through focus"),
                                        keys.Key("motor", types.String(), help="optional to move a single motor"),
                                     )



    @threaded
    def throughFocus(self, cmd):
        cmdkeys =  cmd.cmd.keywords

        nbImage =cmdkeys['nb'].values[0]
        expTime = cmdkeys['exptime'].values[0]
        lowBound =cmdkeys['lowBound'].values[0]
        highBound = cmdkeys['highBound'].values[0]
        motor = cmdkeys['motor'].values[0] if "motor" in cmdkeys else "piston"

        nbBackground = 3
        if expTime > 0 and nbImage > 1:
            i = 1
            self.actor.stopSequence = False
            self.actor.expTime = expTime

            sequence = self.buildThroughFocus(nbImage, expTime, lowBound, highBound, motor, nbBackground)
            for actor, cmdStr, tempo in sequence:
                if self.actor.stopSequence:
                    break
                self.actor.cmdr.call(actor=actor, cmdStr=cmdStr, forUserCmd=cmd)
                for i in range(int(tempo // 0.5)):
                    if self.actor.stopSequence:
                        break
                    time.sleep(0.5)
                time.sleep(tempo % 0.5)
            cmd.finish("text='Through focus is over'")
        else:
            cmd.fail("text='exptime must be positive'")

    def buildThroughFocus(self, nbImage, expTime, lowBound, highBound, motor, nbBackground):


        offset = 12
        linear = np.ones(nbImage - 1) * (highBound - lowBound) / (nbImage - 1)
        coeff = offset + (np.arange(nbImage - 1) - (nbImage - 1) / 2) ** 2
        k = sum(coeff * linear) / (highBound - lowBound)
        coeff = coeff / k
        # try linear first
        coeff=1
        step = coeff * linear

        sequence = [('xcu_r1', " motors moveCcd %s=%i microns abs" %(motor,lowBound), 5), ('spsait', "expose exptime=%.2f object" %expTime,0)]
        # for j in range(nbBackground):
        #     sequence.append(
        #         ('sac', "background fname=%s_background%s.fits exptime=%.2f" % (prefix, str(j + 1).zfill(2), expTime),
        #          0.2))
        # sequence += [('afl', 'switch on', 5),
        #              ('sac', "expose fname=%s exptime=%.2f" % (self.getFilename(prefix, 1), expTime), 0.1)]
        for i in range(nbImage - 2):
            sequence += [('xcu_r1', " motors moveCcd %s=%i microns " %(motor,step[i]), 5), ('spsait', "expose exptime=%.2f object" %expTime,0)]
        sequence += [('xcu_r1', " motors moveCcd %s=%i microns abs" %(motor,highBound), 5), ('spsait', "expose exptime=%.2f object" %expTime,0)]


        return sequence


