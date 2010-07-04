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

import logging
class FileTagger:
    """Looks up a file with MusicBrainz and writes tags"""
    def __init__(self):
        self.log = logging.getLogger("FileTagger")

    def tagFile(self, file, match=0):
        """Tags a file object with the nth musicbrainz match given by match."""
        tags = file.tags
        matches = file.musicbrainz
        self.log.info("Found %i matches for %s (%s)", len(matches), file, file.puid)
        for result in matches:
            self.log.info("%s%% %s by %s on %s", result.score, result.track.title, result.track.artist.name, result.track.getReleases()[0].title)
        if len(matches) == 0:
            raise TagError, "MusicBrainz didn't return any search results."
        self.log.debug("Using first match to tag file.")
        track = matches[0].track
        tags.title = track.title
        tags.artist = track.artist.name
        tags.album = track.getReleases()[0].title
        file.writeTags()

class TagError(Exception):
    pass