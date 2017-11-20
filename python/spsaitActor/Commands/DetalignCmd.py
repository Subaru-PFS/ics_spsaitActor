#!/usr/bin/env python


import sys

import numpy as np
import opscore.protocols.keys as keys
import opscore.protocols.types as types
from spsaitActor.utils import threaded, formatException


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
             'throughfocus <nb> <exptime> <lowBound> <upBound> [<motor>] [@(neon|hgar|xenon)] [<attenuator>] [<startPosition>] [<midPosition>] [switchOff] [@(blue|red)]',
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
                                         The 3 motors positions are required. If it is not set the lowBound position is used. "),
                                        keys.Key("midPosition", types.Float() * (1, 3), help="Start from this position a,b,c.\
                                         The 3 motors positions are required. If it is not set the lowBound position is used. ")
                                        )

    @property
    def controller(self):
        try:
            return self.actor.controllers[self.name]
        except KeyError:
            raise RuntimeError('%s controller is not connected.' % self.name)

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

        arms = ['blue', 'red']

        arms = arms[1:] if 'red' in cmdKeys else arms
        arms = arms[:1] if 'blue' in cmdKeys else arms

        if "midPosition" in cmdKeys:
            midPosition = cmdKeys['midPosition'].values

            upmargin = 300 - np.max(midPosition)
            lowmargin = np.min(midPosition)
            margin = np.min([upmargin, lowmargin])

            lowBound = np.min(midPosition) - margin
            upBound = np.max(midPosition) + margin

            startPosition = midPosition - np.min(midPosition) + lowBound
            upBound -= (np.max(midPosition) - np.min(midPosition))

        arc = None
        arc = "neon" if "neon" in cmdKeys else arc
        arc = "hgar" if "hgar" in cmdKeys else arc
        arc = "xenon" if "xenon" in cmdKeys else arc

        if True in [True if exptime <= 0 else False for exptime in expTimes]:
            raise Exception("exptime must be > 0")

        if nbImage <= 1:
            raise Exception("nbImage must be > 1")

        sequence = self.controller.buildThroughFocus(arc, attenCmd, nbImage, expTimes, lowBound, upBound, motor,
                                                     startPosition, arms)

        try:
            self.actor.processSequence(self.name, cmd, sequence)
            msg = 'Through Focus is over'
        except Exception as e:
            msg = formatException(e, sys.exc_info()[2])

        if arc is not None and switchOff:
            cmdCall(actor='dcb', cmdStr="%s off" % arc, forUserCmd=cmd)

        ender = cmd.fail if e else cmd.finish
        ender("text='%s'" % msg)
