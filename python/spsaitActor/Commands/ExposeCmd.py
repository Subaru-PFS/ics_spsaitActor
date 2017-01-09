#!/usr/bin/env python


import time

import opscore.protocols.keys as keys
import opscore.protocols.types as types
from wrap import threaded


class ExposeCmd(object):
    def __init__(self, actor):
        # This lets us access the rest of the actor.
        self.actor = actor
        # Declare the commands we implement. When the actor is started
        # these are registered with the parser, which will call the
        # associated methods when matched. The callbacks will be
        # passed a single argument, the parsed and typed command.
        #
        self.name = "expose"
        self.vocab = [
            ('expose', 'ping', self.ping),
            ('expose', 'status', self.status),
            ('expose', '@(<exptime>) @(bias|dark|flat|arc|object) [<comment>]', self.doExposure),
            ('expose', '@(test) <exptime>', self.test),
        ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary("spsait_expose", (1, 1),
                                        keys.Key("exptime", types.Float(), help="The exposure time"),
                                        keys.Key("comment", types.String(), help="user comment"),
                                        )



    @property
    def stopExposure(self):
        return self.actor.stopExposure

    def ping(self, cmd):
        """Query the actor for liveness/happiness."""

        cmd.finish("text='Present and (probably) well'")

    def status(self, cmd):
        """Report status and version; obtain and send current data"""

        cmd.inform('text="Present!"')
        cmd.finish()

    @threaded
    def doExposure(self, cmd):
        f = 0.1
        i = 0
        cmdKeys = cmd.cmd.keywords

        expTime = cmdKeys['exptime'].values[0]
        comment = "comment='%s'" % cmdKeys['comment'].values[0] if "comment" in cmdKeys else ""
        print comment
        knownTypes = ["bias", "dark", "flat", "arc", "object"]
        for knownType in knownTypes:
            if knownType in cmdKeys:
                expType = knownType
                break

        if expType in ["flat, arc", "object", "dark"] and expTime <= 0:
            cmd.fail("text='expTime must be positive'")
            return

        self.actor.cmdr.call(actor='ccd_r1', cmdStr="wipe", forUserCmd=cmd)
        # cmd.inform("text='%s %s'" % ('ccd_r1', "wipe"))
        if expType in ["flat, arc", "object"]:
            cmd.inform("integratingTime=%.2f" % expTime)
            self.actor.cmdr.call(actor='enu', cmdStr="shutters open", forUserCmd=cmd)
            # cmd.inform("text='%s %s'" % ('enu', "shutters open"))
            while (i < expTime // f) and not self.stopExposure:
                time.sleep(f)
                i += 1
            time.sleep(expTime % f)

            self.actor.cmdr.call(actor='enu', cmdStr="shutters close", forUserCmd=cmd)
            # cmd.inform("text='%s %s'" % ('enu', "shutters close"))
        elif expType == "dark":
            while (i < expTime // f) and not self.stopExposure:
                time.sleep(f)
                i += 1
            time.sleep(expTime % f)

        # self.actor.cmdr.call(actor='ccd_r1', cmdStr="read %s %s" % (expType, comment), forUserCmd=cmd)
        self.actor.cmdr.call(actor='ccd_r1', cmdStr="read %s" % expType, forUserCmd=cmd)
        # cmd.inform("text='%s %s'" % ('ccd_r1', 'read %s' % expType))
        cmd.finish("text='exposure done expTime=%.2f'" % (i * f + expTime % f))

    def test(self, cmd):
        cmdKeys = cmd.cmd.keywords
        expTime = cmdKeys['exptime'].values[0]
        cmd.inform("integratingTime=%.2f" % expTime)
        cmd.finish()