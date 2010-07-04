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

from modulation import Packet, Plugin
import threading
class ControlPacket(Packet):
    """A ControlPacket gives some kind of control signal to a child plugin, such as "STOP", "PLAY", "SEARCH", "VOLUME", etc

    If a plugin handles the packet according to its intent (eg stopping playback on a stop packet), then the
    original packet must be forwarded with send(). If a plugin then does other actions (such as switching to
    a different stream and then playing), a new packet must be sent as well.

    If a plugin does something of its own accord (eg nobody told it to stop, but it is out of data so it must
    stop anyways), a new packet must be sent.
    """
    def __init__(self, origin=None, data=None):
        Packet.__init__(self, origin)
        self.__data = data

    def getData(self):
        return self.__data

    data = property(getData, None, None, "The data associated with this specific control packet type.")

class Start(ControlPacket):
    """Start some operation"""
    pass

class Stop(ControlPacket):
    """Stop doing some operation"""
    pass

class Pause(ControlPacket):
    """Pause something that can be continued later"""
    pass

class Next(ControlPacket):
    """Skip the current operation"""
    pass

class Prev(ControlPacket):
    """Go back to the previous operation"""
    pass

class Enqueue(ControlPacket):
    """Passes along a source to enqueue"""
    pass

class Load(ControlPacket):
    """Uses the 'uri' data element to indicate loading of data"""
    pass

class Seek(ControlPacket):
    """Uses the 'location' data element"""
    pass

class Exit(ControlPacket):
    """Indicates a plugin upstream has exited and is no longer part of the graph"""
    pass

class PacketDelay(Plugin):
    """PacketDelays are used to wait until a packet of some type has been recieved"""
    def __init__(self, packetType):
        Plugin.__init__(self)
        self.__type = packetType
        self.__lock = threading.Event()

    def handlePacket(self, pkt):
        super(PacketDelay, self).handlePacket(pkt)
        if (isinstance(pkt, self.__type)):
            self.__lock.set()

    def wait():
        self.__lock.wait()