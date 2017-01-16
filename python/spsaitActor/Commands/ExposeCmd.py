#!/usr/bin/env python


import numpy as np
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
            ('expose', '@(flat|arc|object) @(<exptime>) [<comment>]', self.doExposure),

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

        self.actor.stopExposure = False

        cmdKeys = cmd.cmd.keywords
        cmdCall = self.actor.cmdr.call
        enuKeys = self.actor.models['enu']
        ccdKeys = self.actor.models['ccd_r1']

        expTime = cmdKeys['exptime'].values[0]
        comment = "comment='%s'" % cmdKeys['comment'].values[0] if "comment" in cmdKeys else ""

        knownTypes = ["flat", "arc", "object"]
        for knownType in knownTypes:
            if knownType in cmdKeys:
                expType = knownType
                break

        if expTime <= 0:
            cmd.fail("text='expTime must be positive'")
            return

        [state, mode, position] = enuKeys.keyVarDict['shutters'].getValue()
        if not (state == "IDLE" and position == "close") or self.stopExposure:
            raise Exception("aborting exposure")

        cmdCall(actor='ccd_r1', cmdStr="wipe", forUserCmd=cmd)
        try:

            state = ccdKeys.keyVarDict['exposureState'].getValue()
            if state != "integrating" or self.stopExposure:
                raise Exception("aborting exposure")

            cmdCall(actor='enu', cmdStr="shutters expose exptime=%.3f" % expTime, forUserCmd=cmd)
            dateobs = enuKeys.keyVarDict['dateobs'].getValue()
            exptime = enuKeys.keyVarDict['exptime'].getValue()

            if np.isnan(exptime):
                raise Exception("aborting exposure")

            cmdCall(actor='ccd_r1', cmdStr="read %s exptime=%.3f obstime=%s" % (expType, exptime, dateobs),
                    forUserCmd=cmd)

            cmd.finish("text='exposure done exptime=%.2f'" % exptime)

        except Exception as e:

            cmdCall(actor='ccd_r1', cmdStr="clearExposure", forUserCmd=cmd)
            raise
