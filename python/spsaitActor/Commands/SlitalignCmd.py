#!/usr/bin/env python


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
        ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary("spsait_slitalign", (1, 1),
                                        keys.Key("exptime", types.Float(), help="The exposure time"),
                                        )

    @threaded
    def loop(self, cmd):
        self.actor.sequenceOnGoing = True
        expTime = cmd.cmd.keywords['exptime'].values[0]
        if expTime > 0:
            while self.actor.sequenceOnGoing:
                cmdVar = self.actor.cmdr.call(actor='sac', cmdStr="exposure remote exptime=%.2f" % expTime,
                                              forUserCmd=cmd)
                time.sleep(0.5)
            else:
                cmd.finish("text='Exposure Loop is over'")
        else:
            cmd.fail("text='exptime must be positive'")
