#!/usr/bin/env python


import time

import numpy as np
import opscore.protocols.keys as keys
import opscore.protocols.types as types
from astropy.io import fits
from imgtool import centroid
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
            ('slitalign', 'adjust <X> <Y> <Z> <U> <V> <W>', self.adjust),
        ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary("spsait_slitalign", (1, 1),
                                        keys.Key("exptime", types.Float(), help="The exposure time"),
                                        keys.Key("nb", types.Int(), help="Number of exposure"),
                                        keys.Key("prefix", types.String(), help="FITS Prefix name"),
                                        keys.Key("lowBound", types.Float(), help="lower bound for through focus"),
                                        keys.Key("highBound", types.Float(), help="higher bound for through focus"),
                                        keys.Key("X", types.Float(), help="breva X coordinate"),
                                        keys.Key("Y", types.Float(), help="breva Y coordinate"),
                                        keys.Key("Z", types.Float(), help="breva Z coordinate"),
                                        keys.Key("U", types.Float(), help="breva U coordinate"),
                                        keys.Key("V", types.Float(), help="breva V coordinate"),
                                        keys.Key("W", types.Float(), help="breva W coordinate"),
                                        )

    @threaded
    def loop(self, cmd):
        expTime = cmd.cmd.keywords['exptime'].values[0]
        if expTime > 0:
            self.actor.stopSequence = False
            self.actor.expTime = expTime
            while not self.actor.stopSequence:
                cmdVar = self.actor.cmdr.call(actor='sac', cmdStr="expose remote exptime=%.2f" % self.actor.expTime,
                                              forUserCmd=cmd)
                # cmdVar = self.actor.cmdr.call(actor='sac', cmdStr="status", forUserCmd=cmd)

                time.sleep(0.5)
            else:
                cmd.finish("text='Exposure Loop is over'")
        else:
            cmd.fail("text='exptime must be positive'")

    @threaded
    def throughFocus(self, cmd):

        prefix = str(cmd.cmd.keywords['prefix'].values[0])
        nbImage = cmd.cmd.keywords['nb'].values[0]
        expTime = cmd.cmd.keywords['exptime'].values[0]
        slitLowBound = cmd.cmd.keywords['lowBound'].values[0]
        slitHighBound = cmd.cmd.keywords['highBound'].values[0]
        enuKeys = self.actor.models['enu'].keyVarDict
        nbBackground = 3
        if expTime > 0 and nbImage > 1:
            i = 1
            self.actor.stopSequence = False
            self.actor.expTime = expTime

            sequence = self.buildThroughFocus(prefix, nbImage, expTime, slitLowBound, slitHighBound, enuKeys,
                                              nbBackground)
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

    def buildThroughFocus(self, prefix, nbImage, expTime, slitLowBound, slitHighBound, enuKeys, nbBackground):

        start = [slitLowBound] + list(enuKeys["slit"])[3:]
        end = [slitHighBound] + list(enuKeys["slit"])[3:]
        slitStart = " ".join(["%s = %.5f" % (key, val) for key, val in zip(['X', 'Y', 'Z', 'U', 'V', 'W'], start)])
        slitEnd = " ".join(["%s = %.5f" % (key, val) for key, val in zip(['X', 'Y', 'Z', 'U', 'V', 'W'], end)])

        offset = 12
        linear = np.ones(nbImage - 1) * (slitHighBound - slitLowBound) / (nbImage - 1)
        coeff = offset + (np.arange(nbImage - 1) - (nbImage - 1) / 2) ** 2
        k = sum(coeff * linear) / (slitHighBound - slitLowBound)
        coeff = coeff / k
        step = coeff * linear

        sequence = [('afl', 'switch off', 0.1), ('enu', "slit move absolute %s" % slitStart, 5)]
        for j in range(nbBackground):
            sequence.append(
                ('sac', "background fname=%s_background%s.fits exptime=%.2f" % (prefix, str(j + 1).zfill(2), expTime),
                 0.2))
        sequence += [('afl', 'switch on', 5),
                     ('sac', "expose fname=%s exptime=%.2f" % (self.getFilename(prefix, 1), expTime), 0.1)]
        for i in range(nbImage - 2):
            sequence += [('enu', "slit move relative X=%.5f" % step[i], 0.3),
                         ('sac', "expose fname=%s exptime=%.2f" % (self.getFilename(prefix, i + 2), expTime), 0.1)]
        sequence += [('enu', "slit move absolute %s" % slitEnd, 0.3),
                     ('sac', "expose fname=%s exptime=%.2f" % (self.getFilename(prefix, nbImage), expTime), 0.1)]

        return sequence

    def adjust(self, cmd):
        cmdKeys = cmd.cmd.keywords
        X = cmdKeys["X"].values[0]
        Y = cmdKeys["Y"].values[0]
        Z = cmdKeys["Z"].values[0]
        U = cmdKeys["U"].values[0]
        V = cmdKeys["V"].values[0]
        W = cmdKeys["W"].values[0]
        self.actor.cmdr.call(actor='breva', cmdStr='move abs %s' % " ".join(
            ["%s = %.5f" % (key, val) for key, val in zip(['x', 'y', 'z', 'rx', 'ry', 'rz'], [X, Y, Z, U, V, W])]),
                             forUserCmd=cmd)
        cmdVar = self.actor.cmdr.call(actor='sac',
                                      cmdStr="expose fname=%s exptime=%.2f" % ("adjust.fits", self.actor.expTime),
                                      forUserCmd=cmd)
        time.sleep(1.5)
        try:
            px, py = centroid(fits.open('/data/ait/slit-align/adjust.fits', "readonly"))
            print px, py
        except:
            cmd.fail("text='could not find centroid'")
            return

        cx, cy = 1215, 613.3
        c_Ry = 0.1 / 816.  # deg/px
        c_Rz = 0.1 / 1157.23
        dY = (cx - px) * c_Ry
        dZ = (py - cy) * c_Rz

        # d_ry_x = (1547.882 - 732.56) / 0.1
        # d_ry_y = (621.44 - 618.857) / 0.1
        # d_rz_x = (733.07 - 732.56) / 0.05
        # d_rz_y = (39.799 - 618.857) / 0.05
        # dX = (d_rz_y * (cx - px) - d_ry_y * (cy - py)) / (d_rz_y * d_ry_x - d_rz_x * d_ry_y)
        # dY = (d_ry_y * (cx - px) - d_ry_x * (cy - py)) / (d_rz_x * d_ry_y - d_ry_x * d_rz_y)

        self.actor.cmdr.call(actor='breva', cmdStr='move relo ry=%.5f rz=%.5f' % (dY, dZ), forUserCmd=cmd)
        cmd.finish("text='adjust finished'")

    def getFilename(self, prefix, i):

        return "%s_%s.fits" % (prefix, str(i).zfill(2))
