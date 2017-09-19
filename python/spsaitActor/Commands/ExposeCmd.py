#!/usr/bin/env python


import sys
import time
from functools import partial

import numpy as np
import opscore.protocols.keys as keys
import opscore.protocols.types as types
from spsaitActor.utils import threaded, formatException, FailExposure


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
            ('expose', '[object] <exptime> [<comment>] [@(blue|red)]', self.doExposure),
            ('expose', 'flat <exptime> [<attenuator>] [switchOff]', self.doFlat),
            ('expose', 'arc <exptime> [@(neon|hgar|xenon)] [<attenuator>] [switchOff]', self.doArc),
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
        self.actor.ccdState = {}
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

        if "neon" in cmdKeys:
            arcLamp = "neon"
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
                cmdCall(actor='dcb', cmdStr="%s on %s" % (arcLamp, attenCmd), timeLim=300, forUserCmd=cmd)

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

            cmdCall(actor='enu', cmdStr="shutters expose exptime=%.3f" % exptime, timeLim=exptime + 60, forUserCmd=cmd)
            dateobs = enuKeys.keyVarDict['dateobs'].getValue()
            exptime = enuKeys.keyVarDict['exptime'].getValue()

            if np.isnan(exptime):
                raise Exception("Exposure did not occur as expected (interlock ?) Aborting ... ")

            cmdCall(actor='ccd_r1', cmdStr="read %s exptime=%.3f obstime=%s" % (expType, exptime, dateobs),
                    timeLim=300, forUserCmd=cmd)

        except Exception as e:
            self.actor.processSequence(self.name, cmd, FailExposure('ccd_r1'))

        if arcLamp is not None and switchOff:
            cmdCall(actor='dcb', cmdStr="%s off" % arcLamp, timeLim=60, forUserCmd=cmd)

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

            cmdCall(actor='dcb', cmdStr="halogen on %s" % attenCmd, timeLim=300, forUserCmd=cmd)

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

            cmdCall(actor='enu', cmdStr="shutters expose exptime=%.3f" % exptime, timeLim=exptime + 60, forUserCmd=cmd)
            dateobs = enuKeys.keyVarDict['dateobs'].getValue()
            exptime = enuKeys.keyVarDict['exptime'].getValue()

            if np.isnan(exptime):
                raise Exception("Exposure did not occur as expected (interlock ?) Aborting ... ")

            cmdCall(actor='ccd_r1', cmdStr="read %s exptime=%.3f obstime=%s" % (expType, exptime, dateobs),
                    timeLim=300, forUserCmd=cmd)

        except Exception as e:
            self.actor.processSequence(self.name, cmd, FailExposure('ccd_r1'))

        if switchOff:
            cmdCall(actor='dcb', cmdStr="halogen off", timeLim=60, forUserCmd=cmd)

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
        arms = ['blue', 'red']

        arms = arms[1:] if 'red' in cmdKeys else arms
        arms = arms[:1] if 'blue' in cmdKeys else arms
        shutters = 'red' if 'red' in cmdKeys else ''
        exptime = cmdKeys['exptime'].values[0]
        expType = "object" if "object" in cmdKeys else "arc"

        try:
            if exptime <= 0:
                raise Exception("exptime must be positive")

            [state, mode, position] = enuKeys.keyVarDict['shutters'].getValue()
            if not (state == "IDLE" and position == "close") or self.stopExposure:
                raise Exception("Shutters are not in position")

        except Exception as e:
            cmd.fail("text='%s'" % formatException(e, sys.exc_info()[2]))
            return

        try:
            for arm in arms:
                ccd = self.actor.arm2ccd[arm]
                self.actor.ccdState[ccd] = True, None
                self.actor.allThreads[ccd].putMsg(partial(self.actor.operCcd, {'actor': ccd,
                                                                               'cmdStr': "wipe",
                                                                               "timeLim": 60,
                                                                               "forUserCmd": cmd}))

            self.waitAndHandle(state='integrating', timeout=20)

            cmdCall(actor='enu', cmdStr="shutters expose exptime=%.3f %s" % (exptime, shutters), timeLim=exptime + 60,
                    forUserCmd=cmd)
            dateobs = enuKeys.keyVarDict['dateobs'].getValue()
            exptime = enuKeys.keyVarDict['exptime'].getValue()

            if np.isnan(exptime):
                raise Exception("Shutters expose did not occur as expected (interlock ?) Aborting ... ")

            for ccd in self.actor.ccdDict:
                cmdStr = "read %s exptime=%.3f obstime=%s" % (expType, exptime, dateobs)
                self.actor.allThreads[ccd].putMsg(partial(self.actor.operCcd, {'actor': ccd,
                                                                               'cmdStr': cmdStr,
                                                                               'timeLim': 300,
                                                                               'forUserCmd': cmd}))

            self.waitAndHandle(state='reading', timeout=60)
            self.waitAndHandle(state='idle', timeout=180)

        except Exception as e:
            cmd.fail("text='%s'" % formatException(e, sys.exc_info()[2]))
            return

        arms = [self.actor.ccd2arm[ccd] for ccd in self.actor.ccdDict]
        cmd.finish("text='exposure done arms=%s exptime=%.2f'" % (','.join(arms), exptime))

    def waitAndHandle(self, state, timeout):
        t0 = time.time()

        while not (self.actor.checkState(state) and self.actor.ccdDict):

            if (time.time() - t0) > timeout:
                raise Exception("ccd %s timeout" % state)
            if self.stopExposure:
                raise Exception("ccd exposure interrupted by user")
            if not self.actor.ccdDict:
                raise Exception("ccd %s has failed"%state)
