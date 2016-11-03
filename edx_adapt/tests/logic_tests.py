import os
# from . import edx_adapt
import edx_adapt

import unittest
import tempfile

import string
import random

COURSE_ID = 'CMUSTAT101'


def id_generator(size=6, chars=string.ascii_uppercase + string.digits):
    return ''.join(random.choice(chars) for _ in range(size))


class EdxAdaptTestCase(unittest.TestCase):
    def setUp(self):
        self.db_fd, edx_adapt.app.config['DATABASE'] = tempfile.mkstemp() # FIXME
        edx_adapt.app.config['TESTING'] = True
        self.app = edx_adapt.app.test_client()
        with edx_adapt.app.app_context():
            edx_adapt.init_db() # FIXME

    def tearDown(self):
        os.close(self.db_fd)
        os.unlink(edx_adapt.app.config['DATABASE'])


class AllCorrectPreAssessmentTestCase(EdxAdaptTestCase):
    def setUp(self):
        super(AllCorrectPreAssessmentTestCase, self).setUp()
        # XXX Setup course?

        # set up new student
        self.student_name = 'test_student_' + id_generator()

        self.p = {'pg': 0.25, 'ps': 0.25, 'pi': 0.1, 'pt': 0.5, 'threshold': 0.99}  # Default student params
        skills = [
            'center', 'shape', 'spread', 'x axis', 'y axis', 'h to d',
            'd to h', 'histogram', 'None'
        ]

        for skill in skills:
            payload = {'course_id': COURSE_ID, 'params': self.p,
                       'user_id': self.student_name, 'skill_name': skill}
            self.app.post('/api/v1/parameters', data=payload)  # XXX: jsonify?

    def test_student_cut_off_after_all_correct_answers(self):
        pre_assessments = ['Pre-assessment_{}'.format(i) for i in range(0, 13)]
        for problem in pre_assessments:
            data = {'problem': problem, 'correct': True, 'attempt': 1}
            self.app.post(
                '/api/v1/course/{}/user/{}/interaction/'.format(COURSE_ID, self.student_name),
                data=data  # XXX: jsonify?
            )

        status = self.app.get('/api/v1/course/{}/user/{}'.format(COURSE_ID, self.student_name))
        self.assertEqual(status['done_with_course'], True)


if __name__ == '__main__':
    unittest.main()
