import json
import random
import re
import string
import unittest

import pymongo

import course_setup_test
from edx_adapt.api import adapt_api

COURSE_ID = 'CMUSTAT'

base = '/api/v1/course'


def id_generator(size=6, chars=string.ascii_uppercase + string.digits):
    return ''.join(random.choice(chars) for _ in range(size))


class BaseTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.skills = ['center', 'shape', 'spread', 'x axis', 'y axis', 'h to d', 'd to h', 'histogram', 'None']
        cls.course_id = COURSE_ID + id_generator(3)
        course_setup_test.prepare_course(cls.course_id)

        cls.headers = {'Content-type': 'application/json'}
        cls.app = adapt_api.app.test_client()

    @classmethod
    def tearDownClass(cls):
        # NOTE(idegtiarov) sqlite is too slow for using on server we will support only MongoDB
        mclient = pymongo.MongoClient()['edx-adapt']
        mclient.drop_collection(cls.course_id)
        regex = re.compile('_student_')
        mclient.Generic.remove({'key': {'$regex': regex}})

    def _answer_pre_assessment_problems(self, correct=0, attention_question=True):
        """
        Automation fulfilling Pre-Assessment problems

        :param correct: int, Number of correct answers
        :param attention_question: bool, by default one of correct answers id assigned to AttentionQuestion
        """
        pre_assessments = ['Pre_assessment_{}'.format(i) for i in range(0, 14)]
        for i, problem in enumerate(pre_assessments):
            if correct:
                correct_value = True if i < correct - attention_question or (attention_question and i == 13) else False
            else:
                correct_value = False
            data = {'problem': problem, 'correct': correct_value, 'attempt': 1}
            self.app.post(
                base + '/{}/user/{}/interaction'.format(self.course_id, self.student_name),
                data=json.dumps(data), headers=self.headers
            )

    def _answer_problem(self, correct=True, attempt=1, repeat=1, next_problem=True):
        """
        Make an answer on Course's problem
        :param correct: bool, correct or not
        :param attempt: int, which attempt
        :param repeat: int, how many times student answer
        :param next_problem: boolean, answer on next problem True by default, if False student answer on current problem
        """
        for i in range(repeat):
            if next_problem:
                problem = adapt_api.database.get_next_problem(self.course_id, self.student_name)
            else:
                problem = adapt_api.database.get_current_problem(self.course_id, self.student_name)
            data = {'problem': problem['problem_name'], 'correct': correct, 'attempt': attempt}
            self.app.post(
                base + '/{}/user/{}/interaction'.format(self.course_id, self.student_name),
                data=json.dumps(data), headers=self.headers
            )
            attempt += 0 if next_problem else 1

    def _add_probabilities_to_user_kill(self, probabilities):
        for skill in self.skills:
            payload = json.dumps({'course_id': self.course_id, 'params': probabilities,
                                  'user_id': self.student_name, 'skill_name': skill})
            self.app.post('/api/v1/parameters', data=payload, headers=self.headers)


class CourseTestCase(BaseTestCase):
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


class PreAssessmentTestCase(BaseTestCase):
    def setUp(self):
        # super(PreAssessmentTestCase, self).setUp()
        # set up new student
        self.student_name = 'test_student_' + id_generator()

        self.app.post(base + '/{}/user'.format(self.course_id),
                      data=json.dumps({'user_id': self.student_name}), headers=self.headers)
        # Default student params
        probabilities = {'pg': 0.25, 'ps': 0.25, 'pi': 0.1, 'pt': 0.5, 'threshold': 0.99}

        self._add_probabilities_to_user_kill(probabilities)

    def test_student_enrolled(self):
        user = json.loads(self.app.get(base + '/{}/user'.format(self.course_id)).data)['users']['in_progress']
        self.assertTrue(user, msg="There is no any user enrolled on the course")
        self.assertGreaterEqual(len(user), 1)
        self.assertEqual(self.student_name, user[-1])

    def test_student_cut_off_after_all_correct_answers(self):

        self._answer_pre_assessment_problems(correct=7, attention_question=False)

        status = json.loads(self.app.get('/api/v1/course/{}/user/{}'.format(self.course_id, self.student_name)).data)
        self.assertEqual(True, status['done_with_course'])

    def test_student_cut_off_after_all_incorrect_answers(self):
        self._answer_pre_assessment_problems(correct=0)
        status = json.loads(self.app.get('/api/v1/course/{}/user/{}'.format(self.course_id, self.student_name)).data)
        self.assertEqual(True, status['done_with_course'])


