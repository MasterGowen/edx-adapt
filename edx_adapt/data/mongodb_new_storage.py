from bson.json_util import dumps
from json import loads

import pymongo

from edx_adapt.data import interface
from edx_adapt import logger

DIRECTION_MAP = {'ascending': pymongo.ASCENDING, 'descending': pymongo.DESCENDING}


class MongoDbStorage(interface.StorageInterface):
    """
    Storage Interface implementation for MongoDB backend
    """

    def __init__(self, db_uri, db_name='edx-adapt'):
        super(MongoDbStorage, self).__init__()
        self.client = pymongo.MongoClient(db_uri)
        self.db_name = db_name
        self.db = self.client[db_name]

    def create_table(self, table_name, index_fields=None, index_unique=False):
        """
        Creates new MongoDb collection

        :param table_name: string Collection name
        :param index_fields: (optional) list of list [[index_field_name, <direction (ascending or descending)>], ...]
        :param index_unique: (optional) boolean make indexed fields be unique
        """
        try:
            self.db.create_collection(table_name)
        except pymongo.errors.CollectionInvalid:
            logger.info("Collection {0} already exists".format(table_name))
        if index_fields:
            index_fields = [(item[0], DIRECTION_MAP.get(item[1], pymongo.ASCENDING)) for item in index_fields]
            self.db[table_name].create_index(index_fields, unique=index_unique)

    def get_tables(self):
        """
        Returns all collections in the MongoDb
        """
        return [course.get('course_id') for course in self.db.Courses.find()]

    def get(self, coll_name, key):
        """
        Returns value for the required key from db[coll_name]

        :param coll_name: name of collection
        :param key: key which value is return
        """
        # FIXME(idegtiarov) Such structure is still been using in Generic coll_name, it would be great to refactor it
        collection = self.db[coll_name]
        if collection.count({'key': key}) < 1:
            raise interface.DataException("Key {} not found in collection".format(key))
        return collection.find_one({'key': key}).get('val')

    def get_one(self, collection, user_id, required_field):
        """
        Return value for required field from collections with complex structure

        :param collection: name of the collection
        :param user_id: user id to identifying document in collection
        :param required_field: required field
        """
        document = self.db[collection].find_one({'student_id': user_id}, {'_id': 0, required_field: 1})
        if document:
            return document[required_field]
        else:
            raise interface.DataException(
                "Key {} is not found in collection {} or collection is not exists".format(required_field, collection)
            )

    def course_get(self, course_id, field_name):
        """
        Get Course related data

        :param course_id: ID of the course
        :param field_name: string Field of required data
        :return: data from the field
        """
        return self.db.Courses.find_one({'course_id': course_id, field_name: {'$exists': True}})[field_name]

    def course_search(
        self, course_id, search_field, search_condition, projection_field=None, projection_condition=None
    ):
        """
        Make search in Course collection

        :param course_id: course id
        :param search_field: field key which is need to be found
        :param search_condition: dict with conditions which are used as value for $elemMatch operator
        :param projection_field: (optional) field name, if set returned doc contains only value for this field
        :param projection_condition: (optional) dict with conditions which are used as value for $elemMatch operator, if
            set only matched values from the field's list are returned.
        :return: dict with found document
        """
        if not projection_field:
            return self.db.Courses.find_one({'course_id': course_id, search_field: {'$elemMatch': search_condition}})
        elif not projection_condition:
            return self.db.Courses.find_one({'course_id': course_id, search_field: {'$elemMatch': search_condition}},
                                            {'_id': 0, projection_field: 1})
        else:
            return self.db.Courses.find_one({'course_id': course_id, search_field: {'$elemMatch': search_condition}},
                                            {'_id': 0, projection_field: {'$elemMatch': projection_condition}})

    def update_doc(self, collection, search_dict, update_dict):
        """
        Update document in collection

        :param collection: name of the collection
        :param search_dict: dict for match stage in update query
        :param update_dict: dict for update stage in update query
        :return: None
        """
        self.db[collection].update_one(search_dict, update_dict)

    def set(self, coll_name, key, val):
        """
        Update value for the required key from db[coll_name]

        :param coll_name: name of collection
        :param key: key which value is updated
        :param val: value set into database
        """
        self.db[coll_name].update_one(
            {'key': key},
            {'$set': {'val': val}}, upsert=True)

    def append(self, coll_name, list_key, val):
        """
        Append new value to the list

        :param coll_name: name of the collection
        :param list_key: key to the field with list value
        :param val: value which is added into list
        """
        collection = self.db[coll_name]
        if collection.count({'key': list_key}) < 1:
            raise interface.DataException("List: {0} not in collection: {1}".format(list_key, coll_name))
        field_list = collection.find_one({'key': list_key})['val']
        if val in field_list:
            raise interface.DataException("Value: {0} already exists in list: {1}".format(val, list_key))
        collection.update_one(
            {'key': list_key},
            {'$push': {'val': val}})

    def remove(self, table_name, list_key, val):
        # TODO: do
        raise NotImplementedError("Storage module must implement this")

    def export(self, tables=None):
        r = {}
        for table_name in self.db.collection_names():
            r[table_name] = list(self.db[table_name].find())
        return loads(dumps(r))  # To serialize Mongo's ObjectIds

    def record_data(self, table, data):
        """
        Record data into MongoDB

        :param table: name of collection to store data in
        :param data: dict with data which is stored
        """
        try:
            self.db[table].insert_one(data)
        except pymongo.errors.DuplicateKeyError:
            logger.info("Insert in collection {} failed".format(table))

    def course_append(self, course_id, field_key, value):
        """
        Append value in Course main document

        :param course_id: ID of the Course
        :param field_key: name of the list field that should be added with new item
        :param value: new item
        """
        update_res = self.db.Courses.update_one(
            {'course_id': course_id, field_key: {'$exists': True}}, {'$addToSet': {field_key: value}}
        )
        if not update_res.modified_count:
            logger.info("Key {0} is not exists in course {1} document fields".format(field_key, course_id))

    def course_user_done(self, course_id, user_id):
        """
        Move student to field from 'users_in_progress' to 'users_finished'
        """
        update_params = [{'course_id': course_id}, {'$pull': {'users_in_progress': user_id},
                                                    '$push': {'users_finished': user_id}}]
        self.db.Courses.update_one(*update_params)

    def get_statistic(self, collection, user_id, filter_condition, group_key, group_id=None, op='$sum', op_value=1):
        """
        Returns statistics from ..._log collection

        :param collection: name of collection
        :param user_id: student id
        :param filter_condition: dict uses in $match aggregating stage
        :param group_key: key for new document created in $group aggregation stage
        :param group_id: (optional) id for created document, default None
        :param op: operator for grouping of matched fields
        :param op_value: (optional) value which is operated by operator in $group aggregation stage
        """
        search = {'student_id': user_id}
        if filter_condition:
            search.update(filter_condition)
        return self.db[collection].aggregate([{'$match': search},
                                              {'$group': {'_id': group_id, group_key: {op: op_value}}}])

    def get_user_logs(self, collection, user_id, add_filter={}, project=None, get_from_doc=False, group_id=None,
                      group_field='logs'):
        """
        Returns logs from log collection

        :param collection: name of collection
        :param user_id: student id
        :param add_filter: dict added to default in $match aggregation stage
        :param project: dict with fields need be added in return doc {field1: 1, field2: 1}
        :param get_from_doc: (optional) document which is added in group_field's list, by default $$ROOT doc is added
        :param group_id: (optional) id for created document, default None
        :param group_field: (optional) key name for new docs entry
        """
        if not project:
            project = {'_id': 0, 'problem': 1, 'correct': 1, 'attempt': 1, 'unix_s': 1, 'type': 1, 'timestamp': 1}
        else:
            project.update({'_id': 0})
        search = {'student_id': user_id}
        if add_filter:
            search.update(add_filter)
        logs = self.db[collection].aggregate(
            [{'$match': search}, {'$project': project},
             {'$group': {'_id': group_id, group_field: {'$push': '${}'.format(
                 get_from_doc if get_from_doc else '$ROOT')}}}]
        )
        if not logs.alive:
            raise interface.DataException("Student {} logs are not found".format(user_id))
        return logs.next()[group_field]
