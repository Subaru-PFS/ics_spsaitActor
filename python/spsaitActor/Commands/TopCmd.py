#!/usr/bin/env python


import opscore.protocols.keys as keys
import opscore.protocols.types as types
from spsaitActor.sequencing import SubCmd

class TopCmd(object):
    def __init__(self, actor):
        # This lets us access the rest of the actor.
        self.actor = actor

        # Declare the commands we implement. When the actor is started
        # these are registered with the parser, which will call the
        # associated methods when matched. The callbacks will be
        # passed a single argument, the parsed and typed command.
        #
        self.vocab = [
            ('ping', '', self.ping),
            ('status', '', self.status),
            ('adjust', 'slitalign <exptime>', self.adjust),
            ('test', '', self.test),
            ('abort', '', self.abort),
        ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary("spsait_spsait", (1, 1),
                                        keys.Key("exptime", types.Float(), help="The exposure time"),
                                        )

    def ping(self, cmd):
        """Query the actor for liveness/happiness."""

        cmd.finish("text='Present and (probably) well'")

    def status(self, cmd):
        """Report status and version; obtain and send current data"""

        cmd.inform('text="Present!"')
        cmd.finish()

    def abort(self, cmd):

        self.actor.doStop = True
        self.actor.abortShutters(cmd)

        cmd.finish("text='Aborting'")

    def adjust(self, cmd):
        expTime = cmd.cmd.keywords['exptime'].values[0]
        if expTime > 0:
            self.actor.expTime = expTime
            cmd.finish("text='Adjusting exptime to %.2f'" % expTime)
        else:
            cmd.fail("text='expTime must be positive'")

    def test(self, cmd):

        print (type(cmd))
        print (cmd.rawCmd)

        cmd.fail('text="oups"')