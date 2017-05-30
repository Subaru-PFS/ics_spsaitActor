#!/usr/bin/env python


import sys

import opscore.protocols.keys as keys
import opscore.protocols.types as types
from spsaitActor.utils import threaded, formatException, CmdSeq


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
            ('detalign',
             'throughfocus <nb> <exptime> <lowBound> <upBound> [<motor>] [@(ne|hgar|xenon)] [<attenuator>] [<startPosition>] [switchOff]',
             self.throughFocus),
        ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary("spsait_detalign", (1, 1),
                                        keys.Key("exptime", types.Float() * (1,), help="The exposure time(s)"),
                                        keys.Key("nb", types.Int(), help="Number of position"),
                                        keys.Key("lowBound", types.Float(), help="lower bound for through focus"),
                                        keys.Key("upBound", types.Float(), help="upper bound for through focus"),
                                        keys.Key("motor", types.String(), help="optional to move a single motor"),
                                        keys.Key("attenuator", types.Int(), help="optional attenuator value"),
                                        keys.Key("startPosition", types.Float() * (1, 3), help="Start from this position a,b,c.\
                                         The 3 motors positions are required. If it is not set the lowBound position is used. ")
                                        )

    @threaded
    def throughFocus(self, cmd):
        e = False

        cmdKeys = cmd.cmd.keywords
        cmdCall = self.actor.safeCall

        nbImage = cmdKeys['nb'].values[0]
        expTimes = cmdKeys['exptime'].values
        lowBound = cmdKeys['lowBound'].values[0]
        upBound = cmdKeys['upBound'].values[0]
        motor = cmdKeys['motor'].values[0] if "motor" in cmdKeys else "piston"
        startPosition = cmdKeys['startPosition'].values if "startPosition" in cmdKeys else None
        attenCmd = "attenuator=%i" % cmdKeys['attenuator'].values[0] if "attenuator" in cmdKeys else ""
        switchOff = True if "switchOff" in cmdKeys else False

        if "ne" in cmdKeys:
            arcLamp = "ne"
        elif "hgar" in cmdKeys:
            arcLamp = "hgar"
        elif "xenon" in cmdKeys:
            arcLamp = "xenon"
        else:
            arcLamp = None

        for exptime in expTimes:
            if exptime <= 0:
                cmd.fail("text='exptime must be positive'")
                return

        if nbImage <= 1:
            cmd.fail("text='nbImage must be at least 2'")
            return

        sequence = self.buildThroughFocus(arcLamp, attenCmd, nbImage, expTimes, lowBound, upBound, motor, startPosition)

        try:
            self.actor.processSequence(self.name, cmd, sequence)
        except Exception as e:
            pass

        if arcLamp is not None and switchOff:
            cmdCall(actor='dcb', cmdStr="aten switch off channel=%s" % arcLamp, forUserCmd=cmd)
        if e:
            cmd.fail("text='%s'" % formatException(e, sys.exc_info()[2]))
        else:
            cmd.finish("text='Through Focus is over'")

    def buildThroughFocus(self, arcLamp, attenCmd, nbImage, expTimes, lowBound, upBound, motor, startPosition):
        step = (upBound - lowBound) / (nbImage - 1)

        if arcLamp is not None:
            sequence = [CmdSeq('dcb', "switch arc=%s %s" % (arcLamp, attenCmd), doRetry=True)]
        else:
            sequence = []
        # Number of microns must be an integer
        if startPosition is None:
            sequence += [CmdSeq('xcu_r1', "motors moveCcd %s=%i microns abs" % (motor, lowBound), doRetry=True)]
        else:
            posA, posB, posC = startPosition
            sequence += [
                CmdSeq('xcu_r1', "motors moveCcd a=%i b=%i c=%i microns abs" % (posA, posB, posC), doRetry=True)]

        seq_expTime = [CmdSeq('spsait', "expose arc exptime=%.2f" % expTime, doRetry=True) for expTime in expTimes]

        sequence += seq_expTime

        for i in range(nbImage - 1):
            sequence += [CmdSeq('xcu_r1', "motors moveCcd %s=%i microns" % (motor, step))]
            sequence += seq_expTime

        return sequence
