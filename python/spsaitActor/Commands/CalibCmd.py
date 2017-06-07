#!/usr/bin/env python


import sys

import opscore.protocols.keys as keys
import opscore.protocols.types as types
from spsaitActor.utils import threaded, formatException, CmdSeq


class CalibCmd(object):
    def __init__(self, actor):
        # This lets us access the rest of the actor.
        self.actor = actor
        # Declare the commands we implement. When the actor is started
        # these are registered with the parser, which will call the
        # associated methods when matched. The callbacks will be
        # passed a single argument, the parsed and typed command.
        #
        self.name = "calib"
        self.vocab = [
            ('background', '<nb> <exptime>', self.doBackground),
            ('dark', '<ndarks> <exptime>', self.doDarks),
            ('calib', '[<nbias>] [<ndarks>] [<exptime>]', self.doBasicCalib)
        ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary("spsait_calib", (1, 1),
                                        keys.Key("exptime", types.Float(), help="The exposure time"),
                                        keys.Key("nb", types.Int(), help="Number of exposure"),
                                        keys.Key("ndarks", types.Int(), help="Number of darks"),
                                        keys.Key("nbias", types.Int(), help="Number of darks"),
                                        )

    @threaded
    def doBackground(self, cmd):
        e = False

        cmdKeys = cmd.cmd.keywords
        dcbKeys = self.actor.models['dcb']

        exptime = cmdKeys['exptime'].values[0]
        nb = cmdKeys['nb'].values[0]

        attenSave = dcbKeys.keyVarDict['attenuator'].getValue()

        sequence = 2 * [CmdSeq('dcb', "labsphere value=0")]
        sequence += nb * [CmdSeq('spsait', "expose exptime=%.2f" % exptime, doRetry=True)]

        try:
            if exptime <= 0:
                raise Exception("exptime must be > 0")
            if nb <= 0:
                raise Exception("nb > 0 ")

        except Exception as e:
            cmd.fail("text='%s'" % formatException(e, sys.exc_info()[2]))
            return

        try:
            self.actor.processSequence(self.name, cmd, sequence)

        except Exception as e:
            pass

        self.actor.processSequence(self.name, cmd, 2 * [CmdSeq('dcb', "labsphere value=%i" % attenSave)])

        if e:
            cmd.fail("text='%s'" % formatException(e, sys.exc_info()[2]))
        else:
            cmd.finish("text='Background Sequence is over'")

    @threaded
    def doDarks(self, cmd):

        cmdKeys = cmd.cmd.keywords
        ndarks = cmdKeys['ndarks'].values[0]
        exptime = cmdKeys['exptime'].values[0]

        try:
            if exptime <= 0:
                raise Exception("exptime must be > 0")
            if ndarks <= 0:
                raise Exception("ndarks > 0 ")

        except Exception as e:
            cmd.fail("text='%s'" % formatException(e, sys.exc_info()[2]))
            return

        sequence = ndarks * [CmdSeq("ccd_r1", "expose darks=%.2f" % exptime, doRetry=True)]

        try:
            self.actor.processSequence(self.name, cmd, sequence)

        except Exception as e:
            cmd.fail("text='%s'" % formatException(e, sys.exc_info()[2]))
            return

        cmd.finish("text='Dark Sequence is over'")

    @threaded
    def doBasicCalib(self, cmd):
        cmdKeys = cmd.cmd.keywords

        ndarks = cmdKeys['ndarks'].values[0] if 'ndarks' in cmdKeys else 5
        exptime = cmdKeys['exptime'].values[0] if 'exptime' in cmdKeys else 900
        nbias = cmdKeys['nbias'].values[0] if 'nbias' in cmdKeys else 15

        try:
            if exptime <= 0:
                raise Exception("exptime must be > 0")
            if ndarks <= 0:
                raise Exception("ndarks > 0 ")
            if nbias <= 0:
                raise Exception("nbias > 0 ")

        except Exception as e:
            cmd.fail("text='%s'" % formatException(e, sys.exc_info()[2]))
            return

        sequence = nbias * [CmdSeq("ccd_r1", "expose nbias=%i" % nbias, doRetry=True)]
        sequence += ndarks * [CmdSeq("ccd_r1", "expose darks=%.2f" % exptime, doRetry=True)]

        try:
            self.actor.processSequence(self.name, cmd, sequence)

        except Exception as e:
            cmd.fail("text='%s'" % formatException(e, sys.exc_info()[2]))
            return

        cmd.finish("text='Basic calib Sequence is over'")
