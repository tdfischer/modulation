# -*- coding: utf-8 -*-
import modulation.codecs as codecs
class Raw(codecs.FileEncoder, codecs.FileDecoder):
    types = ["audio/x-wav", "text/plain", "application/octet-stream"]
    def encode(self, input, metadata):
        return input

    def decode(self, input):
        return input

codecs.registerEncoder(Raw)
codecs.registerDecoder(Raw)
