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

from __future__ import with_statement
import modulation.media
import modulation.util
import modulation.query
import os
import logging
import time
import sqlite3
import threading
import hashlib

class CollectionObject(object):
    """Some abstract organizational structure in a collection tree"""
    def __init__(self, name, parent=None):
        super(CollectionObject, self).__init__()
        self.__parent = parent
        self.__name = name
        self._log = logging.getLogger("modulation.collection.%s"%(self.__class__.__name__))

    def path(self):
        """Returns the absolute path, in terms of a modulation collection path."""
        if (self.__parent is None):
            return '/'
        if (self.__parent.path() is "/"):
            return '/'+self.name()
        else:
            return self.__parent.path()+"/"+self.__name

    def name(self):
        """Returns the name of this object in the path"""
        return self.__name

    def parent(self):
        """Returns the parent this object belongs to"""
        return self.__parent

    def __str__(self):
        return self.path()+"/"+self.__name

    def __repr__(self):
        return '%s(%s, %s)'%(self.__class__.__name__, str(self.__name), repr(self.__parent))

class Node(CollectionObject):
    """Represents an object in the collection tree that has children"""
    def __init__(self, path, parent=None):
        super(Node, self).__init__(path, parent)
        self.__cache = {}
        self.__stamp = 0

    def __getitem__(self, key):
        if (isinstance(key, str)):
            if (key in self.__cache):
                return self.__cache[key]
            else:
                raise KeyError, key
        else:
            raise TypeError, repr(key)

    @property
    def contents(self):
        """Returns the children of this node"""
        return self.__cache.values()

    def __contains__(self, key):
        return key in self.__cache

    def __len__(self):
        return len(self.__cache)

    def addChild(self, child):
        """Adds a CollectionObject to this node"""
        self.__cache[child.name()] = child

    def setLastUpdateTime(self, time):
        """Sets when this node was last updated"""
        if (time is None):
            time = 0
        self.__stamp = float(time)

    def refresh(self):
        """Updates the collection if neccessary"""
        if (time.time() - self.__stamp > 3600):
            self.update()
            self.__stamp = time.time()

    def findMedia(self, constraint, limit):
        ret = ()
        for entry in self.contents:
            if (isinstance(entry, Node)):
                ret += entry.findMedia(constraint, limit-len(ret))
            else:
                if (constraint.matches(entry.media())):
                    ret += (entry.media(), )
                    if (len(ret) == limit):
                        return ret
        return ret
        
    def update(self):
        """This function is called from within refresh() if an update is deemed neccessary"""
        pass

class Leaf(CollectionObject):
    """Represents a specific piece of media within a collection hiearchy"""
    def __init__(self, name, parent=None):
        super(Leaf, self).__init__(name, parent)
    def media(self):
        """Returns the MediaObject for this object"""
        raise NotImplementedError

class File(Leaf):
    """A on-disk file with a real path"""
    def media(self):
        return modulation.media.FileObject(self.realPath())
        
    def realPath(self):
        return '/'.join((self.parent().realPath(), self.name()))

