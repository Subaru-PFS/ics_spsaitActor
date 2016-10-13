#!/usr/bin/env python


import datetime as dt
import time

import opscore.protocols.keys as keys
import opscore.protocols.types as types


class ExposeCmd(object):
    def __init__(self, actor):
        # This lets us access the rest of the actor.
        self.actor = actor
        # Declare the commands we implement. When the actor is started
        # these are registered with the parser, which will call the
        # associated methods when matched. The callbacks will be
        # passed a single argument, the parsed and typed command.
        #
        self.vocab = [
            ('expose', 'ping', self.ping),
            ('expose', 'status', self.status),
            ('expose', '<exptime>', self.doExposure)
        ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary("spsait_expose", (1, 1),
                                        keys.Key("exptime", types.Float(), help="The exposure time"),
                                        )

    def ping(self, cmd):
        """Query the actor for liveness/happiness."""

        cmd.finish("text='Present and (probably) well'")

    def status(self, cmd):
        """Report status and version; obtain and send current data"""

        cmd.inform('text="Present!"')
        cmd.finish()

    def doExposure(self, cmd):
        expTime = cmd.cmd.keywords['exptime'].values[0]
        if expTime > 0:
            cmdVar = self.actor.cmdr.call(actor='ccd_r1', cmdStr="wipe",
                                          forUserCmd=cmd)
            start = dt.datetime.now()
            cmdVar = self.actor.cmdr.call(actor='enu', cmdStr="shutters open",
                                          forUserCmd=cmd)
            time.sleep(expTime)
            cmd.inform("exptime=%.2f'" % (dt.datetime.now() - start).total_seconds())
            cmdVar = self.actor.cmdr.call(actor='enu', cmdStr="shutters close",
                                          forUserCmd=cmd)
            cmdVar = self.actor.cmdr.call(actor='ccd_r1', cmdStr="read",
                                          forUserCmd=cmd)

            cmd.finish("text='Exposure done'")
        else:
            cmd.finish("text='Wrong argument'")
