""" This file contains api resources for setting model parameters for a course
"""
import random

from flask_restful import Resource, abort, reqparse

from edx_adapt.data.interface import DataException
from edx_adapt import logger
from edx_adapt.select.interface import SelectException

param_parser = reqparse.RequestParser()
param_parser.add_argument('course_id', type=str, location='json', help="Optionally supply a course id")
param_parser.add_argument('user_id', type=str, location='json', help="Optionally supply a user ID")
param_parser.add_argument('skill_name', type=str, location='json', help="Optionally supply the name of a skill")
param_parser.add_argument('params', type=dict, location='json', required=True,
                          help="Please supply the desired model parameters as a dictionary")


class Parameters(Resource):
    def __init__(self, **kwargs):
        """
        @type repo: DataInterface
        @type selector: SelectInterface
        """
        self.repo = kwargs['data']
        self.selector = kwargs['selector']

    def get(self):
        param_list = []
        try:
            param_list = self.selector.get_all_parameters()
        except SelectException as e:
            abort(500, message=str(e))
        return {'parameters': param_list}, 200

    def post(self):
        args = param_parser.parse_args()
        course = args['course_id']
        user = args['user_id']
        skill = args['skill_name']
        params = args['params']

        prob_list = self.repo.get_model_params(course)
        if prob_list:
            params = random.choice(prob_list)
        try:
            self.selector.set_parameter(params, course, user, skill)
        except SelectException as e:
            abort(500, message=str(e))

        return {'success': True}, 200

param_bulk_parser = reqparse.RequestParser()
param_bulk_parser.add_argument('course_id', type=str, location='json', help="Optionally supply a course id")
param_bulk_parser.add_argument('user_id', type=str, location='json', help="Optionally supply a user ID")
param_bulk_parser.add_argument(
    'skills_list', type=list, location='json', help="Optionally supply the list with skill names"
)
param_bulk_parser.add_argument(
    'params',
    type=dict,
    location='json',
    required=True,
    help="Please supply the desired model parameters as a dictionary")


class ParametersBulk(Resource):
    def __init__(self, **kwargs):
        self.repo = kwargs['data']
        self.selector = kwargs['selector']

    def get(self):
        param_list = []
        try:
            param_list = self.selector.get_all_parameters()
        except SelectException as e:
            abort(500, message=str(e))
        return {'parameters': param_list}, 200

    def post(self):
        args = param_parser.parse_args()
        course = args['course_id']
        user = args['user_id']
        default_param = None

        try:
            skills_list = self.repo.get_skills(course)
            logger.debug(
                "Skills for the student {} are taken directly from the course {} in which student is enrolled".format(
                    user, course
                )
            )
        except DataException:
            logger.exception(
                "Skills field are not found in the course: {}, student's skills cannot be added".format(course)
            )
            abort(
                500,
                "Course doesn't contain skills, please update the course {} and try adding student again.".format(
                    course
                )
            )
        try:
            key = self.create_search_key(course, user)
            default_param = self.repo.get(key) or self.repo.get_model_params(course)
        except DataException:
            logger.debug(
                "Default model's parameters are not found, adapt enrolls user with parameters: {}".format(
                    args['params']
                )
            )
            pass
        if default_param and isinstance(default_param, list):
            params = random.choice(default_param)
            logger.debug("Default model's parameters are found, adapt enrolls user with parameters: {}".format(params))
        elif default_param:
            params = default_param
            logger.debug(
                "Adapt enrolls user with parameters which is already used by the user in other adaptive course's "
                "section: {}".format(params)
            )
        else:
            params = args['params']
        try:
            for skill in skills_list:
                self.selector.set_parameter(params, course, user, skill)
        except SelectException as e:
            abort(500, message=str(e))
        return {'success': True, 'configuredSkills': skills_list}, 201

    @staticmethod
    def create_search_key(course, user):
        """
        Creates key value with regular expression for $regex query in MongoDB collection

        :param course: course_id
        :param user: user_id
        :return: dict for MongoDB query
        """
        # For regex query we need main part of the course_id either course_id complex (with section part) or not
        main_course = course.split(':')[0]
        course_escape = main_course.replace('+', '\\+')  # '+' char should be escaped with '\'
        return {'$regex': '{course_id}.+{user_id}'.format(course_id=course_escape, user_id=user)}