class DBCache(Node):
    """A node that sits on top of some other, slower node
    
    A DBCache stores a backend object's hiearchy on disk in a sqlite database.
    This greatly speeds up operations, since searching a filesystem or remote URL
    for a specific piece of metadata can be dreadful and sometimes unrealistic.
    """
    def __init__(self, path, backend):
        super(DBCache, self).__init__('', None)
        self.__db = modulation.util.ThreadingSqliteDB(path)
        with self.__db as db:
            db.create_function('regexp', 2, self.__regexp)
            #db.create_function('glob', 2, self.__glob)
        self.__backend = backend
        self.__initdb()
        self.__updateThread = None
        
    def __regexp(self, pattern, string):
        return re.match(pattern, string)

    def __initdb(self):
        with self.__db as db:
            try:
                version = self.getMeta('_version')
            except sqlite3.OperationalError:
                c = db.cursor()
                c.execute("CREATE TABLE _meta (key TEXT UNIQUE, value TEXT)")
                db.commit()
                c.close()
                version = None
            newver = str(self.upgradeDB(version))
            if (not newver is None):
                self.setMeta('_version', newver)
            self.setLastUpdateTime(self.getMeta('last_update'))

    def getMeta(self, key):
        """Returns a piece of metadata about the database"""
        with self.__db as db:
            c = db.cursor()
            c.execute("SELECT value FROM _meta WHERE key = ?", (key,))
            row = c.fetchone()
            c.close()
            if (row is None):
                return None
            return row['value']

    def setMeta(self, key, value):
        """Saves some metadata with this database"""
        with self.__db as db:
            c = db.cursor()
            c.execute("INSERT OR REPLACE INTO _meta (key, value) VALUES (?, ?)", (key, value))
            db.commit()
            c.close()

    def upgradeDB(self, currentVersion):
        """Called when the database needs upgrading to the latest version"""
        if (currentVersion is None):
            with self.__db as db:
                c = db.cursor()
                #TODO: Store in a preorder tree format
                c.execute("CREATE TABLE paths (id INTEGER PRIMARY KEY, parent INTEGER KEY, name TEXT)")
                c.execute("CREATE UNIQUE INDEX parentname ON paths (parent, name)")
                c.execute("CREATE TABLE entries (id INTEGER PRIMARY KEY, pathid INTEGER KEY, name TEXT, path_sha1 TEXT)")
                c.execute("CREATE TABLE metadata (entryid INTEGER KEY, name TEXT, value BLOB)")
                c.execute("CREATE UNIQUE INDEX idname ON metadata (entryid, name)")
                db.commit()
                c.close()
                return 1

    def findMedia(self, constraint, limit=0):
        """Accepts a mediaman.query.Query object and returns a list of MediaObjects"""
        (wherecond, binds) = self._buildQueryConditions(constraint)
        self._log.debug("Querying for %s with %s", wherecond, binds)
        ret = ()
        with self.__db as db:
            c = db.cursor()
            if (limit > 0):
                c.execute("SELECT entries.name, entries.pathid FROM entries LEFT JOIN metadata ON metadata.entryid = entries.id WHERE %s ORDER BY RANDOM() LIMIT ?"%(wherecond,), binds+(limit,))
            else:
                c.execute("SELECT entries.name, entries.pathid FROM entries LEFT JOIN metadata ON metadata.entryid = entries.id WHERE %s ORDER BY RANDOM()"%(wherecond,), binds)
            rows = c.fetchall()
            for row in rows:
                backendPath = self._getFullPath(row['pathid'])
                backendPath = '/'.join(backendPath.split('/')[1:])
                ret += (self._getMedia('/'.join((backendPath, row['name'])), self.__backend),)
            c.close()
        return ret

    def _buildGroupConditions(self, filter):
        if (isinstance(filter, modulation.query.Limit)):
            return "LIMIT %i"%filter.size()

    def _getMedia(self, path, child=None):
        component = path.split('/')[0]
        for file in child.contents:
            if (component == file.name()):
                if (component == path):
                    return file.media()
                return self._getMedia('/'.join(path.split('/')[1:]), file)
        return None

    def _getFullPath(self, pathid):
        with self.__db as db:
            c = db.cursor()
            c.execute("SELECT parent, name FROM paths WHERE id = ?", (pathid,))
            path = c.fetchone()
            c.close()
            if (path == None):
                return ''
            if (path['name'] == ''):
                return ''
            parent = self._getFullPath(path['parent'])
            ret = '/'.join((parent, path['name']))
            return ret

    def _buildQueryConditions(self, constraint):
        if (isinstance(constraint, modulation.query.Any)):
            return ("1==1",())
        if (isinstance(constraint, modulation.query.Nothing)):
            return ("1==0",())
        if (isinstance(constraint, modulation.query.Not)):
            ret = self._buildQueryConditions(constraint.constraint())
            return ("NOT (%s)"%ret[0], ret[1])
        if (isinstance(constraint, modulation.query.MetadataQuery)):
            return self._buildMetadataQueryConditions(constraint)
        if (isinstance(constraint, modulation.query.Or)):
            query = ()
            binds = ()
            for subquery in constraint.constraints:
                subq = self._buildQueryConditions(subquery)
                query += (subq[0],)
                binds += subq[1]
            return (' OR '.join(query), binds)
        if (isinstance(constraint, modulation.query.And)):
            query = ()
            binds = ()
            for subquery in constraint.constraints:
                subq = self._buildQueryConditions(subquery)
                query += (subq[0],)
                binds += subq[1]
            return (' AND '.join(query), binds)
        if (isinstance(constraint, modulation.query.RandomMatch)):
            if (constraint.getBool()):
                return ('1=1', ())
            return ('1=0', ())

    def _buildMetadataQueryConditions(self, constraint):
        if (isinstance(constraint, modulation.query.EqualsMetadata)):
            return ("(metadata.name == ? AND ? == metadata.value)",(constraint.key(), constraint.value()))
        if (isinstance(constraint, modulation.query.HasMetadata)):
            return ("(metadata.name == ?)", (constraint.key(),))
        if (isinstance(constraint, modulation.query.GreaterThanMetadata)):
            return ("(metadata.name == ? AND ? > metadata.value)", (constraint.key(), constraint.value()))
        if (isinstance(constraint, modulation.query.LessThanMetadata)):
            return ("(metadata.name == ? AND ? < metadata.value)", (constraint.key(), constraint.value()))
        if (isinstance(constraint, modulation.query.ContainsMetadata)):
            return ("metadata.value == ?", (constraint.key()))
        if (isinstance(constraint, modulation.query.MetadataRegex)):
            return ("(metadata.name == ? AND metadata.value  REGEX ?)", (constraint.key(), constraint.value()))
        if (isinstance(constraint, modulation.query.MetadataGlob)):
            return ("(metadata.name == ? AND metadata.value GLOB ?)", (constraint.key(), constraint.value()))

    def update(self):
        """Updates the backend in the background"""
        if (self.__updateThread is None):
            self.__updateThread = threading.Thread(target=self._updateBackend)
            self.__updateThread.start()
        else:
            self.__updateThread.join()
            self.__updateThread = None
    
    def _updateBackend(self):
        self.__backend.update()
        self._updateNode(self.__backend)
        self.setMeta('last_update', time.time())

    def _findLeafByPathHash(self, hash):
        with self.__db as db:
            c = db.cursor()
            c.execute("SELECT id, pathid, name FROM entries WHERE path_sha1 = ?", (hash,))
            ret = c.fetchone()
            c.close()
            return ret

    def _updateNode(self, node):
        for child in node.contents:
            if (isinstance(child, Leaf)):
                self._updateLeaf(child)
            else:
                self._updateNode(child)

    def _updateLeaf(self, leaf):
        media = leaf.media()
        obj = self._findLeafByPathHash(hashlib.sha1(leaf.path()).hexdigest())
        if (obj is None):
            obj = self._addLeaf(leaf)
        with self.__db as db:
            c = db.cursor()
            for key, value in media.getMetadata().iteritems():
                c.execute("INSERT OR REPLACE INTO metadata (entryid, name, value) VALUES (?,?,?)", (obj['id'], key, value))
            db.commit()
            c.close()

    def _addLeaf(self, leaf):
        with self.__db as db:
            c = db.cursor()
            hash = hashlib.sha1(leaf.path()).hexdigest()
            path = self._getPathId('/'.join(leaf.path().split('/')[:-1]))
            c.execute("INSERT INTO entries (pathid, name, path_sha1) VALUES (?,?,?)", (path, leaf.name(), hash))
            db.commit()
            c.close()
            return self._findLeafByPathHash(hash)

    def _getPathId(self, path, parent = 0):
        component = path.split('/')[0]
        with self.__db as db:
            c = db.cursor()
            c.execute("SELECT id, parent, name FROM paths WHERE parent=? AND name=?", (parent, component))
            node = c.fetchone()
            c.close()
            if (node is None):
                node = self._addNode(component, parent)
            if (component == path):
                return node['id']
            return self._getPathId('/'.join(path.split('/')[1:]), node['id'])

    def _getPathById(self, id):
        with self.__db as db:
            c = db.cursor()
            c.execute("SELECT id, parent, name FROM paths WHERE id=?", (id,))
            ret = c.fetchone()
            c.close()
            return ret

    def _addNode(self, name, parent = None):
        with self.__db as db:
            c = db.cursor()
            c.execute("INSERT INTO paths (parent, name) VALUES (?,?)", (parent, name))
            db.commit()
            c.close()
            return self._getPathById(c.lastrowid)

