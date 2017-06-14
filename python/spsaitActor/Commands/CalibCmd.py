#!/usr/bin/env python


import sys

import numpy as np
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
            ('background', '<nb> <exptime> [force]', self.doBackground),
            ('dark', '<ndarks> <exptime>', self.doDarks),
            ('calib', '[<nbias>] [<ndarks>] [<exptime>]', self.doBasicCalib),
            ('imstab', '<exptime> <nb> <delay> [@(ne|hgar|xenon)] [<attenuator>] [switchOff]', self.doImstab)
        ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary("spsait_calib", (1, 1),
                                        keys.Key("exptime", types.Float(), help="The exposure time"),
                                        keys.Key("nb", types.Int(), help="Number of exposure"),
                                        keys.Key("ndarks", types.Int(), help="Number of darks"),
                                        keys.Key("nbias", types.Int(), help="Number of bias"),
                                        keys.Key("delay", types.Int(), help="delay in sec"),
                                        keys.Key("attenuator", types.Int(), help="optional attenuator value"),
                                        )

    @threaded
    def doBackground(self, cmd):
        e = False

        cmdKeys = cmd.cmd.keywords
        dcbKeys = self.actor.models['dcb']

        exptime = cmdKeys['exptime'].values[0]
        nb = cmdKeys['nb'].values[0]
        force = True if "force" in cmdKeys else False

        try:
            if exptime <= 0:
                raise Exception("exptime must be > 0")
            if nb <= 0:
                raise Exception("nb > 0 ")

            self.actor.processSequence(self.name, cmd, 2 * [CmdSeq('dcb', "labsphere value=0")])

            if not force:
                flux = dcbKeys.keyVarDict['photodiode'].getValue()
                if np.isnan(flux) or flux > 2e-3:
                    raise Exception("Flux is not null")

            bckSeq = nb * [CmdSeq('spsait', "expose exptime=%.2f" % exptime, timeLim=exptime+500, doRetry=True)]
            self.actor.processSequence(self.name, cmd, bckSeq)

        except Exception as e:
            cmd.fail("text='%s'" % formatException(e, sys.exc_info()[2]))
            return

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

            sequence = ndarks * [CmdSeq("ccd_r1", "expose darks=%.2f" % exptime, timeLim=exptime+500, doRetry=True)]

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

            sequence = nbias * [CmdSeq("ccd_r1", "expose nbias=%i" % nbias, doRetry=True)]
            sequence += ndarks * [CmdSeq("ccd_r1", "expose darks=%.2f" % exptime, timeLim=exptime+500, doRetry=True)]

            self.actor.processSequence(self.name, cmd, sequence)

        except Exception as e:
            cmd.fail("text='%s'" % formatException(e, sys.exc_info()[2]))
            return

        cmd.finish("text='Basic calib Sequence is over'")

    @threaded
    def doImstab(self, cmd):
        cmdKeys = cmd.cmd.keywords
        cmdCall = self.actor.safeCall
        e = False

        exptime = cmdKeys['exptime'].values[0]
        nb = cmdKeys['nb'].values[0]
        delay = cmdKeys['delay'].values[0]
        switchOff = True if "switchOff" in cmdKeys else False
        attenCmd = "attenuator=%i" % cmdKeys['attenuator'].values[0] if "attenuator" in cmdKeys else ""

        if "ne" in cmdKeys:
            arc = "ne"
        elif "hgar" in cmdKeys:
            arc = "hgar"
        elif "xenon" in cmdKeys:
            arc = "xenon"
        else:
            arc = None

        try:
            if exptime <= 0:
                raise Exception("exptime must be > 0")
            if nb <= 1:
                raise Exception("nb > 1 ")
            if delay <= 0:
                raise Exception("delay > 0 ")

        except Exception as e:
            cmd.fail("text='%s'" % formatException(e, sys.exc_info()[2]))
            return

        sequence = [CmdSeq('dcb', "switch arc=%s %s" % (arc, attenCmd), doRetry=True)] if arc is not None else []

        sequence += nb * [CmdSeq('spsait', "expose arc exptime=%.2f" % exptime, timeLim=500+exptime, doRetry=True, tempo=delay)]

        try:
            self.actor.processSequence(self.name, cmd, sequence)

        except Exception as e:
            pass

        if arc is not None and switchOff:
            cmdCall(actor='dcb', cmdStr="aten switch off channel=%s" % arc, timeLim=60, forUserCmd=cmd)

        if e:
            cmd.fail("text='%s'" % formatException(e, sys.exc_info()[2]))
        else:
            cmd.finish("text='Image stability Sequence is over'")