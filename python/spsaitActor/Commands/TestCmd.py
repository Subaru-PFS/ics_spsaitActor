#!/usr/bin/env python


import random
import sys

import opscore.protocols.keys as keys
import opscore.protocols.types as types
from spsaitActor.utils import threaded, formatException


class TestCmd(object):
    def __init__(self, actor):
        # This lets us access the rest of the actor.
        self.actor = actor
        # Declare the commands we implement. When the actor is started
        # these are registered with the parser, which will call the
        # associated methods when matched. The callbacks will be
        # passed a single argument, the parsed and typed command.
        #
        self.name = "test"
        self.vocab = [
            ('exptes', 'flat <exptime> [@(blue|red)] [<attenuator>] [switchOff]', self.test),
            ('exptes', 'arc <exptime> [@(neon|hgar|xenon)] [@(blue|red)] [<attenuator>] [switchOff]', self.test),
            ('exptes', '<nbias>  [@(blue|red)]', self.test),
            ('tesalign', 'throughfocus <nb> <exptime> <lowBound> <upBound> [<motor>] [@(neon|hgar|xenon)] [switchOff] [<attenuator>] [<startPosition>] [<midPosition>]  [@(blue|red)]', self.test),
            ('dithes','<nb> <exptime> <shift> [@(microns|pixels)] [<attenuator>] [<duplicate>] [switchOff]  [@(blue|red)]', self.test),
            ('backtes', '<nb> <exptime>  [@(blue|red)] [force]', self.test),
            ('darktes', '<ndarks> <exptime>  [@(blue|red)]', self.test),
            ('calibtes', '[<nbias>] [<ndarks>]  [@(blue|red)] [<exptime>]', self.test),
            ('stabtest', '<exptime> <nb> <delay> [@(neon|hgar|xenon)]  [@(blue|red)] [<attenuator>] [switchOff]', self.test)

        ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary("spsait_tesalign", (1, 1),
                                        keys.Key("exptime", types.Float() * (1,), help="The exposure time(s)"),
                                        keys.Key("nb", types.Int(), help="Number of position"),
                                        keys.Key("upBound", types.Float(), help="lower bound for through focus"),
                                        keys.Key("highBound", types.Float(), help="higher bound for through focus"),
                                        keys.Key("motor", types.String(), help="optional to move a single motor"),
                                        keys.Key("startPosition", types.Float() * (1, 3), help="Start from this position a,b,c.\
                                         The 3 motors positions are required. If it is not set the lowBound position is used. "),
                                        keys.Key("midPosition", types.Float() * (1, 3), help="Start from this position a,b,c.\
                                         The 3 motors positions are required. If it is not set the lowBound position is used. "),
                                        keys.Key("nbias", types.Int(),
                                                 help='number of biases to take'),
                                        keys.Key("ndarks", types.Int(), help="Number of darks"),
                                        keys.Key("attenuator", types.Int(), help="optional attenuator value"),
                                        keys.Key("duplicate", types.Int(),
                                                 help="duplicate number of flat per position(1 is default)"),
                                        )

    @property
    def controller(self):
        try:
            return self.actor.controllers[self.name]
        except KeyError:
            raise RuntimeError('%s controller is not connected.' % self.name)

    @threaded
    def test(self, cmd):
        r = random.randint(0, 1)
        ender = cmd.finish if r == 0 else cmd.fail
        ender("text='test finished'")

    @threaded
    def sequence(self, cmd):
        arm = 'red'
        try:
            sequence = self.controller.test(arm)
            self.actor.processSequence(self.name, cmd, sequence)
        except Exception as e:
            cmd.fail("text='%s'" % formatException(e, sys.exc_info()[2]))
            return

        cmd.finish("text='Test is over'")