#!/usr/bin/env python


import opscore.protocols.keys as keys
import opscore.protocols.types as types
from enuActor.utils.wrap import threaded

class SingleCmd(object):
    def __init__(self, actor):
        # This lets us access the rest of the actor.
        self.actor = actor
        # Declare the commands we implement. When the actor is started
        # these are registered with the parser, which will call the
        # associated methods when matched. The callbacks will be
        # passed a single argument, the parsed and typed command.
        #
        self.name = "single"
        self.vocab = [
            ('single', '[@(object|arc|flat)] <exptime> [<cams>]', self.doExposure),

        ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary("spsait_single", (1, 1),
                                        keys.Key("exptime", types.Float(), help="The exposure time"),
                                        keys.Key("cams", types.String() * (1,),
                                                 help='list of camera to take exposure from'),

                                        )

    @property
    def controller(self):
        try:
            return self.actor.controllers[self.name]
        except KeyError:
            raise RuntimeError('%s controller is not connected.' % self.name)

    @property
    def doStop(self):
        return self.actor.doStop

    @threaded
    def doExposure(self, cmd):
        cmdKeys = cmd.cmd.keywords
        imtype = 'object'
        imtype = 'arc' if 'arc' in cmdKeys else imtype
        imtype = 'flat' if 'flat' in cmdKeys else imtype

        exptime = cmdKeys['exptime'].values[0]
        cams = cmdKeys['cams'].values if 'cams' in cmdKeys else False

        self.controller.resetExposure()
        self.controller.expose(cmd=cmd,
                               imtype=imtype,
                               exptime=exptime,
                               cams=cams)

        cmd.finish()





