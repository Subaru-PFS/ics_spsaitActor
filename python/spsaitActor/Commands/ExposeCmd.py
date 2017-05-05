#!/usr/bin/env python


import sys

import numpy as np
import opscore.protocols.keys as keys
import opscore.protocols.types as types
from spsaitActor.utils import threaded, formatException


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
            ('expose', 'object <exptime> [<comment>]', self.doExposure),
            ('expose', 'flat <exptime> [<attenuator>] [switchOff]', self.doFlat),
            ('expose', 'arc <exptime> [@(ne|hgar|xenon)] [<attenuator>] [switchOff]', self.doArc),
        ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary("spsait_expose", (1, 1),
                                        keys.Key("exptime", types.Float(), help="The exposure time"),
                                        keys.Key("comment", types.String(), help="user comment"),
                                        keys.Key("attenuator", types.Int(), help="optional attenuator value"),
                                        )

    @property
    def stopExposure(self):
        return self.actor.boolStop[self.name]

    def resetExposure(self):
        self.actor.boolStop[self.name] = False

    @threaded
    def doArc(self, cmd):
        self.resetExposure()
        e = False

        cmdKeys = cmd.cmd.keywords
        cmdCall = self.actor.safeCall
        enuKeys = self.actor.models['enu']
        ccdKeys = self.actor.models['ccd_r1']
        dcbKeys = self.actor.models['dcb']

        exptime = cmdKeys['exptime'].values[0]
        switchOff = True if "switchOff" in cmdKeys else False
        attenCmd = "attenuator=%i" % cmdKeys['attenuator'].values[0] if "attenuator" in cmdKeys else ""

        expType = "arc"

        if "ne" in cmdKeys:
            arcLamp = "ne"
        elif "hgar" in cmdKeys:
            arcLamp = "hgar"
        elif "xenon" in cmdKeys:
            arcLamp = "xenon"
        else:
            arcLamp = None

        try:
            if exptime <= 0:
                raise Exception("exptime must be positive")

            [state, mode, position] = enuKeys.keyVarDict['shutters'].getValue()
            if not (state == "IDLE" and position == "close") or self.stopExposure:
                raise Exception("Shutters are not in position")

            if arcLamp is not None:
                cmdCall(actor='dcb', cmdStr="switch arc=%s %s" % (arcLamp, attenCmd), timeLim=300, forUserCmd=cmd)

            flux = dcbKeys.keyVarDict['photodiode'].getValue()

            if np.isnan(flux) or flux == 0 or self.stopExposure:
                raise Exception("Flux is null")

        except Exception as e:
            cmd.fail("text='%s'" % formatException(e, sys.exc_info()[2]))
            return

        try:
            cmdCall(actor='ccd_r1', cmdStr="wipe", timeLim=60, forUserCmd=cmd)

            state = ccdKeys.keyVarDict['exposureState'].getValue()
            if state != "integrating" or self.stopExposure:
                raise Exception("ccd is not integrating")

            cmdCall(actor='enu', cmdStr="shutters expose exptime=%.3f" % exptime, forUserCmd=cmd)
            dateobs = enuKeys.keyVarDict['dateobs'].getValue()
            exptime = enuKeys.keyVarDict['exptime'].getValue()

            if np.isnan(exptime):
                raise Exception("Exposure did not occur as expected (interlock ?) Aborting ... ")

            cmdCall(actor='ccd_r1', cmdStr="read %s exptime=%.3f obstime=%s" % (expType, exptime, dateobs),
                    timeLim=300, forUserCmd=cmd)

        except Exception as e:
            cmdCall(actor='ccd_r1', cmdStr="clearExposure", forUserCmd=cmd)

        if arcLamp is not None and switchOff:
            cmdCall(actor='dcb', cmdStr="aten switch off channel=%s" % arcLamp, timeLim=60, forUserCmd=cmd)

        if e:
            cmd.fail("text='%s'" % formatException(e, sys.exc_info()[2]))
        else:
            cmd.finish("text='arc done exptime=%.2f'" % exptime)

    @threaded
    def doFlat(self, cmd):
        self.resetExposure()
        e = False

        cmdKeys = cmd.cmd.keywords
        cmdCall = self.actor.safeCall
        enuKeys = self.actor.models['enu']
        ccdKeys = self.actor.models['ccd_r1']
        dcbKeys = self.actor.models['dcb']

        exptime = cmdKeys['exptime'].values[0]
        switchOff = True if "switchOff" in cmdKeys else False
        attenCmd = "attenuator=%i" % cmdKeys['attenuator'].values[0] if "attenuator" in cmdKeys else ""
        expType = "flat"

        try:
            if exptime <= 0:
                raise Exception("exptime must be positive")

            [state, mode, position] = enuKeys.keyVarDict['shutters'].getValue()
            if not (state == "IDLE" and position == "close") or self.stopExposure:
                raise Exception("shutters not in position")

            cmdCall(actor='dcb', cmdStr="switch arc=halogen %s" % attenCmd, timeLim=300, forUserCmd=cmd)

            flux = dcbKeys.keyVarDict['photodiode'].getValue()

            if np.isnan(flux) or flux == 0 or self.stopExposure:
                raise Exception("flux is null")

        except Exception as e:
            cmd.fail("text='%s'" % formatException(e, sys.exc_info()[2]))
            return

        try:
            cmdCall(actor='ccd_r1', cmdStr="wipe", timeLim=60, forUserCmd=cmd)

            state = ccdKeys.keyVarDict['exposureState'].getValue()
            if state != "integrating" or self.stopExposure:
                raise Exception("ccd is not integrating")

            cmdCall(actor='enu', cmdStr="shutters expose exptime=%.3f" % exptime, forUserCmd=cmd)
            dateobs = enuKeys.keyVarDict['dateobs'].getValue()
            exptime = enuKeys.keyVarDict['exptime'].getValue()

            if np.isnan(exptime):
                raise Exception("Exposure did not occur as expected (interlock ?) Aborting ... ")

            cmdCall(actor='ccd_r1', cmdStr="read %s exptime=%.3f obstime=%s" % (expType, exptime, dateobs),
                    timeLim=300, forUserCmd=cmd)

        except Exception as e:
            cmdCall(actor='ccd_r1', cmdStr="clearExposure", forUserCmd=cmd)

        if switchOff:
            cmdCall(actor='dcb', cmdStr="labsphere switch off", timeLim=60, forUserCmd=cmd)

        if e:
            cmd.fail("text='%s'" % formatException(e, sys.exc_info()[2]))
        else:
            cmd.finish("text='flat done exptime=%.2f'" % exptime)

    @threaded
    def doExposure(self, cmd):
        self.resetExposure()

        cmdCall = self.actor.safeCall
        cmdKeys = cmd.cmd.keywords
        enuKeys = self.actor.models['enu']
        ccdKeys = self.actor.models['ccd_r1']

        exptime = cmdKeys['exptime'].values[0]
        comment = "comment='%s'" % cmdKeys['comment'].values[0] if "comment" in cmdKeys else ""

        expType = "object"

        try:
            if exptime <= 0:
                raise Exception("exptime must be positive")

            [state, mode, position] = enuKeys.keyVarDict['shutters'].getValue()
            if not (state == "IDLE" and position == "close") or self.stopExposure:
                raise Exception("shutters not in position")

        except Exception as e:
            cmd.fail("text='%s'" % formatException(e, sys.exc_info()[2]))
            return

        [state, mode, position] = enuKeys.keyVarDict['shutters'].getValue()
        if not (state == "IDLE" and position == "close") or self.stopExposure:
            raise Exception("aborting exposure")

        try:
            cmdCall(actor='ccd_r1', cmdStr="wipe", timeLim=60, forUserCmd=cmd)

            state = ccdKeys.keyVarDict['exposureState'].getValue()
            if state != "integrating" or self.stopExposure:
                raise Exception("aborting exposure")

            cmdCall(actor='enu', cmdStr="shutters expose exptime=%.3f" % exptime, forUserCmd=cmd)
            dateobs = enuKeys.keyVarDict['dateobs'].getValue()
            exptime = enuKeys.keyVarDict['exptime'].getValue()

            if np.isnan(exptime):
                raise Exception("Exposure did not occur as expected (interlock ?) Aborting ... ")

            cmdCall(actor='ccd_r1',
                    cmdStr="read %s exptime=%.3f obstime=%s %s" % (expType, exptime, dateobs, comment),
                    timeLim=300, forUserCmd=cmd)

        except Exception as e:
            cmdCall(actor='ccd_r1', cmdStr="clearExposure", forUserCmd=cmd)
            cmd.fail("text='%s'" % formatException(e, sys.exc_info()[2]))
            return

        cmd.finish("text='exposure done exptime=%.2f'" % exptime)
