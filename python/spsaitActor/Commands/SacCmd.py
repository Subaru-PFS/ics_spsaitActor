#!/usr/bin/env python


import opscore.protocols.keys as keys
import opscore.protocols.types as types
from spsaitActor.utils import threaded
from spsaitActor.utils.sequencing import CmdList
import numpy as np

class SacCmd(object):
    def __init__(self, actor):
        # This lets us access the rest of the actor.
        self.actor = actor
        # Declare the commands we implement. When the actor is started
        # these are registered with the parser, which will call the
        # associated methods when matched. The callbacks will be
        # passed a single argument, the parsed and typed command.
        #
        self.name = "sac"
        self.vocab = [
            ('sac',
             '@(expose|background) <exptime> [<duplicate>] [<name>] [<comments>] [<head>] [<tail>]', self.expose),
            ('sac',
             'align <exptime> <position> <focus> [<duplicate>] [<name>] [<comments>] [<head>] [<tail>]', self.sacAlign),
            ('sac',
             'throughfocus <exptime> <position> [<duplicate>] [<name>] [<comments>] [<head>] [<tail>]', self.sacTF),
        ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary("spsait_sac", (1, 1),
                                        keys.Key("exptime", types.Float(), help="The exposure time"),
                                        keys.Key("focus", types.Float(), help="sac ccd stage absolute position"),
                                        keys.Key("position", types.Float() * (1, 3),
                                                 help="slit/motor position for throughfocus same args as np.linspace"),
                                        keys.Key("duplicate", types.Int(),
                                                 help="exposure duplicate per position (1 is default)"),
                                        keys.Key("name", types.String(), help='experiment name'),
                                        keys.Key("comments", types.String(), help='operator comments'),
                                        keys.Key("head", types.String() * (1,), help='cmdStr list to process before'),
                                        keys.Key("tail", types.String() * (1,), help='cmdStr list to process after'),
                                        )

    @property
    def controller(self):
        try:
            return self.actor.controllers[self.name]
        except KeyError:
            raise RuntimeError('%s controller is not connected.' % self.name)

    @threaded
    def expose(self, cmd):
        self.actor.resetSequence()
        cmdKeys = cmd.cmd.keywords

        exptime = cmdKeys['exptime'].values[0]
        duplicate = cmdKeys['duplicate'].values[0] if 'duplicate' in cmdKeys else 1
        exptype = 'expose' if 'expose' in cmdKeys else 'background'

        name = cmdKeys['name'].values[0] if 'name' in cmdKeys else ''
        comments = cmdKeys['comments'].values[0] if 'comments' in cmdKeys else ''
        head = CmdList(cmdKeys['head'].values) if 'head' in cmdKeys else []
        tail = CmdList(cmdKeys['tail'].values) if 'tail' in cmdKeys else []

        sequence = self.controller.expose(exptime=exptime,
                                          exptype=exptype,
                                          duplicate=duplicate)

        self.actor.processSequence(cmd, sequence,
                                   seqtype='sac%s' % exptype.capitalize(),
                                   name=name,
                                   comments=comments,
                                   head=head,
                                   tail=tail)

        cmd.finish()

    @threaded
    def sacAlign(self, cmd):
        self.actor.resetSequence()
        cmdKeys = cmd.cmd.keywords

        exptime = cmdKeys['exptime'].values[0]
        positions = np.linspace(*cmdKeys['position'].values)
        focus = cmdKeys['focus'].values[0]

        duplicate = cmdKeys['duplicate'].values[0] if 'duplicate' in cmdKeys else 1

        name = cmdKeys['name'].values[0] if 'name' in cmdKeys else ''
        comments = cmdKeys['comments'].values[0] if 'comments' in cmdKeys else ''
        head = CmdList(cmdKeys['head'].values) if 'head' in cmdKeys else []
        tail = CmdList(cmdKeys['tail'].values) if 'tail' in cmdKeys else []

        sequence = self.controller.sacalign(exptime=exptime,
                                            positions=positions,
                                            focus=focus,
                                            duplicate=duplicate)

        self.actor.processSequence(cmd, sequence,
                                   seqtype='sacAlignment',
                                   name=name,
                                   comments=comments,
                                   head=head,
                                   tail=tail)

        cmd.finish()

    @threaded
    def sacTF(self, cmd):
        self.actor.resetSequence()
        cmdKeys = cmd.cmd.keywords

        exptime = cmdKeys['exptime'].values[0]
        positions = np.linspace(*cmdKeys['position'].values)
        duplicate = cmdKeys['duplicate'].values[0] if 'duplicate' in cmdKeys else 1

        name = cmdKeys['name'].values[0] if 'name' in cmdKeys else ''
        comments = cmdKeys['comments'].values[0] if 'comments' in cmdKeys else ''
        head = CmdList(cmdKeys['head'].values) if 'head' in cmdKeys else []
        tail = CmdList(cmdKeys['tail'].values) if 'tail' in cmdKeys else []

        sequence = self.controller.sacTF(exptime=exptime,
                                         positions=positions,
                                         duplicate=duplicate)

        self.actor.processSequence(cmd, sequence,
                                   seqtype='sacThroughFocus',
                                   name=name,
                                   comments=comments,
                                   head=head,
                                   tail=tail)

        cmd.finish()
