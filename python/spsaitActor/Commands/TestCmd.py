#!/usr/bin/env python


import opscore.protocols.keys as keys
import opscore.protocols.types as types
from enuActor.utils.wrap import threaded
from spsaitActor.sequencing import SubCmd


class TestCmd(object):
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
            ('test', '@(sequence) [<name>] [<comments>]', self.sequence),

        ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary("spsait_test", (1, 1),
                                        keys.Key("name", types.String(), help='experiment name'),
                                        keys.Key("comments", types.String(), help='operator comments'),
                                        )

    @threaded
    def sequence(self, cmd):
        cmdKeys = cmd.cmd.keywords
        name = cmdKeys['name'].values[0] if 'name' in cmdKeys else ''
        comments = cmdKeys['comments'].values[0] if 'comments' in cmdKeys else ''

        head = [SubCmd(actor='enu_sm1', cmdStr='rexm status')]
        tail = [SubCmd(actor='enu_sm1', cmdStr='bsh status')]
        sequence = [SubCmd(actor='enu_sm1', cmdStr='slit status')]
        sequence += [SubCmd(actor='spsait', cmdStr='single arc exptime=2.0', getVisit=True)]
        sequence += [SubCmd(actor='enu_sm1', cmdStr='slit status') for i in range(4)]

        self.actor.processSequence(cmd, sequence,
                                   head=head,
                                   tail=tail,
                                   seqtype='Test',
                                   name=name,
                                   comments=comments)
        cmd.finish()
