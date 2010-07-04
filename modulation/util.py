# -*- coding: utf-8 -*-
# Copyright 2010 Trever Fischer <tdfischer@fedoraproject.org>
#
# This file is part of modulation.
#
# modulation is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# modulation is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with modulation. If not, see <http://www.gnu.org/licenses/>.

import modulation
from modulation import Plugin, ExceptionPacket, KillAllPacket
from modulation.controls import Enqueue, Next
from modulation.notifications import PlaybackComplete
import threading
import sqlite3

class ExceptionHandler(Plugin):
    def __init__(self):
        Plugin.__init__(self)
    @modulation.input(ExceptionPacket)
    def handleException(self, pkt):
        self._log.error("%s: %s", type(pkt.exception), pkt.exception)
        self.kill()
        self.killall()
    def killall(self):
        for node in modulation.allNodes():
            node.acceptPacket(KillAllPacket(node))

class MediaBuffer(Plugin):
    """A MediaBuffer keeps an internal list of MediaObjects. When a PlaybackComplete is sensed, the queue moves on to the next one. As long as the number of elements in the queue is less than the size, it will send out media.
    
    To add packets, send Enqueue
    """
    def __init__(self, size=5):
        Plugin.__init__(self)
        self.__queue = []
        self.__size = size;
        self.__needed = True
    
    @modulation.input(modulation.controls.Next)
    @modulation.input(PlaybackComplete)
    def sendNext(self, pkt=None):
        self.__needed = True
        self._log.info("Sending next packet")
        try:
            next = self.__queue.pop()
            self.send(next)
        except (IndexError):
            pass
        if (len(self.__queue) < self.__size):
            self._log.info("Empty buffer. Requesting more.")
            self.send(Next(self))

    @modulation.input(modulation.media.MediaPacket)
    def enqueue(self, pkt):
        if (len(self.__queue) == 0 and self.__needed):
            self._log.info("Empty buffer. Passing it through.")
            self.send(pkt)
        else:
            self.__queue.insert(0, pkt)
        self.__needed = False
        if (len(self.__queue) < self.__size):
            self._log.info("Low buffer. Requesting more.")
            self.send(Next(self))

    def __len__(self):
        return len(self.__queue)

    def __getitem__(self, key):
        return self.__queue[key]

class PacketFilter(Plugin):
    """Only permits one type of packet through"""
    def __init__(self, type):
        Plugin.__init__(self)
        self.__type = type

    def handlePacket(self, pkt):
        super(PacketFilter, self).handlePacket(pkt)
        if (isinstance(pkt, self.__type)):
            self.send(pkt)

class ThreadingSqliteDB(object):
    def __init__(self, dbpath):
        self.__path = dbpath
        self.__lock = threading.Lock()
        self.__owner = None
        self.__lockDepth = 0

    def __enter__(self):
        if (self.__owner != threading.current_thread()):
            self.__lock.acquire()
            self.__owner = threading.current_thread()
        self.__lockDepth+=1
        db = sqlite3.connect(self.__path)
        db.row_factory = sqlite3.Row
        db.text_factory = str
        return db

    def __exit__(self, type, value, traceback):
        self.__lockDepth-=1
        if (self.__lockDepth == 0):
            self.__lock.release()
            self.__owner = None

class EndNodeException(Exception):
    pass


class File:
    def __init__(self, file):
        self.__log = logging.getLogger("File")
        self.path = file
        self.__matches = None
        self.__track = None
        self.__fingerprint = None
        self.__puid = None
        self.__tags = None
        self.__tagref = None
        self.__properties = None
    
    def getMusicbrainz(self):
        if self.__matches is None:
            self.__log.debug("Loading musicbrainz data")
            if self.puid is None:
                raise TagError, "No PUID could be found."
            q = musicbrainz2.webservice.Query()
            filter = musicbrainz2.webservice.TrackFilter(puid=self.puid)
            self.__matches = q.getTracks(filter)
            self.__log.debug("Loaded musicbrainz data.")
        return self.__matches
    
    def getTrack(self):
        if self.__track is None and len(self.musicbrainz) > 0:
            self.__track = self.musicbrainz[0].track
        return self.__track
    
    def setTrack(self, id):
        self.__track = self.__matches[0].track
    
    def getFingerprint(self):
        if self.__fingerprint is None:
            self.__log.debug("Fingerprinting")
            self.__fingerprint = musicdns.create_fingerprint(self.path)[0]
            self.__log.debug("Fingerprinted.")
        return self.__fingerprint
    
    def getPUID(self):
        if self.__puid is None:
            self.__log.debug("Requesting PUID")
            fingerprint = self.fingerprint
            time = self.properties.length*1000
            self.__puid = musicdns.lookup_fingerprint(fingerprint, time, MUSICDNS_KEY)
            self.__log.debug("Got PUID")
        return self.__puid

    def getProperties(self):
        if self.__properties is None:
            self.__properties = self.__getTagRef().audioProperties()
        return self.__properties

    def getTags(self):
        if self.__tags is None:
            self.__tags = self.__getTagRef().tag()
        return self.__tags

    def writeTags(self):
        self.__getTagRef().save()

    def __getTagRef(self):
        if self.__tagref is None:
            self.__log.debug("Getting taglib data")
            self.__tagref = tagpy.FileRef(self.path)
            if self.__tagref.isNull():
                raise IOError, "%s is in a format unsupported by taglib" % self.path
            self.__log.debug("Got taglib data")
        return self.__tagref

    properties = property(getProperties, None, None, "The file's properties such as bitrate, length, etc")
    musicbrainz = property(getMusicbrainz, None, None, "The list of possible musicbrainz matches")
    mbTrack = property(getTrack, None, None, "The best result for a track object from musicbrainz")
    fingerprint = property(getFingerprint, None, None, "The file's musicdns fingerprint")
    puid = property(getPUID, None, None, "The file's musicdns PUID")
    tags = property(getTags, None, None, "The tags found in the file")
    
    def __str__(self):
        return self.path
    
    def __repr__(self):
        return "<%s '%s'>" % (self.__class__.__name__, self.path)

