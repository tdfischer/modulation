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
import threading
import SocketServer

PROTO_VERSION = 0

class BridgeConnectionHandler(SocketServer.BaseRequestHandler):
    def handle(self):
        self.request.write(PROTO_VERSION)
        self.request.close()

class ThreadedBridgeServer(SocketServer.ThreadingMixIn, SocketServer.TCPServer):
    pass

class Bridge(modulation.Plugin):
    def __init__(self, port=0):
        super(Bridge, self).__init__()
        self.__thread = threading.Thread(target=self.__bridgeLoop)
        self.__port = port
        self.__sock = socket.socket()
        self.__server = ThreadedBridgeServer(("0.0.0.0", 0), BridgeConnection)

    @modulation.input(modulation.KickstartPacket)
    def startup(self, pkt):
        self.__thread.start()
    
    def _kill(self):
        super(Bridge, self)._kill()
        
    def __bridgeLoop(self):
        self.__server.serve_forever()