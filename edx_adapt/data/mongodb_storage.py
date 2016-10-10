from json import loads
from bson.json_util import dumps
from pymongo import MongoClient
from flask import Response

import interface


class MongoDbStorage(interface.StorageInterface):

    def __init__(self, db_uri, db_name='edx-adapt'):
        super(MongoDbStorage, self).__init__()
        self.client = MongoClient(db_uri)
        self.db_name = db_name
        self.db = self.client[db_name]

    def create_table(self, table_name):
        """ Creates new MongoDb collection """
        self._assert_no_table(table_name)
        self.db.create_collection(table_name)

    def get_tables(self):
        """ Returns all collections in the MongoDb """
        #just return table names, not actual tables
        return self.db.collection_names()

    def get(self, table_name, key):
        self._assert_table(table_name)
        table = self.db[table_name]
        if table.count({'key': key}) < 1:
            raise interface.DataException("Key {} not found in table".format(key))
        return table.find_one({'key': key})['val']

    def set(self, table_name, key, val):
        self._assert_table(table_name)
        self.db[table_name].update_one(
            {'key': key},
            {'$set': {'val': val}}, upsert=True)

    def append(self, table_name, list_key, val):
        self._assert_table(table_name)
        table = self.db[table_name]
        if table.count({'key': list_key}) < 1:
            raise interface.DataException("List: {0} not in table: {1}".format(list_key, table_name))
        l = table.find_one({'key': list_key})['val']
        #TODO: check if l is a list maybe
        if val in l:
            raise interface.DataException("Value: {0} already exists in list: {1}".format(val, list_key))
        table.update_one(
            {'key': list_key},
            {'$push': {'val': val}})

    def remove(self, table_name, list_key, val):
        #TODO: do
        raise NotImplementedError("Storage module must implement this")

    def export(self, tables=None):
        r = {}
        for table_name in self.db.collection_names():
            r[table_name] = list(self.db[table_name].find())
        return loads(dumps(r))  # To serialize Mongo's ObjectIds

    def _assert_no_table(self, table_name):
        if table_name in self.get_tables():
            raise interface.DataException("Table already exists: {}".format(table_name))

    def _assert_table(self, table_name):
        if table_name not in self.get_tables():
            print self.get_tables()
            raise interface.DataException("Table does not exist: {}".format(table_name))
