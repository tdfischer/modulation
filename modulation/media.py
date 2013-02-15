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

from modulation import Plugin, Packet
from modulation.streaming import FileStream
import modulation.notifications
import tagpy
import modulation.controls
import threading

class MediaSource(Plugin):
    """A MediaSource is a source of media. It is expected to constantly generate new media packets

    MediaSources must generate at least one media packet when told to Start.
    """
    pass

class MediaSink(Plugin):
    """A MediaSink is where media data ends up. It is expected to generate status notifications and relay the raw media data to whatever external destination is needed.
    """
    def __init__(self):
        super(MediaSink, self).__init__()
        self.__size = 0
        self.__input = None
        self.__output = False
        self.__playing = True
        self.__unpaused = threading.Event()
        self.__unpaused.clear()
        self.__running = True
        self.__thread = threading.Thread(target=self.doStreaming)
        self._log.debug("Creating streaming thread %s", self.__thread)
        self.__thread.start()
        self.__lock = threading.Lock()
        self.__bufSize = 4096
        
    def _kill(self):
        super(MediaSink, self)._kill()
        self._log.debug("Killing streaming thread")
        self.stopStreaming()
        
    def setBufferSize(self, size):
        """Sets the number of bytes read from input and written to output at a time"""
        self.__bufSize = size

    @modulation.input(modulation.controls.Stop)
    def stop(self, pkt):
        """Stops the streaming thread"""
        self._log.debug("Killing streaming thread")
        self.stopStreaming()
        
    @modulation.input(modulation.controls.Pause)
    def pause(self, pkt):
        """Pauses the streaming thread"""
        self._log.debug("Pausing streaming")
        self.pauseStreaming()

    def setOutputStream(self, out):
        """Sets the output stream"""
        self.__output = out
        if (self.__output.closed):
            self.__output.open()

    def getOutputStream(self):
        """Returns the output stream"""
        return self.__output

    def sendData(self):
        """Reads one chunk from the input and writes it to the output"""
        with self.__lock:
            buf = self.getInputStream().read(self.__bufSize)
            self.getOutputStream().write(buf)
            return len(buf)

    def isRunning(self):
        """Returns true if streaming, false otherwise."""
        return self.__running

    def setInputStream(self, strm):
        """Sets the input stream to read from"""
        with self.__lock:
            if (not (self.__input is None)):
                self.__input.close()
            self.__input = strm
            if (not (self.__input is None)):
                if (self.__input.closed):
                    self.__input.open()
                if (self.__playing):
                    self.__unpaused.set()
            else:
                self.__unpaused.clear()

    def getInputStream(self):
        """Returns the input stream"""
        return self.__input

    def setSize(self, size):
        """Set the apparent size of the input"""
        self.__size = size

    def getSize(self):
        """Return the input size"""
        return self.__size

    def startStreaming(self):
        """Starts streaming"""
        self.__playing = True
        self.__unpaused.set()

    def stopStreaming(self):
        """Stops streaming. Input/output is closed."""
        self.__playing = False
        self.__running = False
        self.__unpaused.set()

    def pauseStreaming(self):
        """Pauses streaming, leaving input/output open as long as possible."""
        self.__unpaused.clear()

    def waitForMedia(self):
        """Waits until an input stream is assigned"""
        self.__unpaused.wait()

    def doStreaming(self):
        """The streaming thread"""
        count = 0
        while self.isRunning():
            self.waitForMedia()
            if (self.getInputStream() is None):
                self._log.warn("No media! Pausing.")
                self.__unpaused.clear()
            else:
                sent=self.sendData()
                count+=sent
                self.send(modulation.streaming.StreamProgressPacket(self, count, self.getSize()))
                if (sent == 0):
                    self.setInputStream(None)
                    self.send(modulation.notifications.PlaybackComplete(self))
                    count = 0

class MediaObject(object):
    """A MediaObject represents the a single unit of media.
    It contains two essential atoms of information: the metadata, and the actual data itself.
    """
    def getMetadata(self):
        """Returns the metadata"""
        raise NotImplementedError

    def getStream(self):
        """Returns the stream"""
        raise NotImplementedError

    metadata = property(getMetadata, None, None, "The media's associated metadata")
    stream = property(getStream, None, None, "The media's associated data stream")

class Metadata(dict):
    """Metadata is a dictionary of string pairs"""
    pass

class EmptyMetadata(Metadata):
    """Metadata with no contents"""
    pass

class MediaList(Packet):
    """Passes along a list of MediaObjects"""
    def __init__(self, origin, list):
        super(MediaList, self).__init__(origin)
        self.__list = list

    @property
    def media(self):
        """Returns the list of MediaObjects"""
        return self.__list

class MediaPacket(Packet):
    """A MediaPacket tells a child plugin that the media output graph has changed somehow upstream.
    This could mean a new file started playing, the media's metadata changed, or anything else media related
    """
    def __init__(self, origin, media):
        Packet.__init__(self, origin)
        self.__media = media

    def getMedia(self):
        return self.__media

    media = property(getMedia, None, None, "The MediaObject related to this packet.")

class URLObject(MediaObject):
    """A MediaObject for remote URLs"""
    def __init__(self, url):
        super(URLObject, self).__init__(self)
        self.__url = url

    def getStream(self):
        return URLStream(self.__url)

    def getMetadata(self):
        return EmptyMetadata()

class FileObject(MediaObject):
    """A MediaObject for a file on a local filesystem"""
    def __init__(self, file):
        MediaObject.__init__(self)
        self.__file = file

    def getStream(self):
        return FileStream(self.__file)

    def getMetadata(self):
        m = Metadata()
        try:
            ref = tagpy.FileRef(self.__file)
            tags = ref.tag()
            m["artist"] = tags.artist
            m["album"] = tags.album
            m["title"] = tags.title
            m["year"] = tags.year
            return m
        except ValueError:
            return EmptyMetadata()

class FileSource(MediaSource):
    """A MediaSource that originates from a file on the local filesystem"""
    def __init__(self, file):
        MediaSource.__init__(self)
        self.__file = file
        
    @modulation.input(modulation.controls.Start)
    def play(self, pkt):
        """Sends out a MediaPacket containing the underlying FileObject then exits"""
        self.send(MediaPacket(self, FileObject(self.__file)))
        self.kill()