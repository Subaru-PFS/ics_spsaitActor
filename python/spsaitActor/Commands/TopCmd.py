#!/usr/bin/env python


import opscore.protocols.keys as keys


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
            ('stop', '', self.stop),
        ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary("spsait_spsait", (1, 1),
                                        )

    def ping(self, cmd):
        """Query the actor for liveness/happiness."""

        cmd.finish("text='Present and (probably) well'")

    def status(self, cmd):
        """Report status and version; obtain and send current data"""

        cmd.inform('text="Present!"')
        cmd.finish()

    def stop(self, cmd):
        self.actor.sequenceOnGoing = False
        cmd.finish("text='Stopping current sequence'")
