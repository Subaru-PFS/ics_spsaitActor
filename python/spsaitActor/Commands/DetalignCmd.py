#!/usr/bin/env python


import time

import numpy as np
import opscore.protocols.keys as keys
import opscore.protocols.types as types
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
            ('detalign',
             'throughfocus <nb> <exptime> <lowBound> <highBound> [<motor>] [@(ne|hgar|xenon)] [@(switchOff)] [<startPosition>]',
             self.throughFocus),
        ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary("spsait_detalign", (1, 1),
                                        keys.Key("exptime", types.Float() * (1,), help="The exposure time(s)"),
                                        keys.Key("nb", types.Int(), help="Number of position"),
                                        keys.Key("lowBound", types.Float(), help="lower bound for through focus"),
                                        keys.Key("highBound", types.Float(), help="higher bound for through focus"),
                                        keys.Key("motor", types.String(), help="optional to move a single motor"),
                                        keys.Key("startPosition", types.Float() * (1, 3), help="Start from this position a,b,c.\
                                         The 3 motors positions are required. If it is not set the lowBound position is used. ")
                                        )

    @threaded
    def throughFocus(self, cmd):
        cmdKeys = cmd.cmd.keywords
        cmdCall = self.actor.cmdr.call

        nbImage = cmdKeys['nb'].values[0]
        expTimes = cmdKeys['exptime'].values
        lowBound = cmdKeys['lowBound'].values[0]
        highBound = cmdKeys['highBound'].values[0]
        motor = cmdKeys['motor'].values[0] if "motor" in cmdKeys else "piston"
        startPosition = cmdKeys['startPosition'].values if "startPosition" in cmdKeys else None

        switchOff = True if "switchOff" in cmdKeys else False

        self.actor.stopSequence = False

        if "ne" in cmdKeys:
            arcLamp = "ne"
        elif "hgar" in cmdKeys:
            arcLamp = "hgar"
        elif "xenon" in cmdKeys:
            arcLamp = "xenon"
        else:
            arcLamp = None

        if arcLamp is not None:
            cmdCall(actor='dcb', cmdStr="switch arc=%s attenuator=255" % arcLamp, timeLim=300, forUserCmd=cmd)

        ti = 0.5

        if expTimes[0] > 0 and nbImage > 1:

            sequence = self.buildThroughFocus(nbImage, expTimes, lowBound, highBound, motor, startPosition)
            for actor, cmdStr, tempo in sequence:
                if self.actor.stopSequence:
                    break
                cmdCall(actor=actor, cmdStr=cmdStr, forUserCmd=cmd)
                for i in range(int(tempo // ti)):
                    if self.actor.stopSequence:
                        break
                    time.sleep(ti)
                time.sleep(tempo % ti)

            if arcLamp is not None:
                if switchOff:
                    cmdCall(actor='dcb', cmdStr="aten switch off channel=%s" % arcLamp, timeLim=30, forUserCmd=cmd)

            cmd.finish("text='Through focus is over'")
        else:
            cmd.fail("text='exptime must be positive'")

    def buildThroughFocus(self, nbImage, expTimes, lowBound, highBound, motor, startPosition):

        offset = 12
        linear = np.ones(nbImage - 1) * (highBound - lowBound) / (nbImage - 1)
        coeff = offset + (np.arange(nbImage - 1) - (nbImage - 1) / 2) ** 2
        k = sum(coeff * linear) / (highBound - lowBound)
        coeff = coeff / k
        # try linear first
        coeff = 1
        step = coeff * linear

        seq_expTime = [('spsait', "expose arc exptime=%.2f " % expTime, 0) for expTime in expTimes]

        # Number of microns must be an integer
        if startPosition is None:
            sequence = [('xcu_r1', " motors moveCcd %s=%i microns abs" % (motor, lowBound), 5)]
        else:
            sequence = [('xcu_r1', " motors moveCcd a=%i b=%i c=%i microns abs" \
                         % (startPosition[0], startPosition[1], startPosition[2]), 5)]
        sequence += [('xcu_r1', " motors status", 5)]
        sequence += seq_expTime

        for i in range(nbImage - 1):
            sequence += [('xcu_r1', " motors moveCcd %s=%i microns " % (motor, step[i]), 5)]
            sequence += seq_expTime

        return sequence