class Directory(Node):
    """A directory within a DirectoryRoot collection."""
    def update(self):
        try:
            for file in os.listdir(self.realPath()):
                if (os.path.isfile(self.realPath()+"/"+file)):
                    if (file not in self):
                        self.addChild(File(file, self))
                if (os.path.isdir(self.realPath()+"/"+file)):
                    if (file not in self):
                        subdir = Directory(file, self)
                        subdir.refresh()
                        if (len(subdir) > 0):
                            self.addChild(subdir)
                    else:
                        self[file].refresh()
        except OSError, e:
            pass

    def realPath(self):
        return '/'.join((self.parent().realPath(), self.name()))

class DirectoryRoot(Directory):
    """The root directory of a filesystem collection"""
    def __init__(self, path, parent = None):
        super(DirectoryRoot, self).__init__('', None)
        self.__path = path
        self.update()

    def realPath(self):
        return self.__path

class CollectionManager(modulation.media.MediaSource):
    """A collection manager responds to queries and returns lists of media from the underlying collections"""
    def __init__(self):
        super(CollectionManager, self).__init__()
        self.__collections = []
    def addCollection(self, collection):
        self.__collections.append(collection)
    def findMedia(self, constraint, limit):
        ret = ()
        for c in self.__collections:
            self._log.debug("Updating %s", c)
            try:
                c.refresh()
                ret+=c.findMedia(constraint, limit)
            except Exception, e:
                self._log.error("Exception caught from collection backend %s: %s", c, e)
                self.send(modulation.ExceptionPacket(self, e))
            if (len(ret) == limit):
                return ret
        return ret

    @modulation.input(modulation.query.QueryPacket)
    def query(self, pkt):
        """Replies with a QueryResultPacket"""
        self.send(modulation.query.QueryResultPacket(self, self.findMedia(pkt.constraint, pkt.resultlimit)))