class MainLogicTestCase(BaseTestCase):
    def setUp(self):
        self.student_name = 'test_student_' + id_generator()
        self.app.post(base + '/{}/user'.format(self.course_id),
                      data=json.dumps({'user_id': self.student_name}), headers=self.headers)

    def test_alternative_parameters_set_one(self):
        probabilities = {'pg': 0.01, 'ps': 0.01, 'pi': 0.99, 'pt': 0.99, 'threshold': 0.90}
        self._add_probabilities_to_user_kill(probabilities)
        self._answer_pre_assessment_problems(correct=5)
        self._answer_problem(repeat=3)
        next_problem = json.loads(
            self.app.get('/api/v1/course/{}/user/{}'.format(self.course_id, self.student_name)).data)['next']
        self.assertTrue(next_problem['posttest'])
        self.assertTrue(next_problem['problem_name'].startswith('Post_assessment'))

    def test_alternative_parameters_set_two(self):
        probabilities = {'pg': 0.5, 'ps': 0.5, 'pi': 0.01, 'pt': 0.01, 'threshold': 0.95}
        self._add_probabilities_to_user_kill(probabilities)
        self._answer_pre_assessment_problems(correct=5)
        # NOTE(idegtiarov) we should go through almost all skills problems and see that in next there is not posttest
        # one. We have 14 Pre tests and 14 Post test problems
        given_answer = (
            len(adapt_api.database.get_problems(self.course_id)) - 14 - 14 - 1)
        for _ in range(given_answer):
            self._answer_problem()
            next_problem = json.loads(
                self.app.get('/api/v1/course/{}/user/{}'.format(self.course_id, self.student_name)).data)['next']
            self.assertFalse(next_problem['posttest'])
            self.assertFalse(next_problem['problem_name'].startswith('Post_assessment'))

    def test_default_parameter_set(self):
        """
        Test default user parameter set

        Workflow could have different problems sequence that propose to student to solve, if almost all answers are
        correct student will have to answer not more than 28 problems with two answers from second attempt from 56
        before switching to post assessment part
        """
        probabilities = {'pg': 0.25, 'ps': 0.25, 'pi': 0.1, 'pt': 0.5, 'threshold': 0.99}
        self._add_probabilities_to_user_kill(probabilities)
        self._answer_pre_assessment_problems(correct=5)
        next_problem = json.loads(
            self.app.get('/api/v1/course/{}/user/{}'.format(self.course_id, self.student_name)).data)['next']
        self.assertEqual('b3', next_problem['problem_name'])

        self._answer_problem()
        next_problem = json.loads(
            self.app.get('/api/v1/course/{}/user/{}'.format(self.course_id, self.student_name)).data)['next']
        self.assertEqual('b4', next_problem['problem_name'])

        self._answer_problem()
        next_problem = json.loads(
            self.app.get('/api/v1/course/{}/user/{}'.format(self.course_id, self.student_name)).data)['next']
        self.assertEqual('b3_2_0', next_problem['problem_name'])

        self._answer_problem()
        next_problem = json.loads(
            self.app.get('/api/v1/course/{}/user/{}'.format(self.course_id, self.student_name)).data)['next']
        self.assertEqual('labels_we', next_problem['problem_name'])

        self._answer_problem()
        next_problem = json.loads(
            self.app.get('/api/v1/course/{}/user/{}'.format(self.course_id, self.student_name)).data)['next']
        self.assertEqual('skew_easy_0', next_problem['problem_name'])

        self._answer_problem()
        # next_problem = json.loads(
        #     self.app.get('/api/v1/course/{}/user/{}'.format(self.course_id, self.student_name)).data)['next']

        self._answer_problem(correct=False)
        status = json.loads(
            self.app.get('/api/v1/course/{}/user/{}'.format(self.course_id, self.student_name)).data)
        self.assertFalse(status['done_with_current'])
        self._answer_problem(attempt=2, next_problem=False)
        status = json.loads(
            self.app.get('/api/v1/course/{}/user/{}'.format(self.course_id, self.student_name)).data)
        self.assertTrue(status['done_with_current'])

        self._answer_problem(repeat=3)

        self._answer_problem(correct=False)
        status = json.loads(
            self.app.get('/api/v1/course/{}/user/{}'.format(self.course_id, self.student_name)).data)
        self.assertFalse(status['done_with_current'])
        self._answer_problem(attempt=2, next_problem=False)
        status = json.loads(
            self.app.get('/api/v1/course/{}/user/{}'.format(self.course_id, self.student_name)).data)
        self.assertTrue(status['done_with_current'])

        self._answer_problem(repeat=17)
        status = json.loads(
            self.app.get('/api/v1/course/{}/user/{}'.format(self.course_id, self.student_name)).data)
        self.assertTrue(status['next']['posttest'])
