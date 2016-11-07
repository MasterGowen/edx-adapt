import os

from edx_adapt.api import adapt_api
import course_setup_test

import unittest
import tempfile
import json

import re

import string
import random

COURSE_ID = 'CMUSTAT'

base = '/api/v1/course'


def id_generator(size=6, chars=string.ascii_uppercase + string.digits):
    return ''.join(random.choice(chars) for _ in range(size))


class EdxAdaptTestCase(unittest.TestCase):
    def setUp(self):
        self.course_id = COURSE_ID + id_generator(3)
        course_setup_test.prepare_course(self.course_id)

        self.headers = {'Content-type': 'application/json'}
        self.app = adapt_api.app.test_client()

    def tearDown(self):
        # FIXME(idegtiarov) TearDown method is now implemented only for MongoDB, SQLite should be added
        import pymongo
        mclient = pymongo.MongoClient()['edx-adapt']
        mclient.drop_collection(self.course_id)
        regex = re.compile('_student_')
        mclient.Generic.remove({'key': {'$regex': regex}})

    def test_course_created(self):
        res = json.loads(self.app.get(base).data)
        self.assertEqual(self.course_id, res['course_ids'][0])

    def test_course_has_skills(self):
        skills = json.loads(self.app.get(base + '/{}/skill'.format(self.course_id)).data)
        expected_skills = [u'x axis', u'histogram', u'h to d', u'shape', u'spread', u'y axis', u'd to h', u'center',
                           u'None']
        self.assertEqual(expected_skills, skills['skills'])

    def test_course_problem_fulfilled(self):
        problems = json.loads(self.app.get(base + '/{}'.format(self.course_id)).data)
        self.assertTrue(problems, msg='Not any problem is found in course')
        # NOTE(idegtiarov) We do not controll correct value in the test problem amount depends on problist.tsv file
        self.assertEqual(84, len(problems['problems']))

    def test_course_experiment_fulfilled(self):
        experiments = json.loads(self.app.get(base + '/{}/experiment'.format(self.course_id)).data)
        self.assertTrue(experiments, msg="Experiments are excluded in course's database")
        # NOTE(idegtiarov) further check depends on prepared course's data and could be validate in course_setup_test.py
        expected = [{u'experiment_name': u'test_experiment2', u'start_time': 1462736963, u'end_time': 1999999999}]
        self.assertEqual(expected, experiments['experiments'])


class AllCorrectPreAssessmentTestCase(EdxAdaptTestCase):
    def setUp(self):
        super(AllCorrectPreAssessmentTestCase, self).setUp()
        # set up new student
        self.student_name = 'test_student_' + id_generator()

        self.app.post('/api/v1/course/{}/user'.format(self.course_id),
                      data=json.dumps({'user_id': self.student_name}), headers=self.headers)
        # Default student params
        self.probabilities = {'pg': 0.25, 'ps': 0.25, 'pi': 0.1, 'pt': 0.5, 'threshold': 0.99}
        skills = ['center', 'shape', 'spread', 'x axis', 'y axis', 'h to d', 'd to h', 'histogram', 'None']

        for skill in skills:
            payload = json.dumps({'course_id': COURSE_ID, 'params': self.probabilities, 'user_id': self.student_name,
                                  'skill_name': skill})
            self.app.post('/api/v1/parameters', data=payload, headers=self.headers)

    def test_user_enrolled(self):
        user = json.loads(self.app.get(base + '/{}/user'.format(self.course_id)).data)['users']['in_progress']
        self.assertTrue(user, msg="There is no any user enrolled on the course")
        self.assertEqual(1, len(user))
        self.assertEqual(self.student_name, user[0])

    def test_student_cut_off_after_all_correct_answers(self):
        pre_assessments = ['Pre_assessment_{}'.format(i) for i in range(0, 13)]
        for problem in pre_assessments:
            data = {'problem': problem, 'correct': True, 'attempt': 1}
            self.app.post(
                base + '/{}/user/{}/interaction'.format(self.course_id, self.student_name),
                data=json.dumps(data), headers=self.headers
            )

        status = json.loads(self.app.get('/api/v1/course/{}/user/{}'.format(self.course_id, self.student_name)).data)
        self.assertEqual(True, status['done_with_course'])


if __name__ == '__main__':
    unittest.main()
