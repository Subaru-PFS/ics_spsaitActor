#!/usr/bin/env python

import sys

import opscore.protocols.keys as keys
import opscore.protocols.types as types
from spsaitActor.utils import threaded, CmdSeq, formatException, CryoException


class CryoCmd(object):
    def __init__(self, actor):
        # This lets us access the rest of the actor.
        self.actor = actor
        # Declare the commands we implement. When the actor is started
        # these are registered with the parser, which will call the
        # associated methods when matched. The callbacks will be
        # passed a single argument, the parsed and typed command.
        #
        self.name = "cryo"
        self.vocab = [
            ('pressure_rise', '@(r0|r1) [<duration>]', self.pressureTest),
            ('abort', 'cryo doNone', self.doSleep),
        ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary("spsait_cryo", (1, 1),
                                        keys.Key("arm", types.String(), help="CU Arm"),
                                        keys.Key("duration", types.Int(),
                                                 help="Pressure rising test duration in minute"),
                                        )

    @threaded
    def pressureTest(self, cmd):
        cmdKeys = cmd.cmd.keywords
        cmdCall = self.actor.safeCall
        found = False
        self.doNone = False
        duration = cmdKeys['duration'].values[0] if "duration" in cmdKeys else 30

        if duration < 2:
            cmd.fail("text='Test duration is too short'")
            return

        if "r0" in cmdKeys:
            arm = "r0"
        elif "r1" in cmdKeys:
            arm = "r1"

        xcuActor = 'xcu_%s' % arm
        xcuKeys = self.actor.models[xcuActor]

        cmdCall(actor=xcuActor, cmdStr="gatevalve status", timeLim=10, forUserCmd=cmd)
        cmdCall(actor=xcuActor, cmdStr="turbo status", timeLim=10, forUserCmd=cmd)
        cmdCall(actor=xcuActor, cmdStr="gauge status", timeLim=10, forUserCmd=cmd)

        turboSpeed = xcuKeys.keyVarDict['turboSpeed'].getValue()
        [word, position, controlState] = xcuKeys.keyVarDict['gatevalve'].getValue()
        pressure = xcuKeys.keyVarDict['pressure'].getValue()

        if not (turboSpeed == 90000 and position == "Open" and controlState == "Open" and pressure < 1e-4):
            cmd.fail("text='Can't do a pressure rise test'")
            return

        else:
            cmd.inform("press1=%.5e" % pressure)
            cmd.inform("gatevalve=%s,%s" % (position, controlState))

        seqClosing, seqCheck, seqOpening = self.buildSequence(xcuActor, duration)

        try:
            self.actor.processSequence(self.name, cmd, seqClosing)
            [word, position, controlState] = xcuKeys.keyVarDict['gatevalve'].getValue()
            if not (position == "Closed" and controlState == "Closed"):
                raise Exception("Gatevalve is not closed !")

            self.actor.processSequence(self.name, cmd, seqCheck)

        except CryoException as e:
            if self.doNone:
                cmd.fail("text='%s'" % formatException(e, sys.exc_info()[2]))
                return
            else:
                cmd.warn("text='%s'" % formatException(e, sys.exc_info()[2]))

        except Exception as e:
            cmd.fail("text='%s'" % formatException(e, sys.exc_info()[2]))
            return

        try:
            [word, position, controlState] = xcuKeys.keyVarDict['gatevalve'].getValue()
            pressure = xcuKeys.keyVarDict['pressure'].getValue()

            if not (position == "Closed" and controlState == "Closed" and turboSpeed == 90000):
                raise Exception("Impossible to open the gatevalve !")

            cmd.inform("press2=%.5e" % pressure)
            cmd.inform("gatevalve=%s,%s" % (position, controlState))

            self.actor.processSequence(self.name, cmd, seqOpening)
            [word, position, controlState] = xcuKeys.keyVarDict['gatevalve'].getValue()
            if not (position == "Open" and controlState == "Open"):
                raise Exception("Gatevalve is not open !")

        except Exception as e:
            cmd.fail("text='%s'" % formatException(e, sys.exc_info()[2]))
            return

        cmd.finish("text='Pressure rising test is over'")

    def buildSequence(self, xcuActor, duration):
        seqClosing = [CmdSeq(xcuActor, "gauge status"),
                      CmdSeq(xcuActor, "gatevalve close", tempo=5),
                      CmdSeq(xcuActor, "gatevalve status")]

        seqCheck = [CmdSeq(xcuActor, "gauge status", tempo=duration * 60),
                    CmdSeq(xcuActor, "gatevalve status"),
                    CmdSeq(xcuActor, "gauge status"),
                    CmdSeq(xcuActor, "turbo status")]

        seqOpening = [CmdSeq(xcuActor, "gatevalve open", tempo=5),
                      CmdSeq(xcuActor, "gatevalve status")]

        return seqClosing, seqCheck, seqOpening

    def doSleep(self, cmd):
        self.doNone = True
        self.actor.boolStop["cryo"] = True

        cmd.finish("text='Aborting cryo sequence doNone'")