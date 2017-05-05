#!/usr/bin/env python



import opscore.protocols.keys as keys
import opscore.protocols.types as types


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
            ('abort', '@(detalign|exposure|cryo|test)', self.abort),
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

        cmdKeys = cmd.cmd.keywords

        if "detalign" in cmdKeys:
            name = "detalign"
        elif "exposure" in cmdKeys:
            name = "exposure"
        elif "cryo" in cmdKeys:
            name = "cryo"
        elif "test" in cmdKeys:
            name = "test"

        self.actor.boolStop[name] = True
        if name in ["exposure", "detalign"]:
            self.actor.cmdr.call(actor='enu', cmdStr="shutters abort", forUserCmd=cmd)

        cmd.finish("text='Aborting %s sequence'" % name)

    def adjust(self, cmd):
        expTime = cmd.cmd.keywords['exptime'].values[0]
        if expTime > 0:
            self.actor.expTime = expTime
            cmd.finish("text='Adjusting exptime to %.2f'" % expTime)
        else:
            cmd.fail("text='expTime must be positive'")
