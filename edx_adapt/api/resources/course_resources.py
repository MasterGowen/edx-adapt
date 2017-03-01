""" This file contains api resource classes dealing with course information.
For example, CRUDding courses, users, problems, skills...
"""

from flask_restful import abort, reqparse

from edx_adapt.api.resources.base_resource import BaseResource
from edx_adapt.data.interface import DataException
from edx_adapt import logger
from edx_adapt.select.interface import SelectException

course_parser = reqparse.RequestParser()
course_parser.add_argument('course_id', type=str, required=True, location='json', help="Please supply a course ID")


class DefaultResource(BaseResource):
    def _post_request(self, function_name, *args, **kwargs):
        try:
            getattr(self.repo, function_name)(*args, **kwargs)
        except DataException as e:
            logger.exception('DataException: ')
            abort(500, message=str(e))
        return {'success': True}, 201

    def _get_request(self, function_name, *args):
        output_list = []
        try:
            output_list = getattr(self.repo, function_name)(*args)
        except DataException as e:
            logger.exception('DataException:')
            abort(404, message=str(e))
        return output_list


class Courses(DefaultResource):
    def get(self):
        courses = self._get_request('get_course_ids')
        return {'course_ids': courses}, 200

    def post(self):
        args = course_parser.parse_args()
        return self._post_request('post_course', args['course_id'])

skill_parser = reqparse.RequestParser()
skill_parser.add_argument('skill_name', type=str, required=True, location='json',
                          help="Please supply the name of a skill")


class Skills(DefaultResource):
    def get(self, course_id):
        skills = self._get_request('get_skills', course_id)
        return {'skills': skills}, 200

    def post(self, course_id):
        args = skill_parser.parse_args()
        return self._post_request('post_skill', course_id, args['skill_name'])

user_parser = reqparse.RequestParser()
user_parser.add_argument('user_id', type=str, required=True, location='json', help="Please supply a user ID")


class Users(DefaultResource):
    def get(self, course_id):
        finished_users = self._get_request('get_finished_users', course_id)
        progress_users = self._get_request('get_in_progress_users', course_id)
        return {'users': {'finished': finished_users, 'in_progress': progress_users}}, 200

    def post(self, course_id):
        args = user_parser.parse_args()
        try:
            self.repo.enroll_user(course_id, args['user_id'])
            first_prob = self.selector.choose_first_problem(course_id, args['user_id'])
            if not first_prob:
                first_prob = self.selector.choose_next_problem(course_id, args['user_id'])
                logger.info(
                    "There are no pre-assessment problems in the course, first problem is selected from base problem "
                    "scope: {}".format(first_prob)
                )
            else:
                logger.info("Pre-assessment problem is found and selected: {}".format(first_prob))
            self.repo.set_next_problem(course_id, args['user_id'], first_prob)
        except DataException as e:
            abort(500, message="Student cannot be enrolled because of database issues: {}".format(e))
        except SelectException as e:
            abort(500, message="Student cannot be enrolled because of next problem selecting issues: {}".format(e))
        return {'success': True}, 200


problem_parser = reqparse.RequestParser()
problem_parser.add_argument('problem_name', type=str, required=True,  location='json',
                            help="Please supply a problem name")
problem_parser.add_argument('tutor_url', type=str, required=True, location='json',
                            help="Please supply a link to the problem's page in your tutor")
problem_parser.add_argument('skills', type=list, required=True, location='json',
                            help="Please supply a list of skills that this problem teaches")
problem_parser.add_argument('pretest', type=bool, location='json',
                            help="Set True if this is a pretest problem. Mutually exclusive with posttest")
problem_parser.add_argument('posttest', type=bool, location='json',
                            help="Set True if this is a posttest problem. Mutually exclusive with pretest")


class Problems(DefaultResource):
    def get(self, course_id, skill_name=None):
        problems = self._get_request('get_problems', course_id, skill_name)
        return {'problems': problems}, 200

    def post(self, course_id):
        args = problem_parser.parse_args()
        logger.debug("Post problem args: {}".format(args))
        return self._post_request(
            'post_problem',
            course_id,
            args['skills'],
            args['problem_name'],
            args['tutor_url'],
            args['pretest'],
            args['posttest']
        )

experiment_parser = reqparse.RequestParser()
experiment_parser.add_argument('experiment_name', type=str, location='json', required=True,
                               help="Please supply the name of the experiment")
experiment_parser.add_argument('start_time', type=int, location='json', required=True,
                               help="Please supply the start date in unix seconds")
experiment_parser.add_argument('end_time', type=int, location='json', required=True,
                               help="Please supply the end date in unix seconds")


class Experiments(DefaultResource):
    def get(self, course_id):
        exps = self._get_request('get_experiments', course_id)
        return {'experiments': exps}

    def post(self, course_id):
        args = experiment_parser.parse_args()
        return self._post_request(
            'post_experiment', course_id, args['experiment_name'], args['start_time'], args['end_time']
        )

prob_parser = reqparse.RequestParser()
prob_parser.add_argument('prob_list', type=list, location='json', help="Please supply list with default model_params")


class Probabilities(DefaultResource):
    def get(self, course_id):
        prob_list = self._get_request('get_model_params', course_id)
        return {'model_params': prob_list}, 200

    def post(self, course_id):
        args = prob_parser.parse_args()
        return self._post_request('post_model_params', course_id, args['prob_list'], new=True)

    def put(self, course_id):
        args = prob_parser.parse_args()
        return self._post_request('post_model_params', course_id, args['prob_list'])
