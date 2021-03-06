import csv
import json
import os
import random
import string
import unittest

import pymongo

from edx_adapt.api import adapt_api

COURSE_ID = 'CMUSTAT'

base_api_path = '/api/v1/course'


def _setup_course_in_edxadapt(client, **kwargs):
    client.post(base_api_path, data=json.dumps({'course_id': kwargs['course_id']}), headers=kwargs['headers'])
    for skill in kwargs['skills']:
        payload = json.dumps({'skill_name': skill})
        client.post(base_api_path + '/{course_id}/skill'.format(**kwargs), data=payload, headers=kwargs['headers'])
    path_to_file = os.path.join(os.path.dirname(__file__), '../../data/BKT/problems.csv')
    with open(path_to_file) as file_csv:
        for row in csv.reader(file_csv):
            problem = row[0]
            skill = row[1]
            url = 'http://edx-lms.raccoongang.com/courses/{course_id}/{pname}'.format(pname=problem, **kwargs)
            pre = "Pre_a" in problem
            post = "Post_a" in problem
            payload = json.dumps({
                'problem_name': problem, 'tutor_url': url, 'skills': [skill], 'pretest': pre, 'posttest': post
            })
            client.post(
                base_api_path + '/{course_id}'.format(**kwargs), data=payload, headers=kwargs['headers']
            )
    payload = json.dumps({'experiment_name': 'test_experiment2', 'start_time': 1462736963, 'end_time': 1999999999})
    client.post(
        base_api_path + '/{course_id}/experiment'.format(**kwargs), data=payload, headers=kwargs['headers']
    )


def id_generator(size=6, chars=string.ascii_uppercase + string.digits):
    return ''.join(random.choice(chars) for _ in range(size))


class BaseTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.skills = ['center', 'shape', 'spread', 'x axis', 'y axis', 'h to d', 'd to h', 'histogram', 'None']
        cls.course_id = COURSE_ID + id_generator(3)
        cls.headers = {'Content-type': 'application/json'}
        cls.app = adapt_api.app.test_client()
        cls.params = {
            'headers': cls.headers,
            'skills': cls.skills,
            'course_id': cls.course_id,
        }
        _setup_course_in_edxadapt(cls.app, **cls.params)

    @classmethod
    def tearDownClass(cls):
        # NOTE(idegtiarov) sqlite is too slow for using on server we will support only MongoDB
        mclient = pymongo.MongoClient()
        # TODO(idegtiarov) improve application start-up to use another database name for tests
        mclient.drop_database('edx-adapt')

    def setUp(self):
        # set up new student
        self.student_name = 'test_student_' + id_generator()

        self.app.post(
            base_api_path + '/{}/user'.format(self.course_id),
            data=json.dumps({'user_id': self.student_name}),
            headers=self.headers
        )

    def _answer_pre_assessment_problems(self, correct_answers=0):
        """
        Automation fulfilling Pre-Assessment problems

        :param correct_answers: int, Number of correct answers
        """
        pre_assessments = ['Pre_assessment_{}'.format(i) for i in range(0, 14)]
        for answered_problem, problem in enumerate(pre_assessments):
            is_correct = answered_problem < correct_answers
            data = {'problem': problem, 'correct': is_correct, 'attempt': 1}
            self.app.post(
                base_api_path + '/{}/user/{}/interaction'.format(self.course_id, self.student_name),
                data=json.dumps(data),
                headers=self.headers
            )

    def _answer_problem(self, correct=True, attempt=1, repeat=1, next_problem=True):
        """
        Make an answer on Course's problem.

        :param correct: bool, correct or not
        :param attempt: int, attempt number
        :param repeat: int, how many times student answers
        :param next_problem: boolean, answer on next problem True by default, if False student answer on current problem
        """
        for i in range(repeat):
            if next_problem:
                problem = adapt_api.database.get_next_problem(self.course_id, self.student_name)
            else:
                problem = adapt_api.database.get_current_problem(self.course_id, self.student_name)
            data = {'problem': problem['problem_name'], 'correct': correct, 'attempt': attempt}
            self.app.post(
                base_api_path + '/{}/user/{}/interaction'.format(self.course_id, self.student_name),
                data=json.dumps(data),
                headers=self.headers
            )
            attempt += 0 if next_problem else 1

    def _add_probabilities_to_user_skill(self, probabilities):
        for skill in self.skills:
            payload = json.dumps({
                'course_id': self.course_id, 'params': probabilities, 'user_id': self.student_name, 'skill_name': skill
            })
            self.app.post('/api/v1/parameters', data=payload, headers=self.headers)

    def _get_problems_num(self, pretest=None, posttest=None):
        """Returns number of the problems registered in the course"""
        return len(adapt_api.database.get_problems(self.course_id, pretest=pretest, posttest=posttest))


class CourseTestCase(BaseTestCase):
    def test_course_created(self):
        res = json.loads(self.app.get(base_api_path).data)
        self.assertEqual(self.course_id, res['course_ids'][0])

    def test_course_has_skills(self):
        skills = json.loads(self.app.get(base_api_path + '/{}/skill'.format(self.course_id)).data)
        expected_skills = ['center', 'shape', 'spread', 'x axis', 'y axis', 'h to d', 'd to h', 'histogram', 'None']
        self.assertEqual(expected_skills, skills['skills'])

    def test_course_problem_fulfilled(self):
        problems = json.loads(self.app.get(base_api_path + '/{}'.format(self.course_id)).data)
        self.assertTrue(problems, msg='Not any problem is found in course')
        expecting_problems_number = self._get_problems_num()
        self.assertEqual(expecting_problems_number, len(problems['problems']))

    def test_course_experiment_fulfilled(self):
        experiments = json.loads(self.app.get(base_api_path + '/{}/experiment'.format(self.course_id)).data)
        self.assertTrue(experiments, msg="Experiments are excluded in course's database_api_path")
        # timestamp values are taken from course_setup_tests
        course_start_timestamp = 1462736963
        course_end_timestamp = 1999999999
        expected = [{
            u'experiment_name': u'test_experiment2',
            u'start_time': course_start_timestamp,
            u'end_time': course_end_timestamp
        }]
        self.assertEqual(expected, experiments['experiments'])


