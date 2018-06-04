#!/usr/bin/env python


from builtins import object
import sys

import opscore.protocols.keys as keys
import opscore.protocols.types as types
from spsaitActor.utils import threaded


class DefocusCmd(object):
    def __init__(self, actor):
        # This lets us access the rest of the actor.
        self.actor = actor
        # Declare the commands we implement. When the actor is started
        # these are registered with the parser, which will call the
        # associated methods when matched. The callbacks will be
        # passed a single argument, the parsed and typed command.
        #
        self.name = "defocus"
        self.vocab = [
            ('defocus',
             '<exptime> <nbPosition> [@(neon|hgar|xenon)] [<attenuator>] [@(blue|red)] [<duplicate>] [switchOff]',
             self.defocus),
        ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary("spsait_defocus", (1, 1),
                                        keys.Key("exptime", types.Float() * (1,), help="The exposure time(s)"),
                                        keys.Key("nbPosition", types.Int(), help="Number of position"),
                                        keys.Key("attenuator", types.Int(), help="optional attenuator value"),
                                        keys.Key("duplicate", types.Int(),
                                                 help="duplicate number of flat per position(1 is default)"),
                                        )

    @property
    def controller(self):
        try:
            return self.actor.controllers[self.name]
        except KeyError:
            raise RuntimeError('%s controller is not connected.' % self.name)

    @threaded
    def defocus(self, cmd):
        ex = False
        optArgs = []

        cmdKeys = cmd.cmd.keywords
        cmdCall = self.actor.safeCall

        nbPosition = cmdKeys['nbPosition'].values[0]
        exptime = cmdKeys['exptime'].values[0]

        duplicate = cmdKeys['duplicate'].values[0] if "duplicate" in cmdKeys else 1
        switchOff = True if "switchOff" in cmdKeys else False
        attenCmd = "attenuator=%i" % cmdKeys['attenuator'].values[0] if "attenuator" in cmdKeys else ""

        arc = None
        arc = "neon" if "neon" in cmdKeys else arc
        arc = "hgar" if "hgar" in cmdKeys else arc
        arc = "xenon" if "xenon" in cmdKeys else arc

        optArgs = ['red'] if 'red' in cmdKeys else optArgs
        optArgs = ['blue'] if 'blue' in cmdKeys else optArgs

        optArgs += (['force'] if "force" in cmdKeys else [])

        if exptime <= 0:
            raise Exception("exptime must be > 0")
        if nbPosition <= 0:
            raise Exception("nbImage > 0")

        sequence = self.controller.defocus(exptime, arc, attenCmd, nbPosition, duplicate, -5.0, 5.0, optArgs)

        try:
            self.actor.processSequence(self.name, cmd, sequence)
            msg = 'Defocus sequence is over'
        except Exception as ex:
            msg = formatException(ex, sys.exc_info()[2])

        if arc is not None and switchOff:
            cmdCall(actor='dcb', cmdStr="%s off" % arc, timeLim=60, forUserCmd=cmd)

        ender = cmd.fail if ex else cmd.finish
        ender("text='%s'" % msg)
