import sqlite3



class Logbook:
    engine = '///home/arnaud/data/ait/ait-operation.db'

    @staticmethod
    def getExperimentId():

        conn = sqlite3.connect(Logbook.engine)
        c = conn.cursor()
        c.execute("""SELECT MAX(experimentId) FROM Experiment""")
        (experimentId,) = c.fetchone()
        return experimentId

    @staticmethod
    def newExposure(exposureId, site, visit, obsdate, exptime, exptype, quality):

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
    def getInfo(visit):
        conn = sqlite3.connect(Logbook.engine)
        c = conn.cursor()
        c.execute(
            '''select visit,exptype,spectrograph,arm,quality from Exposure inner join CamExposure on Exposure.exposureId=CamExposure.exposureId where visit=%i''' % visit)
        return c.fetchall()

