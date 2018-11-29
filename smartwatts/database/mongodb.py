# Copyright (C) 2018  University of Lille
# Copyright (C) 2018  INRIA
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""
Module MongoDB
"""

import pymongo
from smartwatts.database.base_db import BaseDB
from smartwatts.report_model.report_model import KEYS_COMMON


class MongoBadDBError(Exception):
    """ MongDB error when hostname/port fail """
    pass


class MongoBadDBNameError(Exception):
    """ MongoDB error when database doesn't exist """
    pass


class MongoBadCollectionNameError(Exception):
    """ MongoDB error when collection doesn't exist """
    pass


class MongoDB(BaseDB):
    """
    MongoDB class
    """

    def __init__(self, report_model,
                 host_name, port, db_name, collection_name,
                 save_mode=False, erase=False):
        """
        Parameters:
            @report_model:    XXXModel object.
            @host_name:       hostname of the mongodb (ex: "localhost")
            @port:            port of the mongodb (ex: 27017)
            @db_name:         database name in the mongodb (ex: "smartwatts")
            @collection_name: collection name in the mongodb (ex: "sensor")
            @save_mode:       put save_mode to True if you want to use it
                              with a Pusher
            @erase:           If save_mode is False, erase too. It allow to
                              erase the collection on setup.
        """
        BaseDB.__init__(self, report_model)
        self.host_name = host_name
        self.port = port
        self.db_name = db_name
        self.collection_name = collection_name
        self.save_mode = save_mode

        if self.save_mode:
            self.erase = erase
        else:
            self.erase = False

        self.mongo_client = None
        self.collection = None
        self.cursor = None

        # Define if the mongodb is capped or not
        self.capped = False

    def load(self):
        """ Override """
        # close connec if reload
        if self.mongo_client is not None:
            self.mongo_client.close()

        self.mongo_client = pymongo.MongoClient(self.host_name, self.port,
                                                serverSelectionTimeoutMS=1)

        self.collection = self.mongo_client[self.db_name][
            self.collection_name]

        # Check if hostname:port work
        try:
            self.mongo_client.admin.command('ismaster')
        except pymongo.errors.ConnectionFailure:
            raise MongoBadDBError()

        if not self.save_mode:
            # Check if database exist
            if self.db_name not in self.mongo_client.list_database_names():
                raise MongoBadDBNameError()

            # Check if collection exist
            if self.collection_name not in self.mongo_client[
                    self.db_name].list_collection_names():
                raise MongoBadCollectionNameError()

            # Check if collection is capped or not
            options = self.collection.options()
            self.capped = True if ('capped' in options and
                                   options['capped']) else False

            # Depend if capped or not, create cursor
            if self.capped:
                self.cursor = self.collection.find(
                    cursor_type=pymongo.CursorType.TAILABLE_AWAIT)
            else:
                self.cursor = self.collection.find({})
        # Else if collection exist and erase is True
        elif (self.erase and
              self.db_name in self.mongo_client.list_database_names() and
              self.collection_name in self.mongo_client[
                  self.db_name].list_collection_names()):
            self.collection.drop()


    def get_next(self):
        """ Override """
        try:
            json = self.cursor.next()
        except StopIteration:
            return None

        # Re arrange the json before return it by removing '_id' field
        json.pop('_id', None)

        return self.report_model.from_mongodb(json)

    def save(self, json):
        """ Override """
        # TODO: Check if json is valid with the report_model
        self.collection.insert_one(json)
