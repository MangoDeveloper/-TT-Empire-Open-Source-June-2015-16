from direct.distributed.PyDatagram import PyDatagram
from direct.distributed.MsgTypes import CLIENTAGENT_EJECT

from otp.ai.AIBaseGlobal import *
from otp.ai.MagicWordGlobal import *
from otp.avatar import DistributedAvatarAI
from otp.avatar import PlayerBase
from otp.distributed import OtpDoGlobals
from otp.otpbase import OTPLocalizer

class DistributedPlayerAI(DistributedAvatarAI.DistributedAvatarAI, PlayerBase.PlayerBase):

    def __init__(self, air):
        DistributedAvatarAI.DistributedAvatarAI.__init__(self, air)
        PlayerBase.PlayerBase.__init__(self)
        self.friendsList = []
        self.DISLid = 0
        self.adminAccess = 0

    def announceGenerate(self):
        DistributedAvatarAI.DistributedAvatarAI.announceGenerate(self)
        self._doPlayerEnter()

    def _announceArrival(self):
        self.sendUpdate('arrivedOnDistrict', [self.air.districtId])

    def _announceExit(self):
        self.sendUpdate('arrivedOnDistrict', [0])

    def _sendExitServerEvent(self):
        self.air.writeServerEvent('avatarExit', self.doId, '')

    def delete(self):
        self._doPlayerExit()
        DistributedAvatarAI.DistributedAvatarAI.delete(self)

    @staticmethod
    def isPlayerControlled():
        return True

    def setLocation(self, parentId, zoneId):
        DistributedAvatarAI.DistributedAvatarAI.setLocation(self, parentId, zoneId)
        if self.isPlayerControlled():
            if not self.air._isValidPlayerLocation(parentId, zoneId):
                self.notify.info('booting player %s for doing setLocation to (%s, %s)' % (self.doId, parentId, zoneId))
                self.air.writeServerEvent('suspicious', self.doId, 'invalid setLocation: (%s, %s)' % (parentId, zoneId))
                self.requestDelete()

    def _doPlayerEnter(self):
        self.incrementPopulation()
        self._announceArrival()

    def _doPlayerExit(self):
        self._announceExit()
        self.decrementPopulation()

    def incrementPopulation(self):
        self.air.incrementPopulation()

    @staticmethod
    def decrementPopulation():
        simbase.air.decrementPopulation()

    def d_setMaxHp(self, maxHp):
        DistributedAvatarAI.DistributedAvatarAI.d_setMaxHp(self, maxHp)
        self.air.writeServerEvent('setMaxHp', self.doId, '%s' % maxHp)

    def d_setSystemMessage(self, aboutId, chatString):
        self.sendUpdate('setSystemMessage', [aboutId, chatString])

    def d_friendsNotify(self, avId, status):
        self.sendUpdate('friendsNotify', [avId, status])

    def friendsNotify(self, avId, status):
        pass

    def setDISLid(self, id):
        self.DISLid = id

    def getDISLid(self):
        return self.DISLid

    def d_setFriendsList(self, friendsList):
        self.sendUpdate('setFriendsList', [friendsList])

    def setFriendsList(self, friendsList):
        self.friendsList = friendsList
        self.notify.debug('setting friends list to %s' % self.friendsList)

    def getFriendsList(self):
        return self.friendsList

    def setAdminAccess(self, access):
        self.adminAccess = access

    def d_setAdminAccess(self, access):
        self.sendUpdate('setAdminAccess', [access])

    def b_setAdminAccess(self, access):
        self.setAdminAccess(access)
        self.d_setAdminAccess(access)

    def getAdminAccess(self):
        return self.adminAccess

    def isAdmin(self):
        return self.adminAccess >= MINIMUM_MAGICWORD_ACCESS

    def extendFriendsList(self, friendId):
        if friendId in self.friendsList:
            return

        self.friendsList.append(friendId)

@magicWord(category=CATEGORY_LEADER, types=[str])
def system(message):
    """
    Broadcast a <message> to the game server.
    """
    message = 'ADMIN: ' + message
    dclass = simbase.air.dclassesByName['ClientServicesManager']
    dg = dclass.aiFormatUpdate('systemMessage',
                               OtpDoGlobals.OTP_DO_ID_CLIENT_SERVICES_MANAGER,
                               10, 1000000, [message])
    simbase.air.send(dg)

