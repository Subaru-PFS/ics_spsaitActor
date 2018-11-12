location = dict(detectorAlignment='experimentLog',
                biases='experimentLog',
                darks='experimentLog',
                calib='experimentLog',
                imageStability='experimentLog',
                defocusedPsf='experimentLog',
                ditheredFlats='experimentLog',
                ditheredPsf='experimentLog',
                arcs='experimentLog',
                flats='experimentLog',
                slitAlignment='experimentLog-sac',
                sacExpose='experimentLog-sac',
                sacBackground='experimentLog-sac',
                sacAlignment='experimentLog-sac',
                sacThroughFocus='experimentLog-sac',
                )


def locate(seqtype):
    return location[seqtype]


def guess(subCmds):
    if True in [subCmd.actor == 'sac' for subCmd in subCmds]:
        return 'experimentLog-sac'

    return 'experimentLog'
