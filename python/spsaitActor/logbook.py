import sqlite3


class Logbook:
    engine = '///data/ait/ait-alignment.db'

    @staticmethod
    def newExperiment(experimentId, name, visitStart, visitEnd, seqtype, cmdStr, comments, anomalies=''):
        sqlRequest = """INSERT INTO Experiment VALUES (%i, '%s', %i, %i, '%s', '%s', '%s', '%s');""" % (experimentId,
                                                                                                        name,
                                                                                                        visitStart,
                                                                                                        visitEnd,
                                                                                                        seqtype,
                                                                                                        cmdStr,
                                                                                                        comments,
                                                                                                        anomalies)
        Logbook.newRow(sqlRequest=sqlRequest)

    @staticmethod
    def newExposure(exposureId, site, visit, obsdate, exptime, exptype, quality='junk'):

        sqlRequest = """INSERT INTO Exposure VALUES ('%s','%s', %i, '%s', %.3f, '%s', '%s');""" % (exposureId,
                                                                                                   site,
                                                                                                   visit,
                                                                                                   obsdate,
                                                                                                   exptime,
                                                                                                   exptype,
                                                                                                   quality)
        Logbook.newRow(sqlRequest=sqlRequest)

    @staticmethod
    def newCamExposure(camExposureId, exposureId, smId, arm):
        sqlRequest = """INSERT INTO CamExposure VALUES ('%s','%s', %i, '%s');""" % (camExposureId,
                                                                                    exposureId,
                                                                                    smId,
                                                                                    arm)

        Logbook.newRow(sqlRequest=sqlRequest)

    @staticmethod
    def newRow(sqlRequest):
        conn = sqlite3.connect(Logbook.engine)
        c = conn.cursor()
        try:
            c.execute(sqlRequest)
            conn.commit()

        except sqlite3.IntegrityError:
            pass

    @staticmethod
    def lastExperimentId():

        conn = sqlite3.connect(Logbook.engine)
        c = conn.cursor()
        c.execute("""SELECT MAX(experimentId) FROM Experiment""")
        (experimentId,) = c.fetchone()
        experimentId = experimentId if experimentId is not None else 0

        return experimentId

    @staticmethod
    def getInfo(visit):
        conn = sqlite3.connect(Logbook.engine)
        c = conn.cursor()
        c.execute(
            '''select visit,exptype,spectrograph,arm,quality from Exposure inner join CamExposure on Exposure.exposureId=CamExposure.exposureId where visit=%i''' % visit)
        return c.fetchall()

    @staticmethod
    def visitRange(experimentId):
        conn = sqlite3.connect(Logbook.engine)
        c = conn.cursor()

        c.execute('''select visitStart,visitEnd from Experiment where ExperimentId=%i''' % experimentId)
        [(visitStart, visitEnd)] = c.fetchall()

        return visitStart, visitEnd

    @staticmethod
    def newAnomalies(experimentId, anomalies):
        sqlRequest = 'UPDATE Experiment SET anomalies = "%s" WHERE experimentId=%i' % (anomalies.replace('"', ""),
                                                                                       experimentId)
        Logbook.newRow(sqlRequest=sqlRequest)
