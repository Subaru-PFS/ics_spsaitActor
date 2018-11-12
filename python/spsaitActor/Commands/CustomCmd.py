#!/usr/bin/env python


import opscore.protocols.keys as keys
import opscore.protocols.types as types
from enuActor.utils.wrap import threaded


class CustomCmd(object):
    def __init__(self, actor):
        # This lets us access the rest of the actor.
        self.actor = actor

        # Declare the commands we implement. When the actor is started
        # these are registered with the parser, which will call the
        # associated methods when matched. The callbacks will be
        # passed a single argument, the parsed and typed command.
        #
        self.name = "test"
        self.vocab = [
            ('custom', '<sequence> [<name>] [<comments>]', self.customSequence),

        ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary("spsait_custom", (1, 1),
                                        keys.Key("name", types.String(), help='experiment name'),
                                        keys.Key("comments", types.String(), help='operator comments'),
                                        keys.Key("sequence", types.String() * (1,), help='cmdStr list to process'),
                                        )

    @threaded
    def customSequence(self, cmd):
        self.actor.resetSequence()
        cmdKeys = cmd.cmd.keywords
        name = cmdKeys['name'].values[0] if 'name' in cmdKeys else ''
        comments = cmdKeys['comments'].values[0] if 'comments' in cmdKeys else ''
        sequence = self.actor.subCmdList(cmdKeys['sequence'].values)

        self.actor.processSequence(cmd, sequence,
                                   seqtype='custom',
                                   name=name,
                                   comments=comments)
        cmd.finish()