class PreAssessmentTestCase(BaseTestCase):
    def setUp(self):
        super(PreAssessmentTestCase, self).setUp()
        # Default student params
        probabilities = {'pg': 0.25, 'ps': 0.25, 'pi': 0.1, 'pt': 0.5, 'threshold': 0.99}

        self._add_probabilities_to_user_skill(probabilities)

    def test_student_enrolled(self):
        """
        Test checking student is enrolled on course in Edx-Adapt.
        """
        user = json.loads(self.app.get(base_api_path + '/{}/user'.format(self.course_id)).data)['users']['in_progress']
        self.assertTrue(user, msg="There is no any user enrolled on the course")
        self.assertGreaterEqual(len(user), 1)
        self.assertEqual(self.student_name, user[-1])

    def test_student_cut_off_after_all_correct_answers(self):
        """
        Test student got status "done_with_course" after answering correctly on more than half pre-assessment problems.
        """
        # Course is done if more than half
        correct_pretest_to_done_course = self._get_problems_num(pretest=True) // 2 + 1
        self._answer_pre_assessment_problems(correct_answers=correct_pretest_to_done_course)

        status = json.loads(self.app.get(base_api_path + '/{}/user/{}'.format(self.course_id, self.student_name)).data)
        self.assertEqual(True, status['done_with_course'])


class MainLogicTestCase(BaseTestCase):
    def test_alternative_parameters_set_one(self):
        """
        Test student with alternative parameter set one (no need to go through course if pre-assessment not fault).
        """
        probabilities = {'pg': 0.01, 'ps': 0.01, 'pi': 0.99, 'pt': 0.99, 'threshold': 0.90}
        self._add_probabilities_to_user_skill(probabilities)
        self._answer_pre_assessment_problems(correct_answers=5)
        self._answer_problem(repeat=3)
        next_problem = json.loads(
            self.app.get(base_api_path + '/{}/user/{}'.format(self.course_id, self.student_name)).data
        )['next']
        self.assertTrue(next_problem['posttest'])
        self.assertTrue(next_problem['problem_name'].startswith('Post_assessment'))

    def test_alternative_parameters_set_two(self):
        """
        Test student with alternative parameter set two (need do all course, even if all answers were correct).
        """
        probabilities = {'pg': 0.5, 'ps': 0.5, 'pi': 0.01, 'pt': 0.01, 'threshold': 0.95}
        self._add_probabilities_to_user_skill(probabilities)
        self._answer_pre_assessment_problems(correct_answers=5)

        given_answer = self._get_problems_num(pretest=False, posttest=False)
        # Checking there is no Post_assessment problem set to "next" before all generic problems are answered
        for _ in range(given_answer - 1):
            self._answer_problem()
            next_problem = json.loads(
                self.app.get(base_api_path + '/{}/user/{}'.format(self.course_id, self.student_name)).data
            )['next']
            self.assertFalse(next_problem['posttest'])
            self.assertFalse(next_problem['problem_name'].startswith('Post_assessment'))
        # Checking finally get Post assessment problem in "next" after all generic problems are answered
        self._answer_problem()
        next_problem = json.loads(
            self.app.get(base_api_path + '/{}/user/{}'.format(self.course_id, self.student_name)).data
        )['next']
        self.assertTrue(next_problem['posttest'])
        self.assertTrue(next_problem['problem_name'].startswith('Post_assessment'))

    def test_default_parameter_set(self):
        """
        Test default user parameter set.

        Workflow can have different problems sequence that propose to student to solve, if almost all answers are
        correct student will have to answer not more than 28 problems with two answers from second attempt from 56
        before switching to post assessment part
        """
        probabilities = {'pg': 0.25, 'ps': 0.25, 'pi': 0.1, 'pt': 0.5, 'threshold': 0.99}
        self._add_probabilities_to_user_skill(probabilities)
        self._answer_pre_assessment_problems(correct_answers=5)

        self._answer_problem(repeat=5)
        self._answer_problem(correct=False)
        status = json.loads(
            self.app.get(base_api_path + '/{}/user/{}'.format(self.course_id, self.student_name)).data
        )
        self.assertFalse(status['done_with_current'])
        self._answer_problem(attempt=2, next_problem=False)
        status = json.loads(
            self.app.get(base_api_path + '/{}/user/{}'.format(self.course_id, self.student_name)).data
        )
        self.assertTrue(status['done_with_current'])

        self._answer_problem(repeat=3)

        self._answer_problem(correct=False)
        status = json.loads(
            self.app.get(base_api_path + '/{}/user/{}'.format(self.course_id, self.student_name)).data
        )
        self.assertFalse(status['done_with_current'])
        self._answer_problem(attempt=2, next_problem=False)
        status = json.loads(
            self.app.get(base_api_path + '/{}/user/{}'.format(self.course_id, self.student_name)).data
        )
        self.assertTrue(status['done_with_current'])

        self._answer_problem(repeat=18)
        status = json.loads(
            self.app.get(base_api_path + '/{}/user/{}'.format(self.course_id, self.student_name)).data
        )
        # NOTE(idegtiarov) with default parameter's set student has to answer correctly not more than on 28 problems
        # from 56 before he will be shifted to Post_assessment part
        self.assertTrue(status['next']['posttest'])
