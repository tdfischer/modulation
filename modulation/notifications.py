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

from modulation import Packet

class NotificationPacket(Packet):
    """Notifies downstream listeners that something happened"""
    pass

class PlaybackComplete(NotificationPacket):
    """Playback of the current media object has completed"""
    pass

class PlaybackStarted(NotificationPacket):
    """Playback of the current media object has started"""
    pass

class PlaybackStopped(NotificationPacket):
    """Playback was paused"""
    pass

class Buffering(NotificationPacket):
    """The buffer is low, and more data should be sent"""
    pass

class PlaylistEmpty(NotificationPacket):
    """The playlist is empty"""
    pass