@magicWord(category=CATEGORY_LEADER, types=[int])
def maintenance(minutes):
    """
    Initiate the maintenance message sequence. It will last for the specified
    amount of <minutes>.
    """
    def disconnect(task):
        dg = PyDatagram()
        dg.addServerHeader(10, simbase.air.ourChannel, CLIENTAGENT_EJECT)
        dg.addUint16(154)
        dg.addString('Toontown Empire is now closed for maintenance.')
        simbase.air.send(dg)
        return Task.done

    def countdown(minutes):
        if minutes > 0:
            system(OTPLocalizer.CRMaintenanceCountdownMessage % minutes)
        else:
            system(OTPLocalizer.CRMaintenanceMessage)
            taskMgr.doMethodLater(10, disconnect, 'maintenance-disconnection')
        if minutes <= 5:
            next = 60
            minutes -= 1
        elif minutes % 5:
            next = 60 * (minutes%5)
            minutes -= minutes % 5
        else:
            next = 300
            minutes -= 5
        if minutes >= 0:
            taskMgr.doMethodLater(next, countdown, 'maintenance-task',
                                  extraArgs=[minutes])


    countdown(minutes)

@magicWord(category=CATEGORY_LEAD_STAFF, types=[str, str, int])
def accessLevel(accessLevel, storage='PERSISTENT', showGM=1):
    """
    Modify the target's access level.
    """
    accessName2Id = {
        'trial': CATEGORY_TRIAL.defaultAccess,
        'Trial': CATEGORY_TRIAL.defaultAccess,
        't': CATEGORY_TRIAL.defaultAccess,
        'staff': CATEGORY_STAFF.defaultAccess,
        'Staff': CATEGORY_STAFF.defaultAccess,
        's': CATEGORY_STAFF.defaultAccess,
        'lead-staff': CATEGORY_LEAD_STAFF.defaultAccess,
        'leadstaff': CATEGORY_LEAD_STAFF.defaultAccess,
        'ls': CATEGORY_LEAD_STAFF.defaultAccess,
        'developer': CATEGORY_DEVELOPER.defaultAccess,
        'dev': CATEGORY_DEVELOPER.defaultAccess,
        'd': CATEGORY_DEVELOPER.defaultAccess,
        'leader': CATEGORY_LEADER.defaultAccess,
        'founder': CATEGORY_LEADER.defaultAccess,
        'l': CATEGORY_LEADER.defaultAccess
    }
    try:
        accessLevel = int(accessLevel)
    except:
        if accessLevel not in accessName2Id:
            return 'Invalid access level!'
        accessLevel = accessName2Id[accessLevel]
    if accessLevel not in accessName2Id.values():
        return 'Invalid access level!'
    target = spellbook.getTarget()
    invoker = spellbook.getInvoker()
    if invoker == target:
        return "You can't set your own access level!"
    if not accessLevel < invoker.getAdminAccess():
        return "The target's access level must be lower than yours!"
    if target.getAdminAccess() == accessLevel:
        return "%s's access level is already %d!" % (target.getName(), accessLevel)
    target.b_setAdminAccess(accessLevel)
    if showGM:
        target.b_setGM(accessLevel)
    temporary = storage.upper() in ('SESSION', 'TEMP', 'TEMPORARY')
    if not temporary:
        target.air.dbInterface.updateObject(
            target.air.dbId,
            target.getDISLid(),
            target.air.dclassesByName['AccountAI'],
            {'ADMIN_ACCESS': accessLevel})
    if not temporary:
        target.d_setSystemMessage(0, '%s set your access level to %d!' % (invoker.getName(), accessLevel))
        return "%s's access level has been set to %d." % (target.getName(), accessLevel)
    else:
        target.d_setSystemMessage(0, '%s set your access level to %d temporarily!' % (invoker.getName(), accessLevel))
        return "%s's access level has been set to %d temporarily." % (target.getName(), accessLevel)