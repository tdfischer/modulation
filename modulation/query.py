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

import modulation.media
import re
import glob
import random

class QueryConstraint(object):
    """Base class for query constraints."""
    pass

class QueryMatchConstraint(QueryConstraint):
    """Base class for constraints that perform some kind of matching against MediaObjects"""
    def matches(self, media):
        if (not isinstance(media, modulation.media.MediaObject)):
            raise TypeError

class RandomMatch(QueryMatchConstraint):
    """Given a probability from 0 to 100, randomly match media"""
    def __init__(self, chance):
        super(RandomMatch, self).__init__()
        self.__chance = chance

    def chance(self):
        return self.__chance

    def getBool(self):
        return random.randint(0, 100) < self.__chance

    def matches(self, media):
        super(RandomMatch, self).matches(media)
        return self.getBool()

    def __repr__(self):
        return "RandomMatch(%i)"%self.__chance

class QueryListFilter(QueryConstraint):
    """Filters the result list"""
    def filter(self, list):
        pass

class Limit(QueryListFilter):
    """Limits the number of results"""
    def __init__(self, size):
        self.__size = size
    def size(self):
        return self.__size
    def filter(self, list):
        if (len(list) > self.__size):
            return list[0:self.__size]

class Any(QueryMatchConstraint):
    """Matches any and everything"""
    def matches(self, media):
        super(Any, self).matches(media)
        return True
    def __repr__(self):
        return "Any()"

class Nothing(QueryMatchConstraint):
    """Doesn't match anything"""
    def matches(self, media):
        super(Nothing, self).matches(media)
        return False
    def __repr__(self):
        return "Nothing()"

class Not(QueryMatchConstraint):
    """Inverts the constraint"""
    def __init__(self, constraint):
        super(Not, self).__init__()
        self.__constraint = constraint

    def matches(self, media):
        super(Not, self).matches(media)
        if (self.__constraint.matches(media)):
            return False
        return True

    def constraint(self):
        return self.__constraint

    def __repr__(self):
        return "Not(%r)"%repr(self.__constraint)

class MetadataQuery(QueryMatchConstraint):
    """Base class for matching against some aspect of metadata"""
    def __init__(self, key):
        super(MetadataQuery, self).__init__()
        self.__key = key

    def key(self):
        return self.__key

class MetadataMatch(MetadataQuery):
    """Base class for matching against a value of metadata"""
    def __init__(self, key, value):
        super(MetadataMatch, self).__init__(key)
        self.__value = value

    def value(self):
        return self.__value

class HasMetadata(MetadataQuery):
    """Matches if metadata with the key exists"""
    def matches(self, media):
        super(HasMetadata, self).matches(media)
        return self.key() in media.getMetadata()

    def __repr__(self):
        return "HasMetadata(%r)"%(self.key())

class EqualsMetadata(MetadataMatch):
    """Matches if the metadata exactly equals the value"""
    def matches(self, media):
        super(EqualsMetadata, self).matches(media)
        if (self.key() in media.getMetadata()):
            return media.getMetadata()[self.key()] == self.value()
        return False

    def __repr__(self):
        return "EqualsMetadata(%r, %r)"%(self.key(), self.value())

class GreaterThanMetadata(MetadataMatch):
    """Matches if the value is greater than the metadata"""
    def matches(self, media):
        super(GreaterThanMetadata, self).matches(media)
        if (self.key() in media.getMetadata()):
            return self.value() > media.getMetadata()[self.key()]

    def __repr__(self):
        return "GreaterThanMetadata(%r, %r)"%(self.key(), self.value())

class MetadataRegex(MetadataMatch):
    """Matches if the regex value matches the metadata"""
    def __init__(self, key, value):
        if (isinstance(value, str)):
            value = re.compile(value)
        super(MetadataRegex, self).__init__(key, value)

    def matches(self, media):
        super(MetadataRegex, self).matches(media)
        if (self.key() in media.getMetadata()):
            return self.value().matches(media.getMetadata()[self.key()])
        return False

class MetadataGlob(MetadataMatch):
    """Matches if the glob value matches the metadata"""
    def matches(self, media):
        super(MetadataGlob, self).matches(media)
        if (self.key() in media.getMetadata()):
            return fnmatch.fnmatch(media.getMetadata()[self.key()], self.value())
        return False

class LessThanMetadata(MetadataMatch):
    """Matches if the value is less than the metadata"""
    def matches(self, media):
        super(LessThanMetadata, self).matches(media)
        if (self.key() in media.getMetadata())):
            return self.value() < media.getMetadata()[self.key()]

    def __repr__(self):
        return "LessThanMetadata(%r, %r)"%(self.key(), self.value())

class ContainsMetadata(MetadataQuery):
    """Matches if the value is equal to any piece of the metadata"""
    def matches(self, media):
        super(ContainsMetadata, self).matches(media)
        for data in media.getMetadata():
            return data == self.key()

    def __repr__(self):
        return "ContainsMetadata(%r)"%(self.key())

class QuerySet(QueryMatchConstraint):
    """Base class for compound constraints"""
    def __init__(self, constraints):
        super(QuerySet, self).__init__()
        self.__constraints = constraints

    @property
    def constraints(self):
        return self.__constraints

class Or(QuerySet):
    """Matches if any one of the sub-constraints matches"""
    def matches(self, media):
        super(Or, self).matches(media)
        for constraint in self.constraints:
            if (constraint.matches(media)):
                return True

    def __repr__(self):
        return "Or(%r)"%(self.constraints,)

class And(QuerySet):
    """Matches only if all of the sub-constraints match"""
    def matches(self, media):
        super(And, self).matches( media)
        for constraint in self.constraints:
            if (not constraint.matches(media)):
                return False
        return True

    def __repr__(self):
        return "And(%r)"%(self.constraints,)

class QueryResultPacket(modulation.media.MediaList):
    """A packet sent in reply to a query. Contains the result list."""
    pass

class QueryPacket(modulation.Packet):
    """Encaspulates a complete query"""
    def __init__(self, origin, constraint, resultLimit = 0):
        super(QueryPacket, self).__init__(origin)
        if (not isinstance(constraint, QueryConstraint)):
            raise TypeError, repr(constraint)
        self.__limit = resultLimit
        self.__constraint = constraint

    @property
    def resultlimit(self):
        return self.__limit

    @property
    def constraint(self):
        return self.__constraint